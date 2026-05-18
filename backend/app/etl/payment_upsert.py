from bisect import bisect_right
from datetime import datetime, timedelta, date, time
from sqlalchemy import text
import logging

from app.config import settings
from app.database import SessionLocal
from app.etl.exchange_rate_backfill import ensure_exchange_rates_for_range, run_historical_exchange_rate_backfill
from app.reporting.database import ReportingSessionLocal
from app.enums import PaymentStatus, BillingStatus, ProductType, BusinessStatus, ExamCategory
from app.services.por_asesor.product_grouping import canonical_exam_category, canonical_exam_name
from app.services.utils.currency_rates import normalize_country_key

logger = logging.getLogger(__name__)

# Maps normalised site key → ISO currency code.
# Mexico (MXN) has a 1:1 rate so it is omitted — handled as the default.
SITE_TO_CURRENCY: dict[str, str] = {
    "colombia": "COP",
    "peru":     "PEN",
}

EXTRACT_QUERY = """
    SELECT
        cp.id                               as cart_product_id,
        s.id                                as seller_id,
        CONCAT(s.name, ' ', s.lastName)     as seller_name,
        l.id                                as lead_id,
        l.name                              as school_name,
        l.site                              as site,
        z.name                              as zone_name,
        la.stateName                        as state_name,
        la.city                             as city,
        c.id                                as cart_id,
        c.billingStatus                     as billing_status,
        c.createdAt                         as created_at,
        c.bookCommission                    as book_commission,
        c.examCommission                    as exam_commission,
        pay.status                          as payment_status,
        pay.paymentDate                     as payment_date,
        COALESCE(pay.paymentDate, DATE(pay.createdAt)) as payment_day,
        p.id                                as product_id,
        p.productType                       as product_type,
        ec.name                             as exam_cat_name,
        ec.dateType                         as exam_date_type,
        cp.quantity                         as quantity,
        cp.total                            as total,
        cp.cost                             as cost,
        cp.discount                         as discount,
        COALESCE(addr.state_names, '')      as state_names,
        COALESCE(addr.city_names, '')       as city_names,
        COALESCE(alloc.has_paid_allocation, 0) as has_paid_allocation
    FROM payment pay
    JOIN cart c ON pay.cartId = c.id
    JOIN seller_lead sl ON c.sellerLeadId = sl.id
    JOIN seller s ON sl.sellerId = s.id
    JOIN `lead` l ON sl.leadId = l.id
    LEFT JOIN zone z ON l.zoneId = z.id
    LEFT JOIN (
        SELECT
            la1.leadId,
            COALESCE(
                NULLIF(
                    SUBSTRING_INDEX(
                        GROUP_CONCAT(
                            CASE WHEN la1.isFavorite = 1 THEN la1.stateName END
                            ORDER BY la1.id SEPARATOR '||'
                        ),
                        '||',
                        1
                    ),
                    ''
                ),
                SUBSTRING_INDEX(GROUP_CONCAT(la1.stateName ORDER BY la1.id SEPARATOR '||'), '||', 1)
            ) AS stateName,
            COALESCE(
                NULLIF(
                    SUBSTRING_INDEX(
                        GROUP_CONCAT(
                            CASE WHEN la1.isFavorite = 1 THEN la1.city END
                            ORDER BY la1.id SEPARATOR '||'
                        ),
                        '||',
                        1
                    ),
                    ''
                ),
                SUBSTRING_INDEX(GROUP_CONCAT(la1.city ORDER BY la1.id SEPARATOR '||'), '||', 1)
            ) AS city
        FROM lead_address la1
        WHERE la1.deletedAt IS NULL
        GROUP BY la1.leadId
    ) la ON la.leadId = l.id
    LEFT JOIN (
        SELECT
            la1.leadId,
            GROUP_CONCAT(DISTINCT la1.stateName ORDER BY la1.stateName SEPARATOR '||') AS state_names,
            GROUP_CONCAT(DISTINCT la1.city ORDER BY la1.city SEPARATOR '||') AS city_names
        FROM lead_address la1
        WHERE la1.deletedAt IS NULL
        GROUP BY la1.leadId
    ) addr ON addr.leadId = l.id
    JOIN cart_product cp ON cp.cartId = c.id
    LEFT JOIN (
        SELECT st.cartProductId AS cart_product_id, 1 AS has_paid_allocation
        FROM student st
        JOIN student_payments sp ON sp.student_id = st.id
        GROUP BY st.cartProductId
    ) alloc ON alloc.cart_product_id = cp.id
    JOIN product p ON cp.productId = p.id
    LEFT JOIN exam_cat ec ON p.examId = ec.id
    WHERE pay.updatedAt >= :since
    AND c.deletedAt IS NULL
    AND cp.deletedAt IS NULL
"""

