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

ALLOCATION_EXTRACT_QUERY = """
    SELECT
        pay.id                              AS payment_id,
        pay.quantity                        AS payment_amount,
        pay.paymentDate                     AS payment_date,
        c.id                                AS cart_id,
        c.createdAt                         AS created_at,
        l.site                              AS site,
        cp.id                               AS cart_product_id,
        cp.total                            AS cp_total
    FROM payment pay
    JOIN cart c ON pay.cartId = c.id
    JOIN seller_lead sl ON c.sellerLeadId = sl.id
    JOIN `lead` l ON sl.leadId = l.id
    JOIN cart_product cp ON cp.cartId = c.id
    WHERE pay.updatedAt > :since
    AND pay.status = :payment_status
    AND c.deletedAt IS NULL
    AND cp.deletedAt IS NULL
"""

# Returns one row per (cart_product, payment_date) so each payment's portion of
# paid_total can be converted at its own exchange rate rather than collapsing
# everything to MAX(payment_date).  The list of cart_product_ids is passed as a
# parameter rather than derived from the :since window so we capture ALL
# historical payments for the affected products, not just recent ones.
PAID_TOTAL_BY_DATE_QUERY = """
    SELECT
        st.cartProductId    AS cart_product_id,
        pay.paymentDate     AS payment_date,
        l.site              AS site,
        SUM(sp.amount)      AS paid_total
    FROM student_payments sp
    JOIN student st ON sp.student_id = st.id
    JOIN payment pay ON sp.payment_id = pay.id
    JOIN cart_product cp ON cp.id = st.cartProductId
    JOIN cart c ON c.id = cp.cartId
    JOIN seller_lead sl ON sl.id = c.sellerLeadId
    JOIN `lead` l ON l.id = sl.leadId
    WHERE pay.status = :payment_status
      AND st.cartProductId IN :cart_product_ids
    GROUP BY st.cartProductId, pay.paymentDate, l.site
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


async def _extract_all(since: datetime) -> tuple[list, list, list, list[int], list[int]]:
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
        allocation_rows,
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
        _fetch_mappings(
            ALLOCATION_EXTRACT_QUERY,
            {"since": since, "payment_status": PaymentStatus.APROBADO.value},
        ),
        _fetch_ids(DELETED_CART_PRODUCTS_QUERY, {"since": since}),
        _fetch_ids(DELETED_CARTS_QUERY, {"since": since}),
    )
    return (
        payment_rows,
        line_item_rows,
        allocation_rows,
        deleted_cart_product_ids,
        deleted_cart_ids,
    )


async def _build_paid_total_converted(
    paid_total_date_rows: list[dict],
    rates: dict,
) -> dict[int, tuple[float | None, float | None]]:
    """
    For each cart_product, sum the paid_total converted at each payment's own
    exchange rate.  Returns {cart_product_id: (paid_total_mxn, paid_total_usd)}.

    If any date-slice for a cart_product has an unknown site (unconvertible),
    the whole product is marked (None, None) so reporting treats it as
    uncategorized rather than applying a wrong partial rate.
    """
    accum_mxn: dict[int, float | None] = {}
    accum_usd: dict[int, float | None] = {}

    for row in paid_total_date_rows:
        cp_id = int(row["cart_product_id"])
        # Skip if already marked unconvertible by an earlier row for this product
        if cp_id in accum_mxn and accum_mxn[cp_id] is None:
            continue

        site = row.get("site", "")
        amount = float(row.get("paid_total") or 0)
        rate_date = coerce_to_date(row.get("payment_date"), date.today())
        mxn, usd = await convert_currency(amount, site, rate_date, rates)

        if mxn is None or usd is None:
            accum_mxn[cp_id] = None
            accum_usd[cp_id] = None
        else:
            accum_mxn[cp_id] = (accum_mxn.get(cp_id) or 0.0) + mxn
            accum_usd[cp_id] = (accum_usd.get(cp_id) or 0.0) + usd

    return {cp_id: (accum_mxn[cp_id], accum_usd[cp_id]) for cp_id in accum_mxn}


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
    paid_total_converted: dict[int, tuple[float | None, float | None]],
) -> dict:
    dims = extract_dimensions(row)
    product_type = row.get("product_type") or ""
    exam_cat_name = row.get("exam_cat_name") or ""
    expected_total = float(row.get("expected_total") or 0)
    expected_cost = float(row.get("expected_cost") or 0)
    paid_total = float(row.get("paid_total") or 0)
    site = row.get("site", "")
    rate_date = coerce_to_date(row.get("payment_date"), dims["created_at"].date())
    expected_total_mxn, expected_total_usd = await convert_currency(
        expected_total, site, rate_date, rates
    )
    expected_cost_mxn, expected_cost_usd = await convert_currency(
        expected_cost, site, rate_date, rates
    )
    # Use the per-payment-date conversion if available; fall back to MAX-date
    # conversion only for cart_products not covered by the breakdown query.
    cp_id = int(row["cart_product_id"])
    if cp_id in paid_total_converted:
        paid_total_mxn, paid_total_usd = paid_total_converted[cp_id]
    else:
        paid_total_mxn, paid_total_usd = await convert_currency(paid_total, site, rate_date, rates)
    payment_date = dims["payment_date"]  # already coerced via extract_dimensions
    return {
        **dims,
        "payment_date": payment_date,
        "payment_day": payment_date or dims["created_at"].date(),
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
        "include_in_product_breakdown": paid_total > 0,
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
        "paid_total": paid_total,
        "paid_total_mxn": paid_total_mxn,
        "paid_total_usd": paid_total_usd,
        "student_count": int(row.get("student_count") or 0),
        "payment_count": int(row.get("payment_count") or 0),
        "total": expected_total,
        "cost": expected_cost,
        "total_mxn": expected_total_mxn,
        "total_usd": expected_total_usd,
        "cost_mxn": expected_cost_mxn,
        "cost_usd": expected_cost_usd,
    }


async def _build_allocation_rows(allocation_rows_raw: list, rates: dict) -> list[dict]:
    cart_totals: dict[int, float] = {}
    for row in allocation_rows_raw:
        cart_totals[int(row["cart_id"])] = cart_totals.get(int(row["cart_id"]), 0.0) + float(
            row["cp_total"] or 0
        )

    rows: list[dict] = []
    for raw_row in allocation_rows_raw:
        row = dict(raw_row)
        cart_total = cart_totals.get(int(row["cart_id"]), 0.0)
        cp_total = float(row["cp_total"] or 0)
        payment_amount = float(row["payment_amount"] or 0)
        share = (cp_total / cart_total) if cart_total > 0 else 0.0
        allocated_amount = round(payment_amount * share, 2)
        rate_date = coerce_to_date(row.get("payment_date"), row["created_at"].date())
        allocated_amount_mxn, allocated_amount_usd = await convert_currency(
            allocated_amount,
            row.get("site", ""),
            rate_date,
            rates,
        )
        rows.append(
            {
                "payment_id": row["payment_id"],
                "cart_product_id": row["cart_product_id"],
                "etl_date": datetime.now().date(),
                "allocated_amount": allocated_amount,
                "allocated_amount_mxn": allocated_amount_mxn,
                "allocated_amount_usd": allocated_amount_usd,
            }
        )
    return rows


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
                    year, month, created_at, payment_date, payment_day, base_currency,
                    cart_id, product_id, product_type, exam_cat_name, exam_category,
                    exam_canonical_name, exam_date_type, billing_status, payment_status, business_status,
                    is_active, include_in_product_breakdown, quantity,
                    expected_total, expected_cost, discount, book_commission, exam_commission,
                    expected_total_mxn, expected_total_usd, expected_cost_mxn, expected_cost_usd,
                    paid_total, paid_total_mxn, paid_total_usd, student_count, payment_count,
                    total, cost, total_mxn, total_usd, cost_mxn, cost_usd
                ) VALUES (
                    :cart_product_id, :etl_date, :seller_id, :seller_name,
                    :lead_id, :school_name, :site, :zone_name, :state_name, :city,
                    :all_states, :all_cities, :state_names, :city_names,
                    :year, :month, :created_at, :payment_date, :payment_day, :base_currency,
                    :cart_id, :product_id, :product_type, :exam_cat_name, :exam_category,
                    :exam_canonical_name, :exam_date_type, :billing_status, :payment_status, :business_status,
                    :is_active, :include_in_product_breakdown, :quantity,
                    :expected_total, :expected_cost, :discount, :book_commission, :exam_commission,
                    :expected_total_mxn, :expected_total_usd, :expected_cost_mxn, :expected_cost_usd,
                    :paid_total, :paid_total_mxn, :paid_total_usd, :student_count, :payment_count,
                    :total, :cost, :total_mxn, :total_usd, :cost_mxn, :cost_usd
                )
                ON CONFLICT (cart_product_id) DO UPDATE SET
                    etl_date                    = EXCLUDED.etl_date,
                    seller_name                 = EXCLUDED.seller_name,
                    school_name                 = EXCLUDED.school_name,
                    site                        = EXCLUDED.site,
                    zone_name                   = EXCLUDED.zone_name,
                    state_name                  = EXCLUDED.state_name,
                    city                        = EXCLUDED.city,
                    all_states                  = EXCLUDED.all_states,
                    all_cities                  = EXCLUDED.all_cities,
                    state_names                 = EXCLUDED.state_names,
                    city_names                  = EXCLUDED.city_names,
                    payment_date                = EXCLUDED.payment_date,
                    payment_day                 = EXCLUDED.payment_day,
                    product_type                = EXCLUDED.product_type,
                    exam_category               = EXCLUDED.exam_category,
                    exam_canonical_name         = EXCLUDED.exam_canonical_name,
                    billing_status              = EXCLUDED.billing_status,
                    payment_status              = EXCLUDED.payment_status,
                    business_status             = EXCLUDED.business_status,
                    is_active                   = EXCLUDED.is_active,
                    include_in_product_breakdown = EXCLUDED.include_in_product_breakdown,
                    quantity                    = EXCLUDED.quantity,
                    expected_total              = EXCLUDED.expected_total,
                    expected_cost               = EXCLUDED.expected_cost,
                    discount                    = EXCLUDED.discount,
                    book_commission             = EXCLUDED.book_commission,
                    exam_commission             = EXCLUDED.exam_commission,
                    expected_total_mxn          = EXCLUDED.expected_total_mxn,
                    expected_total_usd          = EXCLUDED.expected_total_usd,
                    expected_cost_mxn           = EXCLUDED.expected_cost_mxn,
                    expected_cost_usd           = EXCLUDED.expected_cost_usd,
                    paid_total                  = EXCLUDED.paid_total,
                    paid_total_mxn              = EXCLUDED.paid_total_mxn,
                    paid_total_usd              = EXCLUDED.paid_total_usd,
                    student_count               = EXCLUDED.student_count,
                    payment_count               = EXCLUDED.payment_count,
                    total                       = EXCLUDED.total,
                    cost                        = EXCLUDED.cost,
                    total_mxn                   = EXCLUDED.total_mxn,
                    total_usd                   = EXCLUDED.total_usd,
                    cost_mxn                    = EXCLUDED.cost_mxn,
                    cost_usd                    = EXCLUDED.cost_usd
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
                    allocated_amount, allocated_amount_mxn, allocated_amount_usd
                ) VALUES (
                    :payment_id, :cart_product_id, :etl_date,
                    :allocated_amount, :allocated_amount_mxn, :allocated_amount_usd
                )
                ON CONFLICT (payment_id, cart_product_id) DO UPDATE SET
                    etl_date             = EXCLUDED.etl_date,
                    allocated_amount     = EXCLUDED.allocated_amount,
                    allocated_amount_mxn = EXCLUDED.allocated_amount_mxn,
                    allocated_amount_usd = EXCLUDED.allocated_amount_usd
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
            allocation_rows_raw,
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
        all_rows = [*payment_rows_raw, *line_item_rows_raw, *allocation_rows_raw]
        all_dates = {dict(row)["created_at"].date() for row in all_rows}
        all_dates |= {d for row in all_rows if (d := coerce_to_date(dict(row).get("payment_date")))}
        ganados, perdidos, mantenidos = await calculate_business_status(all_lead_ids)

        # Fetch per-payment-date paid_total breakdown for all affected cart_products.
        # This lets us convert each payment slice at its own exchange rate so that
        # paid_total_mxn/usd on line items matches the per-rate conversion done on
        # report_payments, eliminating spurious negative uncategorized_revenue values.
        affected_cp_ids = [int(row["cart_product_id"]) for row in line_item_rows_raw]
        paid_total_date_rows: list[dict] = []
        if affected_cp_ids:
            async with SessionLocal() as source:
                result = await source.execute(
                    text(PAID_TOTAL_BY_DATE_QUERY).bindparams(
                        bindparam("cart_product_ids", expanding=True)
                    ),
                    {
                        "payment_status": PaymentStatus.APROBADO.value,
                        "cart_product_ids": affected_cp_ids,
                    },
                )
                paid_total_date_rows = [dict(row) for row in result.mappings().fetchall()]

        # Include any new payment dates from the breakdown rows in the prefetch set.
        all_dates |= {
            d for row in paid_total_date_rows if (d := coerce_to_date(row.get("payment_date")))
        }
        rates = await prefetch_rates(all_dates)

        paid_total_converted = await _build_paid_total_converted(paid_total_date_rows, rates)

        payment_rows = [
            await _transform_payment(dict(row), ganados, perdidos, mantenidos, rates)
            for row in payment_rows_raw
        ]
        line_item_rows = [
            await _transform_line_item(
                dict(row), ganados, perdidos, mantenidos, rates, paid_total_converted
            )
            for row in line_item_rows_raw
        ]
        allocation_rows = await _build_allocation_rows(allocation_rows_raw, rates)

        async with ReportingSessionLocal() as reporting:
            async with reporting.begin():
                await _delete_line_items(reporting, deleted_cart_product_ids, deleted_cart_ids)
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
