"""
ETL upsert pipeline: MySQL → report_payments, report_line_items, report_payment_allocations.

## Data quality issues in the MySQL source (design decisions)

1. payment.paymentDate IS NULL for ~78% of approved payments.
   Decision: fall back to payment.createdAt, never to NULL or today's date.

2. Garbage years in paymentDate (e.g. year 206, 1901).
   Decision: sanitise inside PAYMENTS_FOR_CARTS_QUERY with
   BETWEEN '2000-01-01' AND '2099-12-31'; fall back to createdAt.

3. Negative remainder (SUM(student_payment.amount for P) > P.quantity).
   This means a data-entry error in the source: more was recorded via
   student_payments than the actual payment collected.
   Decision: write negative allocation amounts as-is. Do NOT clamp to zero.
   A negative allocated_amount in report_payment_allocations is the data
   quality signal. Clamping hides the error and distorts sin_categorizar.
   Frontend: render sin_categorizar in warning colour when < 0.

4. student_payments records inserted/modified without touching payment.updatedAt.
   This is a pre-existing ETL detection gap: the since-window query
   (pay.updatedAt > :since) will miss student_payment-only changes.
   Decision: acknowledged, out of scope here.

5. Books and courses have no rows in student_payments by design.
   Decision: remainder allocation is the best available approximation of
   which payment covered which book product.

6. first_payment_date on report_line_items = MIN(allocation.payment_date).
   This is the canonical date for filtering a product's quantity into a
   reporting period. A product whose contract was signed in Nov 2025 but
   whose first payment arrived Jan 2026 has first_payment_date = 2026-01-xx
   and correctly appears only in 2026 filters.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import bindparam, text

from app.database import SessionLocal
from app.enums import ETLJobName, ExamCategory, PaymentStatus, ProductType
from app.reporting.database import ReportingSessionLocal
from app.services.por_asesor.product_grouping import canonical_exam_category, canonical_exam_name
from app.etl.shared import (
    LEAD_ADDRESS_SUBQUERY,
    calculate_business_status,
    coerce_to_date,
    convert_currency,
    extract_dimensions,
    log_etl_run,
    prefetch_rates,
    resolve_business_status,
)

logger = logging.getLogger(__name__)


PAYMENT_EXTRACT_QUERY = """
    SELECT
        pay.id                              AS payment_id,
        pay.quantity                        AS amount,
        pay.status                          AS payment_status,
        pay.paymentDate                     AS payment_date,
        c.id                                AS cart_id,
        c.createdAt                         AS created_at,
        c.deletedAt                         AS cart_deleted_at,
        s.id                                AS seller_id,
        CONCAT(s.name, ' ', s.lastName)     AS seller_name,
        l.id                                AS lead_id,
        l.name                              AS school_name,
        l.site                              AS site,
        z.name                              AS zone_name,
        la.stateName                        AS state_name,
        la.city                             AS city,
        la.state_names                      AS all_states,
        la.city_names                       AS all_cities
    FROM payment pay
    JOIN cart c ON pay.cartId = c.id
    JOIN seller_lead sl ON c.sellerLeadId = sl.id
    JOIN seller s ON sl.sellerId = s.id
    JOIN `lead` l ON sl.leadId = l.id
    LEFT JOIN zone z ON l.zoneId = z.id
    {LEAD_ADDRESS_SUBQUERY}
    WHERE pay.updatedAt > :since