DELETED_CART_PRODUCTS_QUERY = """
    SELECT cp.id
    FROM cart_product cp
    WHERE cp.deletedAt IS NOT NULL
    AND cp.deletedAt >= :since
"""

# ─────────────────────────────────────────────────────────────
# Main ETL job
# ─────────────────────────────────────────────────────────────

def _incremental_since(now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    return now - timedelta(hours=settings.payment_upsert_lookback_hours)


async def _has_successful_job_run(job_name: str) -> bool:
    async with ReportingSessionLocal() as session:
        row = (await session.execute(text("""
            SELECT 1
            FROM etl_meta
            WHERE job_name = :job_name
            AND status = 'success'
            LIMIT 1
        """), {"job_name": job_name})).fetchone()
    return row is not None


async def run_payment_upsert(*, since: datetime | None = None, job_name: str = "payment_upsert") -> None:
    start = datetime.now()
    since = since or await _resolve_since(job_name, start)
    logger.info(f"{job_name} started — payments updated since {since}")

    try:
        async with SessionLocal() as source:
            deleted_result = await source.execute(text(DELETED_CART_PRODUCTS_QUERY), {"since": since})
            deleted_cart_product_ids = [row[0] for row in deleted_result.fetchall()]
            result = await source.execute(text(EXTRACT_QUERY), {"since": since})
            raw_rows = result.mappings().fetchall()

        rows: list[dict] = []
        if raw_rows:
            conversion_dates = [_conversion_date(dict(r)) for r in raw_rows]
            history_end_date = date.today()
            await ensure_exchange_rates_for_range(min(conversion_dates), history_end_date)
            rate_history = await _load_rate_history(history_end_date)
            lead_ids = {r["lead_id"] for r in raw_rows}
            ganados, perdidos, mantenidos = await calculate_business_status(lead_ids)
            rows = [_transform(dict(r), ganados, perdidos, mantenidos, rate_history) for r in raw_rows]

        async with ReportingSessionLocal() as reporting:
            async with reporting.begin():
                await _delete_cart_products(reporting, deleted_cart_product_ids)
                if rows:
                    await _upsert(reporting, rows)

        if not raw_rows and not deleted_cart_product_ids:
            logger.info(f"{job_name} — no updated payments found")
            await _log(start, job_name, 0, "success")
            return

        logger.info(
            f"{job_name} complete — {len(rows)} rows upserted, "
            f"{len(deleted_cart_product_ids)} soft-deleted cart_products removed"
        )
        await _log(start, job_name, len(rows), "success")

    except Exception as e:
        logger.error(f"{job_name} failed: {e}")
        await _log(start, job_name, 0, "failed", error=str(e))
        raise


async def run_startup_payment_upsert() -> None:
    if await _has_successful_job_run("payment_upsert_startup"):
        logger.info("payment_upsert_startup skipped — startup backfill already completed")
        return

    earliest_date = await run_historical_exchange_rate_backfill()
    if earliest_date is None:
        logger.info("payment_upsert_startup skipped — source DB has no payment rows")
        await _log(datetime.now(), "payment_upsert_startup", 0, "success")
        return

    await run_payment_upsert(
        since=datetime.combine(earliest_date, time.min),
        job_name="payment_upsert_startup",
    )


async def _resolve_since(job_name: str, now: datetime) -> datetime:
    if job_name == "payment_upsert" and not await _has_successful_job_run("payment_upsert"):
        return settings.payment_upsert_initial_since
    return _incremental_since(now)


# ─────────────────────────────────────────────────────────────
# Transform
# ─────────────────────────────────────────────────────────────

def _transform(
    row: dict,
    ganados: set,
    perdidos: set,
    mantenidos: set,
    rate_history: dict[tuple[str, str], dict[str, list]],
) -> dict:
    created_at   = row["created_at"]
    payment_day  = _coerce_date(row.get("payment_day")) or _conversion_date(row)
    product_type = row["product_type"] or ""
    exam_cat_name = row["exam_cat_name"] or ""
    lead_id      = row["lead_id"]
    payment_status = row.get("payment_status") or ""
    normalized_payment_date = _coerce_date(row.get("payment_date"))

    site_key = normalize_country_key(row.get("site") or "")
    base_currency = _site_to_currency(site_key)
    conversion_date = _conversion_date(row)
    total    = float(row.get("total") or 0)
    cost     = float(row.get("cost")  or 0)

    return {
        **row,
        "etl_date":            datetime.now().date(),
        "year":                payment_day.year,
        "month":               payment_day.month,
        "payment_date":        normalized_payment_date,
        "payment_day":         payment_day,
        "base_currency":       base_currency,
        "state_names":         _split_multi_value(row.get("state_names")),
        "city_names":          _split_multi_value(row.get("city_names")),
        "include_in_product_breakdown": bool(row.get("has_paid_allocation")),
        "total_mxn":           round(_convert_amount(total, base_currency, "MXN", conversion_date, rate_history), 2),
        "cost_mxn":            round(_convert_amount(cost, base_currency, "MXN", conversion_date, rate_history), 2),
        "total_usd":           round(_convert_amount(total, base_currency, "USD", conversion_date, rate_history), 2),
        "cost_usd":            round(_convert_amount(cost, base_currency, "USD", conversion_date, rate_history), 2),
        "product_type":        product_type if product_type in [e.value for e in ProductType] else ProductType.UNCATEGORIZED.value,
        "exam_category":       canonical_exam_category(exam_cat_name) if exam_cat_name else ExamCategory.UNCATEGORIZED.value,
        "exam_canonical_name": canonical_exam_name(exam_cat_name) if exam_cat_name else "UNCATEGORIZED",
        "billing_status":      row.get("billing_status") or BillingStatus.UNCATEGORIZED.value,
        "payment_status":      payment_status if payment_status else PaymentStatus.UNCATEGORIZED.value,
        "business_status": (
            BusinessStatus.GANADO.value    if lead_id in ganados    else
            BusinessStatus.PERDIDO.value   if lead_id in perdidos   else
            BusinessStatus.MANTENIDO.value if lead_id in mantenidos else
            BusinessStatus.UNCATEGORIZED.value
        ),
        "is_active": payment_status != PaymentStatus.CANCELADO.value,
    }


def _site_to_currency(site_key: str) -> str:
    return SITE_TO_CURRENCY.get(site_key, "MXN")


def _conversion_date(row: dict) -> date:
    floor_date = settings.payment_upsert_initial_since.date()
    payment_date = row.get("payment_date")
    if payment_date:
        coerced_payment_date = _coerce_date(payment_date)
        if coerced_payment_date is not None and coerced_payment_date >= floor_date:
            return coerced_payment_date
    created_at = row["created_at"]
    coerced_created_at = _coerce_date(created_at)
    if coerced_created_at is None:
        raise ValueError(f"Unable to derive conversion date for cart_product_id={row.get('cart_product_id')}")
    return max(coerced_created_at, floor_date)


async def _load_rate_history(end_date: date) -> dict[tuple[str, str], dict[str, list]]:
    async with ReportingSessionLocal() as session:
        rows = (await session.execute(text("""
            SELECT date, from_currency, to_currency, rate
            FROM exchange_rates
            WHERE date <= :end_date
            ORDER BY from_currency ASC, to_currency ASC, date ASC
        """), {"end_date": end_date})).fetchall()

    history: dict[tuple[str, str], dict[str, list]] = {}
    for row in rows:
        key = (row.from_currency, row.to_currency)
        bucket = history.setdefault(key, {"dates": [], "rates": []})
        bucket["dates"].append(row.date)
        bucket["rates"].append(float(row.rate))
    return history


def _convert_amount(
    amount: float,
    from_currency: str,
    to_currency: str,
    effective_date: date,
    rate_history: dict[tuple[str, str], dict[str, list]],
) -> float:
    if amount == 0:
        return 0.0
    if from_currency == to_currency:
        return float(amount)

    key = (from_currency, to_currency)
    bucket = rate_history.get(key)
    if not bucket:
        raise ValueError(f"Missing exchange rate history for {from_currency}->{to_currency}")

    dates = bucket["dates"]
    index = bisect_right(dates, effective_date) - 1
    if index < 0:
        return float(amount) * float(bucket["rates"][-1])

    return float(amount) * float(bucket["rates"][index])


def _coerce_date(value: date | datetime | str | None) -> date | None:
    if value in (None, "", "0000-00-00", "0000-00-00 00:00:00"):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError:
        logger.warning("Invalid date value for payment upsert: %r", value)
        return None


def _split_multi_value(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [part for part in value if part]
    return [part for part in value.split("||") if part]


# ─────────────────────────────────────────────────────────────
# Upsert
# ─────────────────────────────────────────────────────────────

async def _upsert(session, rows: list[dict]) -> None:
    CHUNK_SIZE = 500
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i:i + CHUNK_SIZE]
        await session.execute(text("""
            INSERT INTO report_line_items (
                cart_product_id, etl_date, seller_id, seller_name,
                lead_id, school_name, site, zone_name, state_name, city,
                business_status, cart_id, billing_status, created_at,
                year, month, payment_status, payment_date, payment_day, product_id,
                product_type, exam_cat_name, exam_category, exam_canonical_name,
                exam_date_type, quantity, total, cost, discount,
                book_commission, exam_commission, base_currency,
                include_in_product_breakdown, state_names, city_names,
                total_mxn, cost_mxn, total_usd, cost_usd, is_active
            ) VALUES (
                :cart_product_id, :etl_date, :seller_id, :seller_name,
                :lead_id, :school_name, :site, :zone_name, :state_name, :city,
                :business_status, :cart_id, :billing_status, :created_at,
                :year, :month, :payment_status, :payment_date, :payment_day, :product_id,
                :product_type, :exam_cat_name, :exam_category, :exam_canonical_name,
                :exam_date_type, :quantity, :total, :cost, :discount,
                :book_commission, :exam_commission, :base_currency,
                :include_in_product_breakdown, :state_names, :city_names,
                :total_mxn, :cost_mxn, :total_usd, :cost_usd, :is_active
            )
            ON CONFLICT (cart_product_id) DO UPDATE SET
                etl_date            = EXCLUDED.etl_date,
                seller_name         = EXCLUDED.seller_name,
                school_name         = EXCLUDED.school_name,
                site                = EXCLUDED.site,
                zone_name           = EXCLUDED.zone_name,
                state_name          = EXCLUDED.state_name,
                city                = EXCLUDED.city,
                state_names         = EXCLUDED.state_names,
                city_names          = EXCLUDED.city_names,
                business_status     = EXCLUDED.business_status,
                billing_status      = EXCLUDED.billing_status,
                payment_status      = EXCLUDED.payment_status,
                payment_date        = EXCLUDED.payment_date,
                payment_day         = EXCLUDED.payment_day,
                is_active           = EXCLUDED.is_active,
                quantity            = EXCLUDED.quantity,
                total               = EXCLUDED.total,
                cost                = EXCLUDED.cost,
                discount            = EXCLUDED.discount,
                book_commission     = EXCLUDED.book_commission,
                exam_commission     = EXCLUDED.exam_commission,
                base_currency       = EXCLUDED.base_currency,
                include_in_product_breakdown = EXCLUDED.include_in_product_breakdown,
                total_mxn           = EXCLUDED.total_mxn,
                cost_mxn            = EXCLUDED.cost_mxn,
                total_usd           = EXCLUDED.total_usd,
                cost_usd            = EXCLUDED.cost_usd
        """), chunk)


async def _delete_cart_products(session, cart_product_ids: list[int]) -> None:
    if not cart_product_ids:
        return
    await session.execute(text("""
        DELETE FROM report_line_items
        WHERE cart_product_id = ANY(:cart_product_ids)
    """), {"cart_product_ids": cart_product_ids})


# ─────────────────────────────────────────────────────────────
# Business status calculation
# ─────────────────────────────────────────────────────────────

async def calculate_business_status(lead_ids: set[int]) -> tuple[set, set, set]:
    current_year = datetime.now().year

    async def approved_leads(year: int) -> set:
        async with SessionLocal() as source:
            result = await source.execute(text("""
                SELECT DISTINCT sl.leadId FROM cart c
                JOIN seller_lead sl ON c.sellerLeadId = sl.id
                WHERE YEAR(c.createdAt) = :year
                AND sl.leadId IN :lead_ids
                AND EXISTS (
                    SELECT 1 FROM payment pay
                    WHERE pay.cartId = c.id
                    AND pay.status = :status
                )
                AND c.deletedAt IS NULL
            """), {
                "year":     year,
                "lead_ids": tuple(lead_ids),
                "status":   PaymentStatus.APROBADO.value,
            })
            return {r[0] for r in result.fetchall()}

    current = await approved_leads(current_year)
    prior   = await approved_leads(current_year - 1)
    return current - prior, prior - current, current & prior


# ─────────────────────────────────────────────────────────────
# ETL run log
# ─────────────────────────────────────────────────────────────

async def _log(start: datetime, job_name: str, rows: int, status: str, error: str = None) -> None:
    async with ReportingSessionLocal() as session:
        async with session.begin():
            await session.execute(text("""
                INSERT INTO etl_meta (job_name, run_at, rows_processed, status, error, duration_seconds)
                VALUES (:job_name, :run_at, :rows, :status, :error, :duration)
            """), {
                "job_name": job_name,
                "run_at":   datetime.now(),
                "rows":     rows,
                "status":   status,
                "error":    error,
                "duration": (datetime.now() - start).seconds,
            })
