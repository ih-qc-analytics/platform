from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from app.config import settings
from app.etl.payment_upsert import run_payment_upsert
from app.etl.dimensional_refresh import run_dimensional_refresh

scheduler = AsyncIOScheduler()


def start_etl_scheduler():
    scheduler.add_job(
        run_payment_upsert,
        "interval",
        hours=settings.payment_upsert_lookback_hours,
        next_run_time=datetime.now(),
    )
    scheduler.add_job(run_dimensional_refresh, "cron",     hour=3, minute=0)
    scheduler.start()
