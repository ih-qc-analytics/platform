from datetime import datetime, timedelta, date
from sqlalchemy import text
import httpx
import logging

from app.database import SessionLocal
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
        p.id                                as product_id,
        p.productType                       as product_type,
        ec.name                             as exam_cat_name,
        ec.dateType                         as exam_date_type,
        cp.quantity                         as quantity,
        cp.total                            as total,
        cp.cost                             as cost,
        cp.discount                         as discount
    FROM payment pay
    JOIN cart c ON pay.cartId = c.id
    JOIN seller_lead sl ON c.sellerLeadId = sl.id
    JOIN seller s ON sl.sellerId = s.id
    JOIN `lead` l ON sl.leadId = l.id
    LEFT JOIN zone z ON l.zoneId = z.id
    LEFT JOIN (
        SELECT la1.leadId, la1.stateName, la1.city
        FROM lead_address la1
        WHERE la1.id = (
            SELECT MIN(id) FROM lead_address la2
            WHERE la2.leadId = la1.leadId
            AND la2.deletedAt IS NULL
        )
    ) la ON la.leadId = l.id
    JOIN cart_product cp ON cp.cartId = c.id
    JOIN product p ON cp.productId = p.id
    LEFT JOIN exam_cat ec ON p.examId = ec.id
    WHERE pay.updatedAt > :since
    AND c.deletedAt IS NULL
