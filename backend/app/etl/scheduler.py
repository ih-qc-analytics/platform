from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.etl.payment_upsert import run_payment_upsert
from app.etl.dimensional_refresh import run_dimensional_refresh

scheduler = AsyncIOScheduler()


def start_etl_scheduler():
    scheduler.add_job(run_payment_upsert,     "interval", hours=3)
    scheduler.add_job(run_dimensional_refresh, "cron",     hour=3, minute=0)
    scheduler.start()
