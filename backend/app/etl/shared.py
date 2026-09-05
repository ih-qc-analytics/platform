from datetime import date, datetime, timedelta
import logging

from sqlalchemy import bindparam, text

from app.database import SessionLocal
from app.etl.frankfurter import FXRateFetchError, fetch_frankfurter_rate
from app.etl.rate_defaults import FALLBACK_RATES
from app.enums import BusinessStatus, ETLJobName, PaymentStatus
from app.reporting.database import ReportingSessionLocal

logger = logging.getLogger(__name__)

# Job names that advance the payment sync watermark. Both write the same rows,
# so either one's success marks how far report_payments has been brought up to date.
PAYMENT_SYNC_JOB_NAMES = ("startup_backfill", "upsert")

# etl_meta.run_at is stamped at completion, so resume slightly before it — anything
# updated while the previous run was executing would otherwise be skipped. Overlap
# is free: every write is an upsert keyed on the source ID.
SYNC_OVERLAP = timedelta(minutes=15)
# Used when etl_meta has no successful run yet (fresh DB, or every run so far failed).
SYNC_FALLBACK = timedelta(hours=3)
# Ceiling on catch-up after a long outage. The extract path builds unpaginated IN
# lists over every affected cart, so an unbounded window can exhaust memory.
SYNC_MAX_CATCHUP = timedelta(days=30)

LATEST_SYNC_QUERY = text("""
    SELECT run_at
    FROM etl_meta
    WHERE status = :status
    AND job_name IN :job_names
    ORDER BY run_at DESC
    LIMIT 1
""").bindparams(bindparam("job_names", expanding=True))


SOURCE_CLOCK_OFFSET_QUERY = text(
    "SELECT TIMESTAMPDIFF(SECOND, NOW(), UTC_TIMESTAMP()) AS offset_seconds"
)


async def get_source_clock_offset() -> timedelta:
    """How far the source server's wall clock sits behind the app's.

    The windowed columns (payment.updatedAt, cart.deletedAt, ...) are DATETIME(6):
    no timezone, written in the source server's local time. The app runs in UTC, so
    a Python-derived bound is compared against values on a different clock. In
    production the source is UTC-6, which put every incremental window ~6 hours in
    the future — `updatedAt > :since` matched nothing, and every scheduled run
    reported 0 rows while the data quietly went stale.

    Measured per run rather than configured, so a DST shift on the source host is
    picked up on the next pass instead of silently reopening the same gap.
    """
    async with SessionLocal() as source:
        row = (await source.execute(SOURCE_CLOCK_OFFSET_QUERY)).one()
    return timedelta(seconds=int(row.offset_seconds))


async def to_source_time(moment: datetime, offset: timedelta | None = None) -> datetime:
    """Translate an app-clock timestamp into the source server's local clock."""
    return moment - (offset if offset is not None else await get_source_clock_offset())


async def get_incremental_since(now: datetime | None = None) -> datetime:
    """Resume the payment upsert from the last successful sync.

    Previously the recurring job always used `now - 3h`, matching the scheduler
    interval. Any failed run therefore left a permanent 3-hour hole: the next run
    looked back only 3h from *itself*, never revisiting the window it missed.
    """
    current_time = now or datetime.now()
    async with ReportingSessionLocal() as session:
        result = await session.execute(
            LATEST_SYNC_QUERY,
            {"status": "success", "job_names": list(PAYMENT_SYNC_JOB_NAMES)},
        )
        latest_success = result.scalar_one_or_none()

    if latest_success is None:
        return current_time - SYNC_FALLBACK
    return max(latest_success - SYNC_OVERLAP, current_time - SYNC_MAX_CATCHUP)


SITE_CURRENCY = {
    "mexico": "MXN",
    "colombia": "COP",
    "peru": "PEN",
}
UNKNOWN_CURRENCY = "UNKNOWN"