"""


# ─────────────────────────────────────────────────────────────
# Exchange rate helpers
# ─────────────────────────────────────────────────────────────

async def _get_mxn_rates() -> dict[str, float]:
    """
    Returns a map of {normalised_site_key: mxn_conversion_rate}.
    Mexico is always 1.0. Other currencies are fetched from the
    reporting DB's exchange_rates table (today's row) or from
    Frankfurter API if not yet stored.

    Rate semantics: total_mxn = total_raw * rate
      e.g. rate for COP = 1 / (COP per 1 MXN)
    """
    today = date.today()
    rates: dict[str, float] = {"mexico": 1.0}

    # Try reporting DB first
    async with ReportingSessionLocal() as session:
        rows = (await session.execute(text("""
            SELECT from_currency, rate
            FROM exchange_rates
            WHERE date = :today AND to_currency = 'MXN'
        """), {"today": today})).fetchall()

    db_rates = {r.from_currency: float(r.rate) for r in rows}

    missing_currencies = [
        currency for site, currency in SITE_TO_CURRENCY.items()
        if currency not in db_rates
    ]

    if missing_currencies:
        db_rates.update(await _fetch_and_store_rates(today, missing_currencies))

    for site, currency in SITE_TO_CURRENCY.items():
        if currency in db_rates:
            rates[site] = db_rates[currency]

    return rates


async def _fetch_and_store_rates(for_date: date, currencies: list[str]) -> dict[str, float]:
    """Fetch from Frankfurter and insert into exchange_rates. Returns {currency: mxn_rate}."""
    quotes = ",".join(currencies)
    url = f"https://api.frankfurter.app/latest?base=MXN&symbols={quotes}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Frankfurter fetch failed: {e} — rates defaulting to 1.0 for {currencies}")
        return {c: 1.0 for c in currencies}

    # data["rates"] is {currency: units_per_1_MXN}
    raw = data.get("rates", {})
    result: dict[str, float] = {}
    inserts = []
    for currency in currencies:
        if currency in raw:
            mxn_rate = 1.0 / float(raw[currency])   # COP→MXN conversion factor
            result[currency] = mxn_rate
            inserts.append({
                "date":          for_date,
                "from_currency": currency,
                "to_currency":   "MXN",
                "rate":          mxn_rate,
            })

    if inserts:
        async with ReportingSessionLocal() as session:
            async with session.begin():
                for ins in inserts:
                    await session.execute(text("""
                        INSERT INTO exchange_rates (date, from_currency, to_currency, rate)
                        VALUES (:date, :from_currency, :to_currency, :rate)
                        ON CONFLICT (date, from_currency, to_currency) DO NOTHING
                    """), ins)

    return result


# ─────────────────────────────────────────────────────────────
# Main ETL job
# ─────────────────────────────────────────────────────────────

async def run_payment_upsert() -> None:
    start = datetime.now()
    since = datetime.now() - timedelta(hours=3)
    logger.info(f"Job 1 started — payments updated since {since}")

    try:
        async with SessionLocal() as source:
            result = await source.execute(text(EXTRACT_QUERY), {"since": since})
            raw_rows = result.mappings().fetchall()

        if not raw_rows:
            logger.info("Job 1 — no updated payments found")
            await _log(start, "payment_upsert", 0, "success")
            return

        mxn_rates = await _get_mxn_rates()
        lead_ids = {r["lead_id"] for r in raw_rows}
        ganados, perdidos, mantenidos = await calculate_business_status(lead_ids)
        rows = [_transform(dict(r), ganados, perdidos, mantenidos, mxn_rates) for r in raw_rows]

        async with ReportingSessionLocal() as reporting:
            async with reporting.begin():
                await _upsert(reporting, rows)

        logger.info(f"Job 1 complete — {len(rows)} rows upserted")
        await _log(start, "payment_upsert", len(rows), "success")

    except Exception as e:
        logger.error(f"Job 1 failed: {e}")
        await _log(start, "payment_upsert", 0, "failed", error=str(e))
        raise


# ─────────────────────────────────────────────────────────────
# Transform
# ─────────────────────────────────────────────────────────────

def _transform(
    row: dict,
    ganados: set,
    perdidos: set,
    mantenidos: set,
    mxn_rates: dict[str, float],
) -> dict:
    created_at   = row["created_at"]
    product_type = row["product_type"] or ""
    exam_cat_name = row["exam_cat_name"] or ""
    lead_id      = row["lead_id"]
    payment_status = row.get("payment_status") or ""

    site_key = normalize_country_key(row.get("site") or "")
    rate     = mxn_rates.get(site_key, 1.0)
    total    = float(row.get("total") or 0)
    cost     = float(row.get("cost")  or 0)

    return {
        **row,
        "etl_date":            datetime.now().date(),
        "year":                created_at.year,
        "month":               created_at.month,
        "base_currency":       _site_to_currency(site_key),
        "total_mxn":           round(total * rate, 2),
        "cost_mxn":            round(cost  * rate, 2),
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
                year, month, payment_status, payment_date, product_id,
                product_type, exam_cat_name, exam_category, exam_canonical_name,
                exam_date_type, quantity, total, cost, discount,
                book_commission, exam_commission, base_currency, total_mxn, cost_mxn, is_active
            ) VALUES (
                :cart_product_id, :etl_date, :seller_id, :seller_name,
                :lead_id, :school_name, :site, :zone_name, :state_name, :city,
                :business_status, :cart_id, :billing_status, :created_at,
                :year, :month, :payment_status, :payment_date, :product_id,
                :product_type, :exam_cat_name, :exam_category, :exam_canonical_name,
                :exam_date_type, :quantity, :total, :cost, :discount,
                :book_commission, :exam_commission, :base_currency, :total_mxn, :cost_mxn, :is_active
            )
            ON CONFLICT (cart_product_id) DO UPDATE SET
                etl_date            = EXCLUDED.etl_date,
                seller_name         = EXCLUDED.seller_name,
                school_name         = EXCLUDED.school_name,
                site                = EXCLUDED.site,
                zone_name           = EXCLUDED.zone_name,
                state_name          = EXCLUDED.state_name,
                city                = EXCLUDED.city,
                business_status     = EXCLUDED.business_status,
                billing_status      = EXCLUDED.billing_status,
                payment_status      = EXCLUDED.payment_status,
                payment_date        = EXCLUDED.payment_date,
                is_active           = EXCLUDED.is_active,
                quantity            = EXCLUDED.quantity,
                total               = EXCLUDED.total,
                cost                = EXCLUDED.cost,
                discount            = EXCLUDED.discount,
                book_commission     = EXCLUDED.book_commission,
                exam_commission     = EXCLUDED.exam_commission,
                base_currency       = EXCLUDED.base_currency,
                total_mxn           = EXCLUDED.total_mxn,
                cost_mxn            = EXCLUDED.cost_mxn
        """), chunk)


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
