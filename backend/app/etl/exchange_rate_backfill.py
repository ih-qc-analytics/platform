from __future__ import annotations

import asyncio
from datetime import date, datetime

import httpx
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.reporting.database import ReportingSessionLocal
import logging

logger = logging.getLogger(__name__)

FRANKFURTER_RATES_URL = "https://api.frankfurter.dev/v2/rates"
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

    target_date = date.today()
    missing_pairs = await _missing_pairs_for_date(target_date)
    if not missing_pairs:
        return

    async with httpx.AsyncClient(timeout=30) as client:
        for base_currency, quotes in missing_pairs.items():
            if not quotes:
                continue

            rows = await _fetch_daily_rates(
                client,
                base_currency=base_currency,
                for_date=target_date,
                quotes=quotes,
            )
            if rows:
                await _upsert_exchange_rates(rows)


async def run_historical_exchange_rate_backfill() -> date | None:
    earliest_date = await get_source_earliest_rate_date()
    if earliest_date is None:
        return None

    await ensure_exchange_rates_for_range(earliest_date, date.today())
    return earliest_date


async def _missing_pairs_for_date(for_date: date) -> dict[str, list[str]]:
    expected_pairs = [
        (base_currency, target_currency)
        for base_currency in SUPPORTED_BASE_CURRENCIES
        for target_currency in RATE_TARGETS
        if target_currency != base_currency
    ]

    async with ReportingSessionLocal() as session:
        rows = (await session.execute(text("""
            SELECT from_currency, to_currency
            FROM exchange_rates
            WHERE date = :for_date
        """), {"for_date": for_date})).fetchall()

    existing_pairs = {(row.from_currency, row.to_currency) for row in rows}
    missing_pairs: dict[str, list[str]] = {}
    for base_currency, target_currency in expected_pairs:
        if (base_currency, target_currency) not in existing_pairs:
            missing_pairs.setdefault(base_currency, []).append(target_currency)
    return missing_pairs


async def _fetch_daily_rates(
    client: httpx.AsyncClient,
    *,
    base_currency: str,
    for_date: date,
    quotes: list[str],
) -> list[dict[str, object]]:
    response = await client.get(
        FRANKFURTER_RATES_URL,
        params={
            "base": base_currency,
            "quotes": ",".join(quotes),
        },
    )
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, list):
        raise ValueError("Unexpected Frankfurter response shape for daily rates")

    rows: list[dict[str, object]] = []
    for item in data:
        rows.append(
            {
                "date": for_date,
                "from_currency": item["base"],
                "to_currency": item["quote"],
                "rate": float(item["rate"]),
            }
        )
    return rows


async def _upsert_exchange_rates(rows: list[dict[str, object]]) -> None:
    async with ReportingSessionLocal() as session:
        async with session.begin():
            for row in rows:
                await session.execute(
                    text("""
                        INSERT INTO exchange_rates (date, from_currency, to_currency, rate)
                        VALUES (:date, :from_currency, :to_currency, :rate)
                        ON CONFLICT (date, from_currency, to_currency) DO UPDATE
                        SET rate = EXCLUDED.rate
                    """),
                    row,
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
