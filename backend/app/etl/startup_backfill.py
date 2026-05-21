from datetime import datetime, timedelta

from sqlalchemy import bindparam, text

from app.enums import ETLJobName
from app.reporting.database import ReportingSessionLocal
from app.etl.upsert import run_upsert

STARTUP_BACKFILL_FLOOR = datetime(2023, 1, 1, 0, 0, 0)
STARTUP_LOOKBACK = timedelta(hours=3)
PAYMENT_SYNC_JOB_NAMES = (
    ETLJobName.STARTUP_BACKFILL.value,
    ETLJobName.UPSERT.value,
)


async def get_startup_backfill_since(now: datetime | None = None) -> datetime | None:
    current_time = now or datetime.now()
    query = text("""
        SELECT run_at
        FROM etl_meta
        WHERE status = :status
        AND job_name IN :job_names
        ORDER BY run_at DESC
        LIMIT 1
    """).bindparams(bindparam("job_names", expanding=True))

    async with ReportingSessionLocal() as session:
        result = await session.execute(
            query,
            {
                "status": "success",
                "job_names": list(PAYMENT_SYNC_JOB_NAMES),
            },
        )
        latest_success = result.scalar_one_or_none()

    if latest_success is None:
        return STARTUP_BACKFILL_FLOOR

    if latest_success > current_time - STARTUP_LOOKBACK:
        return None

    return latest_success


async def run_startup_backfill_if_needed(now: datetime | None = None) -> None:
    since = await get_startup_backfill_since(now=now)
    if since is None:
        return
    await run_upsert(since=since, job_name=ETLJobName.STARTUP_BACKFILL)