LEAD_ADDRESS_SUBQUERY = """
    LEFT JOIN (
        SELECT
            leadId,
            COALESCE(
                NULLIF(
                    SUBSTRING_INDEX(
                        GROUP_CONCAT(
                            CASE WHEN isFavorite = 1 THEN stateName END
                            ORDER BY id SEPARATOR '||'
                        ),
                        '||',
                        1
                    ),
                    ''
                ),
                SUBSTRING_INDEX(GROUP_CONCAT(stateName ORDER BY id SEPARATOR '||'), '||', 1)
            ) AS stateName,
            COALESCE(
                NULLIF(
                    SUBSTRING_INDEX(
                        GROUP_CONCAT(
                            CASE WHEN isFavorite = 1 THEN city END
                            ORDER BY id SEPARATOR '||'
                        ),
                        '||',
                        1
                    ),
                    ''
                ),
                SUBSTRING_INDEX(GROUP_CONCAT(city ORDER BY id SEPARATOR '||'), '||', 1)
            ) AS city,
            GROUP_CONCAT(DISTINCT stateName ORDER BY stateName SEPARATOR '||') AS state_names,
            GROUP_CONCAT(DISTINCT city ORDER BY city SEPARATOR '||') AS city_names
        FROM lead_address
        WHERE deletedAt IS NULL
        GROUP BY leadId
    ) la ON la.leadId = l.id
"""


