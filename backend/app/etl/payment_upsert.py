from app.enums import ETLJobName
from app.etl.upsert import run_upsert


async def run_payment_upsert(*, since=None, job_name: ETLJobName = ETLJobName.UPSERT) -> None:
    await run_upsert(since=since, job_name=job_name)


async def run_startup_payment_upsert() -> None:
    await run_upsert(job_name=ETLJobName.STARTUP_BACKFILL)
