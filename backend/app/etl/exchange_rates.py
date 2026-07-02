from datetime import date

from app.etl.exchange_rate_backfill import ensure_exchange_rates_for_range


async def fetch_and_store_rates() -> dict:
    today = date.today()
    await ensure_exchange_rates_for_range(today, today)
    return {"date": today.isoformat()}