"""

LINE_ITEM_EXTRACT_QUERY = """
    SELECT
        cp.id                               AS cart_product_id,
        cp.total                            AS expected_total,
        cp.cost                             AS expected_cost,
        cp.quantity                         AS quantity,
        cp.discount                         AS discount,
        c.id                                AS cart_id,
        c.bookCommission                    AS book_commission,
        c.examCommission                    AS exam_commission,
        c.createdAt                         AS created_at,
        p.id                                AS product_id,
        p.productType                       AS product_type,
        ec.name                             AS exam_cat_name,
        ec.dateType                         AS exam_date_type,
        s.id                                AS seller_id,
        CONCAT(s.name, ' ', s.lastName)     AS seller_name,
        l.id                                AS lead_id,
        l.name                              AS school_name,
        l.site                              AS site,
        z.name                              AS zone_name,
        la.stateName                        AS state_name,
        la.city                             AS city,
        la.state_names                      AS all_states,
        la.city_names                       AS all_cities,
        COALESCE(pa.paid_total, 0)          AS paid_total,
        COALESCE(pa.student_count, 0)       AS student_count,
        COALESCE(pa.payment_count, 0)       AS payment_count,
        pa.payment_date                     AS payment_date
    FROM (
        SELECT DISTINCT pay.cartId
        FROM payment pay
        WHERE pay.updatedAt > :since
    ) affected
    JOIN cart c ON c.id = affected.cartId
    JOIN cart_product cp ON cp.cartId = c.id
    JOIN product p ON cp.productId = p.id
    LEFT JOIN exam_cat ec ON p.examId = ec.id
    JOIN seller_lead sl ON c.sellerLeadId = sl.id
    JOIN seller s ON sl.sellerId = s.id
    JOIN `lead` l ON sl.leadId = l.id
    LEFT JOIN zone z ON l.zoneId = z.id
    {LEAD_ADDRESS_SUBQUERY}
    LEFT JOIN (
        SELECT
            st.cartProductId                AS cart_product_id,
            COALESCE(SUM(sp.amount), 0)     AS paid_total,
            COUNT(DISTINCT st.id)           AS student_count,
            COUNT(DISTINCT sp.payment_id)   AS payment_count,
            MAX(pay.paymentDate)            AS payment_date
        FROM student_payments sp
        JOIN student st ON sp.student_id = st.id
        JOIN payment pay ON sp.payment_id = pay.id
        WHERE pay.status = :payment_status
        GROUP BY st.cartProductId
    ) pa ON pa.cart_product_id = cp.id
    WHERE c.deletedAt IS NULL
    AND cp.deletedAt IS NULL
    AND EXISTS (
        SELECT 1
        FROM payment pay2
        WHERE pay2.cartId = c.id
        AND pay2.status = :payment_status
    )
"""

# For all approved payments on affected carts, fetch the amount that went to each
# cart_product via student_payments.  Used by _build_allocation_rows_v2 to apply
# the remainder approach: products with student_payments get their exact amount;
# the remainder is distributed proportionally among products without.
STUDENT_AMOUNTS_BY_PAYMENT_QUERY = """
    SELECT
        sp.payment_id                   AS payment_id,
        st.cartProductId                AS cart_product_id,
        SUM(sp.amount)                  AS student_amount
    FROM student_payments sp
    JOIN student st  ON st.id       = sp.student_id
    JOIN payment pay ON pay.id      = sp.payment_id
    WHERE pay.cartId IN :cart_ids
      AND pay.status = :payment_status
    GROUP BY sp.payment_id, st.cartProductId
"""

# All approved payments for affected carts with the dimensions needed for
# allocation rows.  Fetches the complete approved history (not windowed by :since)
# so incremental ETL re-runs always rebuild full allocation rows for the cart.
#
# payment_date sanitisation (see module docstring, points 1 & 2):
#   paymentDate NULL → createdAt; garbage years → createdAt.
PAYMENTS_FOR_CARTS_QUERY = """
    SELECT
        pay.id                              AS payment_id,
        pay.cartId                          AS cart_id,
        pay.quantity                        AS quantity,
        CASE
            WHEN pay.paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
            THEN pay.paymentDate
            ELSE DATE(pay.createdAt)
        END                                 AS payment_date,
        s.id                                AS seller_id,
        CONCAT(s.name, ' ', s.lastName)     AS seller_name,
        l.id                                AS lead_id,
        l.site                              AS site
    FROM payment pay
    JOIN cart c ON c.id = pay.cartId
    JOIN seller_lead sl ON sl.id = c.sellerLeadId
    JOIN seller s ON s.id = sl.sellerId
    JOIN `lead` l ON l.id = sl.leadId
    WHERE pay.cartId IN :cart_ids
      AND pay.status = :payment_status
      AND c.deletedAt IS NULL
