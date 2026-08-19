"""Load PRODUCTION data into the LOCAL dev reporting DB.

app/config.py derives both databases from a single ENVIRONMENT var, so there is
no supported "prod source + local reporting" combination. This creates one by
setting ENVIRONMENT=dev and injecting PROD_DB_* into the DEV_DB_* slots before
app.config is imported. backend/.env is never modified.

Usage:  make backfill-dev-db
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
TABLES = "report_payments, report_line_items, report_payment_allocations"


def die(reason: str) -> None:
    print(f"\nABORTED — {reason}\n", file=sys.stderr)
    sys.exit(1)


# ── Point the ETL at prod source + local reporting ───────────────────────────
# load_dotenv defaults to override=False, so the later calls in app/config.py
# and alembic/env.py leave what we set here alone.
load_dotenv(BACKEND_DIR / ".env")
os.environ["ENVIRONMENT"] = "dev"
for key in ("USER", "PASS", "HOST", "PORT", "NAME"):
    os.environ[f"DEV_DB_{key}"] = os.environ.get(f"PROD_DB_{key}", "")

# The only safety check: we must be reading production and writing localhost.
# It runs before the app imports because app/reporting/database.py builds its
# engine at import time.
SOURCE = os.environ["DEV_DB_HOST"]
TARGET = (os.getenv("DEV_REPORTING_DB_HOST") or "").lower()

if not SOURCE:
    die("PROD_DB_* is not set in backend/.env — nothing to read from.")
if SOURCE.lower() in LOCAL_HOSTS:
    die(f"source is {SOURCE}, not production. Check PROD_DB_HOST in backend/.env.")
if TARGET not in LOCAL_HOSTS:
    die(
        f"target is {TARGET or '(unset)'}, not local. This only ever writes to the "
        "local Supabase Postgres — expected DEV_REPORTING_DB_HOST=localhost, port 54322."
    )

from sqlalchemy import text  # noqa: E402 — must follow the env rewiring above

from app.config import settings  # noqa: E402
from app.enums import ETLJobName  # noqa: E402
from app.etl.exchange_rate_backfill import ensure_exchange_rates_for_range  # noqa: E402
from app.etl.upsert import run_upsert  # noqa: E402
from app.database import engine as source_engine  # noqa: E402
from app.reporting.database import ReportingSessionLocal, reporting_engine  # noqa: E402


async def main() -> None:
    since = settings.payment_upsert_initial_since
    target = (
        f"{settings.reporting_db_host}:{settings.reporting_db_port}/{settings.reporting_db_name}"
    )

    print(f"\n  read  {SOURCE}:{settings.port}/{settings.dbname}  [PROD, read-only]")
    print(f"  write {target}  [LOCAL]")
    print(f"  since {since.isoformat()}\n")
    print(f"  {TABLES}")
    print("  will be TRUNCATED and reloaded. The full history loads in one pass —")
    print("  expect several minutes and multi-GB memory use.")
    try:
        answer = input("\nProceed? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        sys.exit("Aborted.")

    started = time.monotonic()

    try:
        print("\n[1/4] Migrating…")
        alembic = [sys.executable, "-m", "alembic", "upgrade", "head"]
        if subprocess.run(alembic, cwd=BACKEND_DIR).returncode:
            die("migrations failed. Is the local Supabase running? Try: supabase start")

        print("\n[2/4] Truncating report tables…")
        async with ReportingSessionLocal() as session:
            await session.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY"))
            await session.commit()

        # Rates must land first: the upsert freezes *_mxn/*_usd at write time, and a
        # missing rate makes it persist a fallback approximation permanently.
        print("\n[3/4] Backfilling exchange rates…")
        await ensure_exchange_rates_for_range(since.date())

        print("\n[4/4] Upserting payments (one transaction, no output until done)…")
        counts = await run_upsert(since=since, job_name=ETLJobName.UPSERT)

        summary = "  ".join(f"{k}={v:,}" for k, v in counts.items())
        print(f"\nDone in {time.monotonic() - started:.0f}s — {summary}")
        print("An etl_meta 'upsert' row was written, so your next `make dev` skips the")
        print("automatic startup backfill for 3h, then resumes incremental catch-up.")
        print("\nNext: make dev\n")
    finally:
        # asyncio.run() closes the loop on return. Dispose the pools first, or
        # aiomysql's Connection.__del__ fires against a closed loop during GC
        # and prints 'Event loop is closed' tracebacks after a clean run.
        await source_engine.dispose()
        await reporting_engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        die("interrupted — the reporting write rolled back. Safe to re-run.")
    except Exception as exc:
        die(f"{type(exc).__name__}: {exc} — rolled back, re-running is safe.")