def split_multi_value(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [part for part in value if part]
    return [part for part in value.split("||") if part]


def coerce_to_date(value, fallback: date | None = None) -> date | None:
    """
    Coerce any date-like value to a plain datetime.date.

    datetime is checked before date because datetime subclasses date — without
    this, a datetime object passes the isinstance(value, date) branch and is
    returned as-is.  That breaks exchange-rate dict lookups because
    date(2024,1,15) and datetime(2024,1,15) have different hashes and are not
    equal as mapping keys, causing silent cache misses on every ETL run.
    """
    if value is None:
        return fallback
    if isinstance(value, datetime):  # must come before date check
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return fallback


def extract_dimensions(row: dict) -> dict:
    created_at = row["created_at"]
    return {
        "seller_id": row["seller_id"],
        "seller_name": row["seller_name"],
        "lead_id": row["lead_id"],
        "school_name": row.get("school_name"),
        "site": row.get("site"),
        "zone_name": row.get("zone_name"),
        "state_name": row.get("state_name"),
        "city": row.get("city"),
        "all_states": split_multi_value(row.get("all_states")),
        "all_cities": split_multi_value(row.get("all_cities")),
        "state_names": split_multi_value(row.get("all_states")),
        "city_names": split_multi_value(row.get("all_cities")),
        "year": created_at.year,
        "month": created_at.month,
        "created_at": created_at,
        "etl_date": datetime.now().date(),
        "base_currency": SITE_CURRENCY.get(row.get("site", ""), UNKNOWN_CURRENCY),
    }


async def calculate_business_status(lead_ids: set[int]) -> tuple[set[int], set[int], set[int]]:
    if not lead_ids:
        return set(), set(), set()

    current_year = datetime.now().year

    async def approved_leads(year: int) -> set[int]:
        query = text("""
            SELECT DISTINCT sl.leadId
            FROM cart c
            JOIN seller_lead sl ON c.sellerLeadId = sl.id
            WHERE YEAR(c.createdAt) = :year
            AND sl.leadId IN :lead_ids
            AND EXISTS (
                SELECT 1
                FROM payment pay
                WHERE pay.cartId = c.id
                AND pay.status = :status
            )
            AND c.deletedAt IS NULL
        """).bindparams(bindparam("lead_ids", expanding=True))
        async with SessionLocal() as source:
            result = await source.execute(
                query,
                {
                    "year": year,
                    "lead_ids": sorted(lead_ids),
                    "status": PaymentStatus.APROBADO.value,
                },
            )
            return {int(row[0]) for row in result.fetchall()}

    current = await approved_leads(current_year)
    prior = await approved_leads(current_year - 1)
    return current - prior, prior - current, current & prior


def resolve_business_status(
    lead_id: int, ganados: set[int], perdidos: set[int], mantenidos: set[int]
) -> str:
    if lead_id in ganados:
        return BusinessStatus.GANADO.value
    if lead_id in perdidos:
        return BusinessStatus.PERDIDO.value
    if lead_id in mantenidos:
        return BusinessStatus.MANTENIDO.value
    return BusinessStatus.UNCATEGORIZED.value


async def prefetch_rates(dates: set[date]) -> dict[tuple[date, str, str], float]:
    if not dates:
        return {}
    async with ReportingSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT date, from_currency, to_currency, rate
                FROM exchange_rates
                WHERE date = ANY(:dates)
            """),
            {"dates": list(dates)},
        )
        return {
            (row.date, row.from_currency, row.to_currency): float(row.rate)
            for row in result.fetchall()
        }


async def fetch_live_rate(rate_date: date, from_cur: str, to_cur: str) -> float:
    try:
        provider_date, rate = await fetch_frankfurter_rate(from_cur, to_cur, rate_date)
    except FXRateFetchError as exc:
        approx = FALLBACK_RATES.get((from_cur, to_cur), 9999.0)
        logger.error(
            "APPROX_FX_RATE: could not fetch %s/%s on %s — using approximate rate %.6f. "
            "Manual correction required in exchange_rates table. Original error: %s",
            from_cur,
            to_cur,
            rate_date.isoformat(),
            approx,
            exc,
        )
        async with ReportingSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    text("""
                        INSERT INTO exchange_rates (date, from_currency, to_currency, rate)
                        VALUES (:date, :from_cur, :to_cur, :rate)
                        ON CONFLICT (date, from_currency, to_currency) DO NOTHING
                    """),
                    {"date": rate_date, "from_cur": from_cur, "to_cur": to_cur, "rate": approx},
                )
        return approx

    if provider_date != rate_date:
        logger.warning(
            "Frankfurter returned %s for %s/%s requested on %s; caching rate under requested date.",
            provider_date.isoformat(),
            from_cur,
            to_cur,
            rate_date.isoformat(),
        )

    async with ReportingSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("""
                    INSERT INTO exchange_rates (date, from_currency, to_currency, rate)
                    VALUES (:date, :from_cur, :to_cur, :rate)
                    ON CONFLICT (date, from_currency, to_currency) DO NOTHING
                """),
                {"date": rate_date, "from_cur": from_cur, "to_cur": to_cur, "rate": rate},
            )
    return rate


async def get_rate(
    rate_date: date, from_cur: str, to_cur: str, rates: dict[tuple[date, str, str], float]
) -> float:
    if from_cur == to_cur:
        return 1.0
    exact_rate = rates.get((rate_date, from_cur, to_cur))
    if exact_rate is not None:
        return exact_rate
    fetched_rate = await fetch_live_rate(rate_date, from_cur, to_cur)
    rates[(rate_date, from_cur, to_cur)] = fetched_rate
    return fetched_rate


async def convert_currency(
    amount: float,
    site: str,
    rate_date: date,
    rates: dict[tuple[date, str, str], float],
) -> tuple[float | None, float | None]:
    base_currency = SITE_CURRENCY.get(site, UNKNOWN_CURRENCY)
    if base_currency == UNKNOWN_CURRENCY:
        return None, None
    rate_to_mxn = (
        await get_rate(rate_date, base_currency, "MXN", rates) if base_currency != "MXN" else 1.0
    )
    rate_to_usd = await get_rate(rate_date, base_currency, "USD", rates)
    return round(amount * rate_to_mxn, 2), round(amount * rate_to_usd, 2)


async def log_etl_run(
    job_name: ETLJobName,
    rows: int,
    status: str,
    start: datetime,
    error: str | None = None,
) -> None:
    async with ReportingSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("""
                    INSERT INTO etl_meta (job_name, run_at, rows_processed, status, error, duration_seconds)
                    VALUES (:job_name, :run_at, :rows, :status, :error, :duration)
                """),
                {
                    "job_name": job_name.value,
                    "run_at": datetime.now(),
                    "rows": rows,
                    "status": status,
                    "error": error,
                    "duration": int((datetime.now() - start).total_seconds()),
                },
            )
