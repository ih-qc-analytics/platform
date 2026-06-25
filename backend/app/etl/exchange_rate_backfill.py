from __future__ import annotations

import asyncio
from datetime import date, datetime

import httpx
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.etl.frankfurter import FXRateFetchError, fetch_frankfurter_time_series
from app.etl.retry import async_retry
from app.reporting.database import ReportingSessionLocal
import logging

logger = logging.getLogger(__name__)

RATE_TARGETS = ("MXN", "USD")
SUPPORTED_BASE_CURRENCIES = ("MXN", "COP", "PEN")

EARLIEST_RATE_DATE_QUERY = """
    SELECT MIN(COALESCE(pay.paymentDate, DATE(c.createdAt))) AS earliest_date
    FROM payment pay
    JOIN cart c ON pay.cartId = c.id
    WHERE c.deletedAt IS NULL
"""


async def get_source_earliest_rate_date() -> date | None:
    async with SessionLocal() as source:
        row = (await source.execute(text(EARLIEST_RATE_DATE_QUERY))).fetchone()
    earliest_date = _coerce_date(row.earliest_date) if row else None
    if earliest_date is None:
        return None
    return max(earliest_date, settings.payment_upsert_initial_since.date())


async def ensure_exchange_rates_for_range(
    start_date: date,
    end_date: date | None = None,
) -> None:
    start_date = _coerce_date(start_date)
    end_date = end_date or date.today()
    if start_date > end_date:
        return

    missing_quotes_by_base = await _missing_quotes_by_base_for_range(start_date, end_date)
    if not missing_quotes_by_base:
        return

    all_rows: list[dict[str, object]] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for base_currency, quotes in missing_quotes_by_base.items():
            if not quotes:
                continue
            try:
                rows = await async_retry(
                    lambda b=base_currency, q=quotes: fetch_frankfurter_time_series(
                        b, q, start_date, end_date, client=client
                    ),
                    attempts=3,
                    exceptions=(FXRateFetchError,),
                )
                all_rows.extend(rows)
            except FXRateFetchError:
                logger.error(
                    "MISSING_FX_RATES: failed to fetch %s → %s for %s–%s after 3 attempts. "
                    "Approximate fallback rates will be used during upsert.",
                    base_currency,
                    quotes,
                    start_date,
                    end_date,
                )

    if all_rows:
        await _upsert_exchange_rates(all_rows)


async def run_historical_exchange_rate_backfill() -> date | None:
    earliest_date = await get_source_earliest_rate_date()
    if earliest_date is None:
        return None

    await ensure_exchange_rates_for_range(earliest_date, date.today())
    return earliest_date


async def _missing_quotes_by_base_for_range(
    start_date: date, end_date: date
) -> dict[str, list[str]]:
    total_days = (end_date - start_date).days + 1
    expected_pairs = [
        (base_currency, target_currency)
        for base_currency in SUPPORTED_BASE_CURRENCIES
        for target_currency in RATE_TARGETS
        if target_currency != base_currency
    ]

    async with ReportingSessionLocal() as session:
        rows = (
            await session.execute(
                text("""
            SELECT from_currency, to_currency, COUNT(DISTINCT date) AS day_count
            FROM exchange_rates
            WHERE date BETWEEN :start_date AND :end_date
            GROUP BY from_currency, to_currency
        """),
                {"start_date": start_date, "end_date": end_date},
            )
        ).fetchall()

    existing_pairs = {(row.from_currency, row.to_currency): int(row.day_count) for row in rows}
    missing_pairs: dict[str, list[str]] = {}
    for base_currency, target_currency in expected_pairs:
        if existing_pairs.get((base_currency, target_currency), 0) < total_days:
            missing_pairs.setdefault(base_currency, []).append(target_currency)
    return missing_pairs


async def _upsert_exchange_rates(rows: list[dict[str, object]]) -> None:
    async with ReportingSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("""
                    INSERT INTO exchange_rates (date, from_currency, to_currency, rate)
                    VALUES (:date, :from_currency, :to_currency, :rate)
                    ON CONFLICT (date, from_currency, to_currency) DO UPDATE
                    SET rate = EXCLUDED.rate
                """),
                rows,
            )


def _main() -> None:
    asyncio.run(run_historical_exchange_rate_backfill())


def _coerce_date(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        floor_date = settings.payment_upsert_initial_since.date()
        logger.warning(
            "Malformed date value encountered: %r. Error: %s. Falling back to %s.",
            value,
            e,
            floor_date.isoformat(),
        )
        return floor_date


if __name__ == "__main__":
    _main()