"""

DELETED_CART_PRODUCTS_QUERY = """
    SELECT cp.id
    FROM cart_product cp
    WHERE cp.deletedAt IS NOT NULL
    AND cp.deletedAt >= :since
"""

DELETED_CARTS_QUERY = """
    SELECT c.id
    FROM cart c
    WHERE c.deletedAt IS NOT NULL
    AND c.deletedAt >= :since
"""


async def _extract_all(since: datetime) -> tuple[list, list, list[int], list[int]]:
    async def _fetch_mappings(query: str, params: dict) -> list[dict]:
        async with SessionLocal() as source:
            result = await source.execute(text(query), params)
            return [dict(row) for row in result.mappings().fetchall()]

    async def _fetch_ids(query: str, params: dict) -> list[int]:
        async with SessionLocal() as source:
            result = await source.execute(text(query), params)
            return [int(row[0]) for row in result.fetchall()]

    (
        payment_rows,
        line_item_rows,
        deleted_cart_product_ids,
        deleted_cart_ids,
    ) = await asyncio.gather(
        _fetch_mappings(
            PAYMENT_EXTRACT_QUERY.format(LEAD_ADDRESS_SUBQUERY=LEAD_ADDRESS_SUBQUERY),
            {"since": since},
        ),
        _fetch_mappings(
            LINE_ITEM_EXTRACT_QUERY.format(LEAD_ADDRESS_SUBQUERY=LEAD_ADDRESS_SUBQUERY),
            {"since": since, "payment_status": PaymentStatus.APROBADO.value},
        ),
        _fetch_ids(DELETED_CART_PRODUCTS_QUERY, {"since": since}),
        _fetch_ids(DELETED_CARTS_QUERY, {"since": since}),
    )
    return (
        payment_rows,
        line_item_rows,
        deleted_cart_product_ids,
        deleted_cart_ids,
    )


async def _build_allocation_rows_v2(
    payments_for_carts: list[dict],
    student_amounts_by_key: dict[tuple[int, int], float],
    cart_products_by_cart: dict[int, list[dict]],
    rates: dict,
) -> tuple[list[dict], dict[int, date | None]]:
    """
    Build allocation rows using the remainder approach (see module docstring).

    For each approved payment P on an affected cart:
      1. Products WITH student_payments for P → allocated = student_amount exactly.
      2. remainder = P.quantity − SUM(student amounts for P across all products)
      3. Products WITHOUT student_payments for P → allocated = remainder × (cp.expected_total /
         SUM(expected_total for no-student products)). Proportional to agreed price.
      4. If remainder < 0 (data quality error), allocated values for non-student
         products go negative. Surfaced as-is — do not clamp (see module docstring #3).

    Returns:
        allocation_rows: one dict per (payment_id, cart_product_id)
        cp_first_payment_dates: {cart_product_id: MIN(payment_date for this cp)}
    """
    allocation_rows: list[dict] = []
    cp_first_dates: dict[int, date | None] = {}

    for pay in payments_for_carts:
        payment_id = int(pay["payment_id"])
        cart_id = int(pay["cart_id"])
        quantity = float(pay["quantity"] or 0)
        payment_date = coerce_to_date(pay.get("payment_date"))
        site = pay.get("site", "")
        seller_id = pay.get("seller_id")
        seller_name = pay.get("seller_name")
        lead_id = pay.get("lead_id")

        cart_products = cart_products_by_cart.get(cart_id, [])
        if not cart_products:
            continue

        # Split products into those with and without student amounts for this payment
        with_student: list[tuple[dict, float]] = []
        without_student: list[dict] = []
        for cp in cart_products:
            cp_id = int(cp["cart_product_id"])
            student_amt = student_amounts_by_key.get((payment_id, cp_id))
            if student_amt is not None:
                with_student.append((cp, float(student_amt)))
            else:
                without_student.append(cp)

        total_student = sum(amt for _, amt in with_student)
        remainder = quantity - total_student

        # Denominator for proportional remainder split
        no_student_total = sum(float(cp["expected_total"] or 0) for cp in without_student)

        for cp, student_amt in with_student:
            cp_id = int(cp["cart_product_id"])
            allocated = student_amt
            mxn, usd = await convert_currency(allocated, site, payment_date or date.today(), rates)
            raw_pt = cp.get("product_type") or ""
            product_type = raw_pt if raw_pt in ("exam", "book", "course") else "UNCATEGORIZED"
            allocation_rows.append({
                "payment_id": payment_id,
                "cart_product_id": cp_id,
                "etl_date": datetime.now().date(),
                "payment_date": payment_date,
                "allocated_amount": allocated,
                "allocated_amount_mxn": mxn,
                "allocated_amount_usd": usd,
                "seller_id": seller_id,
                "seller_name": seller_name,
                "lead_id": lead_id,
                "site": site,
                "product_type": product_type,
                "is_active": True,
            })
            if payment_date is not None:
                prev = cp_first_dates.get(cp_id)
                cp_first_dates[cp_id] = min(prev, payment_date) if prev else payment_date

        for cp in without_student:
            cp_id = int(cp["cart_product_id"])
            expected = float(cp["expected_total"] or 0)
            if no_student_total > 0:
                allocated = remainder * expected / no_student_total
            elif len(without_student) > 0:
                # No expected prices to weight by — split evenly
                allocated = remainder / len(without_student)
            else:
                allocated = 0.0
            allocated = round(allocated, 2)
            mxn, usd = await convert_currency(allocated, site, payment_date or date.today(), rates)
            raw_pt = cp.get("product_type") or ""
            product_type = raw_pt if raw_pt in ("exam", "book", "course") else "UNCATEGORIZED"
            allocation_rows.append({
                "payment_id": payment_id,
                "cart_product_id": cp_id,
                "etl_date": datetime.now().date(),
                "payment_date": payment_date,
                "allocated_amount": allocated,
                "allocated_amount_mxn": mxn,
                "allocated_amount_usd": usd,
                "seller_id": seller_id,
                "seller_name": seller_name,
                "lead_id": lead_id,
                "site": site,
                "product_type": product_type,
                "is_active": True,
            })
            if payment_date is not None:
                prev = cp_first_dates.get(cp_id)
                cp_first_dates[cp_id] = min(prev, payment_date) if prev else payment_date

    return allocation_rows, cp_first_dates


async def _transform_payment(
    row: dict, ganados: set[int], perdidos: set[int], mantenidos: set[int], rates: dict
) -> dict:
    dims = extract_dimensions(row)
    amount = float(row.get("amount") or 0)
    rate_date = coerce_to_date(row.get("payment_date"), dims["created_at"].date())
    amount_mxn, amount_usd = await convert_currency(amount, row.get("site", ""), rate_date, rates)
    payment_status = row.get("payment_status") or PaymentStatus.UNCATEGORIZED.value
    cart_deleted_at = row.get("cart_deleted_at")
    return {
        **dims,
        "payment_id": row["payment_id"],
        "cart_id": row["cart_id"],
        "payment_date": rate_date,  # sanitized: createdAt fallback already applied
        "payment_status": payment_status,
        "business_status": resolve_business_status(row["lead_id"], ganados, perdidos, mantenidos),
        "amount": amount,
        "amount_mxn": amount_mxn,
        "amount_usd": amount_usd,
        "is_active": payment_status != PaymentStatus.CANCELADO.value and cart_deleted_at is None,
    }


async def _transform_line_item(
    row: dict,
    ganados: set[int],
    perdidos: set[int],
    mantenidos: set[int],
    rates: dict,
    cp_first_payment_dates: dict[int, date | None],
) -> dict:
    dims = extract_dimensions(row)
    product_type = row.get("product_type") or ""
    exam_cat_name = row.get("exam_cat_name") or ""
    expected_total = float(row.get("expected_total") or 0)
    expected_cost = float(row.get("expected_cost") or 0)
    site = row.get("site", "")
    # Use first_payment_date for the FX rate date when converting expected amounts.
    # Falls back to cart.createdAt when no payment has been applied yet.
    cp_id = int(row["cart_product_id"])
    first_payment_date = cp_first_payment_dates.get(cp_id)
    rate_date = first_payment_date or dims["created_at"].date()
    expected_total_mxn, expected_total_usd = await convert_currency(
        expected_total, site, rate_date, rates
    )
    expected_cost_mxn, expected_cost_usd = await convert_currency(
        expected_cost, site, rate_date, rates
    )
    return {
        **dims,
        "cart_product_id": row["cart_product_id"],
        "cart_id": row["cart_id"],
        "product_id": row["product_id"],
        "product_type": product_type
        if product_type in [e.value for e in ProductType]
        else ProductType.UNCATEGORIZED.value,
        "exam_cat_name": exam_cat_name or None,
        "exam_category": canonical_exam_category(exam_cat_name)
        if exam_cat_name
        else ExamCategory.UNCATEGORIZED.value,
        "exam_canonical_name": canonical_exam_name(exam_cat_name)
        if exam_cat_name
        else "UNCATEGORIZED",
        "exam_date_type": row.get("exam_date_type"),
        "billing_status": PaymentStatus.APROBADO.value,
        "payment_status": PaymentStatus.APROBADO.value,
        "business_status": resolve_business_status(row["lead_id"], ganados, perdidos, mantenidos),
        "is_active": True,
        "include_in_product_breakdown": first_payment_date is not None,
        "quantity": int(row.get("quantity") or 0),
        "expected_total": expected_total,
        "expected_cost": expected_cost,
        "discount": float(row["discount"]) if row.get("discount") is not None else None,
        "book_commission": float(row["book_commission"])
        if row.get("book_commission") is not None
        else None,
        "exam_commission": float(row["exam_commission"])
        if row.get("exam_commission") is not None
        else None,
        "expected_total_mxn": expected_total_mxn,
        "expected_total_usd": expected_total_usd,
        "expected_cost_mxn": expected_cost_mxn,
        "expected_cost_usd": expected_cost_usd,
        "first_payment_date": first_payment_date,
        "student_count": int(row.get("student_count") or 0),
        "payment_count": int(row.get("payment_count") or 0),
        "total": expected_total,
        "cost": expected_cost,
        "total_mxn": expected_total_mxn,
        "total_usd": expected_total_usd,
        "cost_mxn": expected_cost_mxn,
        "cost_usd": expected_cost_usd,
    }


async def _delete_allocations(session, payment_ids: list[int]) -> None:
    if not payment_ids:
        return
    await session.execute(
        text("DELETE FROM report_payment_allocations WHERE payment_id = ANY(:pids)"),
        {"pids": payment_ids},
    )


async def _upsert_payments(session, rows: list[dict]) -> None:
    if not rows:
        return
    chunk_size = 500
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        await session.execute(
            text("""
                INSERT INTO report_payments (
                    payment_id, etl_date, seller_id, seller_name,
                    lead_id, school_name, site, zone_name, state_name, city,
                    all_states, all_cities, state_names, city_names, year, month, created_at, payment_date,
                    base_currency, cart_id, payment_status, business_status,
                    amount, amount_mxn, amount_usd, is_active
                ) VALUES (
                    :payment_id, :etl_date, :seller_id, :seller_name,
                    :lead_id, :school_name, :site, :zone_name, :state_name, :city,
                    :all_states, :all_cities, :state_names, :city_names, :year, :month, :created_at, :payment_date,
                    :base_currency, :cart_id, :payment_status, :business_status,
                    :amount, :amount_mxn, :amount_usd, :is_active
                )
                ON CONFLICT (payment_id) DO UPDATE SET
                    etl_date        = EXCLUDED.etl_date,
                    seller_name     = EXCLUDED.seller_name,
                    school_name     = EXCLUDED.school_name,
                    site            = EXCLUDED.site,
                    zone_name       = EXCLUDED.zone_name,
                    state_name      = EXCLUDED.state_name,
                    city            = EXCLUDED.city,
                    all_states      = EXCLUDED.all_states,
                    all_cities      = EXCLUDED.all_cities,
                    state_names     = EXCLUDED.state_names,
                    city_names      = EXCLUDED.city_names,
                    payment_date    = EXCLUDED.payment_date,
                    payment_status  = EXCLUDED.payment_status,
                    business_status = EXCLUDED.business_status,
                    amount          = EXCLUDED.amount,
                    amount_mxn      = EXCLUDED.amount_mxn,
                    amount_usd      = EXCLUDED.amount_usd,
                    is_active       = EXCLUDED.is_active
            """),
            chunk,
        )


async def _upsert_line_items(session, rows: list[dict]) -> None:
    if not rows:
        return
    chunk_size = 500
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        await session.execute(
            text("""
                INSERT INTO report_line_items (
                    cart_product_id, etl_date, seller_id, seller_name,
                    lead_id, school_name, site, zone_name, state_name, city,
                    all_states, all_cities, state_names, city_names,
                    year, month, created_at, first_payment_date, base_currency,
                    cart_id, product_id, product_type, exam_cat_name, exam_category,
                    exam_canonical_name, exam_date_type, billing_status, payment_status, business_status,
                    is_active, include_in_product_breakdown, quantity,
                    expected_total, expected_cost, discount, book_commission, exam_commission,
                    expected_total_mxn, expected_total_usd, expected_cost_mxn, expected_cost_usd,
                    student_count, payment_count,
                    total, cost, total_mxn, total_usd, cost_mxn, cost_usd
                ) VALUES (
                    :cart_product_id, :etl_date, :seller_id, :seller_name,
                    :lead_id, :school_name, :site, :zone_name, :state_name, :city,
                    :all_states, :all_cities, :state_names, :city_names,
                    :year, :month, :created_at, :first_payment_date, :base_currency,
                    :cart_id, :product_id, :product_type, :exam_cat_name, :exam_category,
                    :exam_canonical_name, :exam_date_type, :billing_status, :payment_status, :business_status,
                    :is_active, :include_in_product_breakdown, :quantity,
                    :expected_total, :expected_cost, :discount, :book_commission, :exam_commission,
                    :expected_total_mxn, :expected_total_usd, :expected_cost_mxn, :expected_cost_usd,
                    :student_count, :payment_count,
                    :total, :cost, :total_mxn, :total_usd, :cost_mxn, :cost_usd
                )
                ON CONFLICT (cart_product_id) DO UPDATE SET
                    etl_date                     = EXCLUDED.etl_date,
                    seller_name                  = EXCLUDED.seller_name,
                    school_name                  = EXCLUDED.school_name,
                    site                         = EXCLUDED.site,
                    zone_name                    = EXCLUDED.zone_name,
                    state_name                   = EXCLUDED.state_name,
                    city                         = EXCLUDED.city,
                    all_states                   = EXCLUDED.all_states,
                    all_cities                   = EXCLUDED.all_cities,
                    state_names                  = EXCLUDED.state_names,
                    city_names                   = EXCLUDED.city_names,
                    first_payment_date           = EXCLUDED.first_payment_date,
                    product_type                 = EXCLUDED.product_type,
                    exam_category                = EXCLUDED.exam_category,
                    exam_canonical_name          = EXCLUDED.exam_canonical_name,
                    billing_status               = EXCLUDED.billing_status,
                    payment_status               = EXCLUDED.payment_status,
                    business_status              = EXCLUDED.business_status,
                    is_active                    = EXCLUDED.is_active,
                    include_in_product_breakdown = EXCLUDED.include_in_product_breakdown,
                    quantity                     = EXCLUDED.quantity,
                    expected_total               = EXCLUDED.expected_total,
                    expected_cost                = EXCLUDED.expected_cost,
                    discount                     = EXCLUDED.discount,
                    book_commission              = EXCLUDED.book_commission,
                    exam_commission              = EXCLUDED.exam_commission,
                    expected_total_mxn           = EXCLUDED.expected_total_mxn,
                    expected_total_usd           = EXCLUDED.expected_total_usd,
                    expected_cost_mxn            = EXCLUDED.expected_cost_mxn,
                    expected_cost_usd            = EXCLUDED.expected_cost_usd,
                    student_count                = EXCLUDED.student_count,
                    payment_count                = EXCLUDED.payment_count,
                    total                        = EXCLUDED.total,
                    cost                         = EXCLUDED.cost,
                    total_mxn                    = EXCLUDED.total_mxn,
                    total_usd                    = EXCLUDED.total_usd,
                    cost_mxn                     = EXCLUDED.cost_mxn,
                    cost_usd                     = EXCLUDED.cost_usd
            """),
            chunk,
        )


async def _upsert_allocations(session, rows: list[dict]) -> None:
    if not rows:
        return
    chunk_size = 500
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        await session.execute(
            text("""
                INSERT INTO report_payment_allocations (
                    payment_id, cart_product_id, etl_date,
                    payment_date, allocated_amount, allocated_amount_mxn, allocated_amount_usd,
                    seller_id, seller_name, lead_id, site, product_type, is_active
                ) VALUES (
                    :payment_id, :cart_product_id, :etl_date,
                    :payment_date, :allocated_amount, :allocated_amount_mxn, :allocated_amount_usd,
                    :seller_id, :seller_name, :lead_id, :site, :product_type, :is_active
                )
                ON CONFLICT (payment_id, cart_product_id) DO UPDATE SET
                    etl_date             = EXCLUDED.etl_date,
                    payment_date         = EXCLUDED.payment_date,
                    allocated_amount     = EXCLUDED.allocated_amount,
                    allocated_amount_mxn = EXCLUDED.allocated_amount_mxn,
                    allocated_amount_usd = EXCLUDED.allocated_amount_usd,
                    seller_id            = EXCLUDED.seller_id,
                    seller_name          = EXCLUDED.seller_name,
                    lead_id              = EXCLUDED.lead_id,
                    site                 = EXCLUDED.site,
                    product_type         = EXCLUDED.product_type,
                    is_active            = EXCLUDED.is_active
            """),
            chunk,
        )


async def _delete_line_items(session, cart_product_ids: list[int], cart_ids: list[int]) -> None:
    if cart_product_ids:
        await session.execute(
            text("DELETE FROM report_line_items WHERE cart_product_id = ANY(:cart_product_ids)"),
            {"cart_product_ids": cart_product_ids},
        )
    if cart_ids:
        await session.execute(
            text("DELETE FROM report_line_items WHERE cart_id = ANY(:cart_ids)"),
            {"cart_ids": cart_ids},
        )


async def run_upsert(
    *, since: datetime | None = None, job_name: ETLJobName = ETLJobName.UPSERT
) -> dict:
    start = datetime.now()
    since = since or (datetime.now() - timedelta(hours=3))
    try:
        (
            payment_rows_raw,
            line_item_rows_raw,
            deleted_cart_product_ids,
            deleted_cart_ids,
        ) = await _extract_all(since)
        if (
            not payment_rows_raw
            and not line_item_rows_raw
            and not deleted_cart_product_ids
            and not deleted_cart_ids
        ):
            await log_etl_run(job_name, 0, "success", start)
            return {"payments": 0, "line_items": 0, "allocations": 0, "deleted": 0}

        all_lead_ids = {int(row["lead_id"]) for row in [*payment_rows_raw, *line_item_rows_raw]}
        ganados, perdidos, mantenidos = await calculate_business_status(all_lead_ids)

        # Derive the affected cart IDs and payment IDs from the since-windowed results.
        affected_cart_ids = list({int(row["cart_id"]) for row in line_item_rows_raw})
        affected_payment_ids = list({int(row["payment_id"]) for row in payment_rows_raw})

        # Build cart_products_by_cart from the already-fetched line_item_rows_raw —
        # no additional MySQL query needed.
        cart_products_by_cart: dict[int, list[dict]] = {}
        for row in line_item_rows_raw:
            cart_id = int(row["cart_id"])
            cart_products_by_cart.setdefault(cart_id, []).append({
                "cart_product_id": int(row["cart_product_id"]),
                "expected_total": float(row.get("expected_total") or 0),
                "product_type": row.get("product_type"),
            })

        # Fetch student amounts and full payment history for affected carts in parallel.
        # Both queries are not windowed by :since — they fetch the complete approved
        # history for the affected carts so incremental re-upserts rebuild full allocations.
        student_amounts_rows: list[dict] = []
        payments_for_carts: list[dict] = []
        if affected_cart_ids:
            async def _fetch_student_amounts() -> list[dict]:
                async with SessionLocal() as source:
                    result = await source.execute(
                        text(STUDENT_AMOUNTS_BY_PAYMENT_QUERY).bindparams(
                            bindparam("cart_ids", expanding=True)
                        ),
                        {
                            "cart_ids": affected_cart_ids,
                            "payment_status": PaymentStatus.APROBADO.value,
                        },
                    )
                    return [dict(row) for row in result.mappings().fetchall()]

            async def _fetch_payments_for_carts() -> list[dict]:
                async with SessionLocal() as source:
                    result = await source.execute(
                        text(PAYMENTS_FOR_CARTS_QUERY).bindparams(
                            bindparam("cart_ids", expanding=True)
                        ),
                        {
                            "cart_ids": affected_cart_ids,
                            "payment_status": PaymentStatus.APROBADO.value,
                        },
                    )
                    return [dict(row) for row in result.mappings().fetchall()]

            student_amounts_rows, payments_for_carts = await asyncio.gather(
                _fetch_student_amounts(),
                _fetch_payments_for_carts(),
            )

        # Index student amounts by (payment_id, cart_product_id) for O(1) lookup.
        student_amounts_by_key: dict[tuple[int, int], float] = {
            (int(r["payment_id"]), int(r["cart_product_id"])): float(r["student_amount"] or 0)
            for r in student_amounts_rows
        }

        # Prefetch all FX rates needed across payment dates.
        all_dates: set[date] = {row["created_at"].date() for row in line_item_rows_raw}
        all_dates |= {
            d for row in payments_for_carts if (d := coerce_to_date(row.get("payment_date")))
        }
        all_dates |= {
            d for row in payment_rows_raw if (d := coerce_to_date(row.get("payment_date")))
        }
        rates = await prefetch_rates(all_dates)

        # Build allocation rows and first_payment_date index in one pass.
        allocation_rows, cp_first_payment_dates = await _build_allocation_rows_v2(
            payments_for_carts,
            student_amounts_by_key,
            cart_products_by_cart,
            rates,
        )

        payment_rows = [
            await _transform_payment(dict(row), ganados, perdidos, mantenidos, rates)
            for row in payment_rows_raw
        ]
        line_item_rows = [
            await _transform_line_item(
                dict(row),
                ganados,
                perdidos,
                mantenidos,
                rates,
                cp_first_payment_dates,
            )
            for row in line_item_rows_raw
        ]

        async with ReportingSessionLocal() as reporting:
            async with reporting.begin():
                await _delete_line_items(reporting, deleted_cart_product_ids, deleted_cart_ids)
                await _delete_allocations(reporting, affected_payment_ids)
                await _upsert_payments(reporting, payment_rows)
                await _upsert_line_items(reporting, line_item_rows)
                await _upsert_allocations(reporting, allocation_rows)

        total_rows = len(payment_rows) + len(line_item_rows) + len(allocation_rows)
        await log_etl_run(job_name, total_rows, "success", start)
        deleted = len(deleted_cart_product_ids) + len(deleted_cart_ids)
        duration = (datetime.now() - start).total_seconds()
        logger.info(
            "ETL upsert — payments: %d  line_items: %d  allocations: %d  deleted: %d  (%.1fs)",
            len(payment_rows),
            len(line_item_rows),
            len(allocation_rows),
            deleted,
            duration,
        )
        return {
            "payments": len(payment_rows),
            "line_items": len(line_item_rows),
            "allocations": len(allocation_rows),
            "deleted": deleted,
        }
    except Exception as error:
        await log_etl_run(job_name, 0, "failed", start, error=str(error))
        raise
