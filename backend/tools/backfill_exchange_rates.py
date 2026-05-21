import asyncio
from datetime import date
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.etl.exchange_rate_backfill import ensure_exchange_rates_for_range

BACKFILL_START_DATE = date(2023, 1, 1)


async def _run() -> None:
    await ensure_exchange_rates_for_range(BACKFILL_START_DATE, date.today())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
