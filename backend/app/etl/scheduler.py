from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.etl.dimensional_refresh import run_dimensional_refresh
from app.etl.exchange_rates import fetch_and_store_rates
from app.etl.upsert import run_upsert
from app.enums import ETLJobName

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    scheduler.add_job(fetch_and_store_rates, "cron", hour=2, minute=0)
    scheduler.add_job(
        run_upsert,
        "interval",
        hours=settings.payment_upsert_lookback_hours,
        kwargs={"job_name": ETLJobName.UPSERT},
    )
    scheduler.add_job(run_dimensional_refresh, "cron", hour=3, minute=0)
    scheduler.start()
