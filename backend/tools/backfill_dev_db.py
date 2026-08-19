"""backfill_dev_db.py — load PRODUCTION data into the LOCAL dev reporting DB.

Runs the existing ETL with the source pointed at production MySQL (read-only)
and the reporting target pinned to the local Supabase Postgres.

app/config.py derives BOTH databases from a single ENVIRONMENT var, so there is
no supported "prod source + local reporting" combination.  This script creates
one by setting ENVIRONMENT=dev and injecting the PROD_DB_* values into the
DEV_DB_* slots before app.config is imported.  That direction fails safe: with
env_mode == "dev" the reporting side can only ever resolve to DEV_REPORTING_DB_*,
so a broken remap can never write to the production reporting DB.

The change is process-local — backend/.env is never modified.

Usage (from backend/):
    make backfill-dev-db
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

RULE = "═" * 60
SOURCE_KEYS = ("USER", "PASS", "HOST", "PORT", "NAME")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
REPORT_TABLES = ("report_payments", "report_line_items", "report_payment_allocations")


def die(*lines: str) -> None:
    print(f"\n{RULE}", file=sys.stderr)
    for line in lines:
        print(f"  {line}", file=sys.stderr)
    print(f"{RULE}\n", file=sys.stderr)
    sys.exit(1)


# ── Rewire the environment before any app.* import ───────────────────────────
# load_dotenv defaults to override=False, so the later calls inside app/config.py
# and alembic/env.py will not clobber anything we set here.
load_dotenv(BACKEND_DIR / ".env")

_missing = [f"PROD_DB_{k}" for k in SOURCE_KEYS if not os.getenv(f"PROD_DB_{k}")]
_missing += [
    f"DEV_REPORTING_DB_{k}"
    for k in ("USER", "HOST", "PORT", "NAME")
    if not os.getenv(f"DEV_REPORTING_DB_{k}")
]
if _missing:
    die(
        "Missing required variables in backend/.env:",
        "",
        *[f"  - {name}" for name in _missing],
        "",
        "The local reporting DB is the Supabase instance started by `supabase start`:",
        "  DEV_REPORTING_DB_USER=postgres",
        "  DEV_REPORTING_DB_PASS=postgres",
        "  DEV_REPORTING_DB_HOST=localhost",
        "  DEV_REPORTING_DB_PORT=54322",
        "  DEV_REPORTING_DB_NAME=postgres",
    )

os.environ["ENVIRONMENT"] = "dev"
for _key in SOURCE_KEYS:
    os.environ[f"DEV_DB_{_key}"] = os.environ[f"PROD_DB_{_key}"]

from sqlalchemy import text  # noqa: E402 — must follow the env rewiring above

from app.config import settings  # noqa: E402 — must follow the env rewiring above
from app.enums import ETLJobName  # noqa: E402 — must follow the env rewiring above
from app.etl.exchange_rate_backfill import ensure_exchange_rates_for_range  # noqa: E402 — must follow the env rewiring above
from app.etl.upsert import run_upsert  # noqa: E402 — must follow the env rewiring above
from app.reporting.database import ReportingSessionLocal  # noqa: E402 — must follow the env rewiring above


def assert_local_reporting() -> None:
    """Refuse to run unless the resolved reporting target is a local host."""
    host = (settings.reporting_db_host or "").strip().lower()
    prod_host = (os.getenv("PROD_REPORTING_DB_HOST") or "").strip().lower()

    if settings.env_mode != "dev" or host not in LOCAL_HOSTS or (prod_host and host == prod_host):
        die(
            "ABORTED — refusing to run: the reporting target is not local.",
            "",
            f"  resolved ENVIRONMENT    : {settings.env_mode}",
            f"  resolved reporting host : {host or '(unset)'}",
            f"  allowed hosts           : {', '.join(sorted(LOCAL_HOSTS))}",
            "",
            "This tool only ever writes to the local Supabase Postgres.",
            "Check DEV_REPORTING_DB_HOST in backend/.env (expected: localhost:54322).",
        )


def confirm() -> None:
    print(f"\n{RULE}")
    print("  Backfill the LOCAL dev reporting DB from PRODUCTION")
    print("")
    print(f"    source (read-only) : {settings.host}:{settings.port}/{settings.dbname}  [PROD]")
    print(
        f"    target (truncated) : {settings.reporting_db_host}:{settings.reporting_db_port}"
        f"/{settings.reporting_db_name}  [LOCAL]"
    )
    print(f"    since              : {settings.payment_upsert_initial_since.isoformat()}")
    print("")
    print(f"  {', '.join(REPORT_TABLES)}")
    print("  will be TRUNCATED and reloaded. The full history loads in a single")
    print("  pass, so expect several minutes and multi-GB memory use.")
    print(f"{RULE}")

    try:
        answer = input("\nProceed? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        print("Aborted.")
        sys.exit(1)


def run_migrations() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        die(
            "Migrations failed — see the alembic output above.",
            "Is the local Supabase running? Try: supabase start",
        )


async def truncate_report_tables() -> None:
    async with ReportingSessionLocal() as session:
        await session.execute(text(f"TRUNCATE {', '.join(REPORT_TABLES)} RESTART IDENTITY"))
        await session.commit()


async def _run() -> dict:
    since = settings.payment_upsert_initial_since

    print("\n[1/4] Applying migrations to the local reporting DB…")
    run_migrations()

    print(f"\n[2/4] Truncating {len(REPORT_TABLES)} report tables…")
    await truncate_report_tables()

    print("\n[3/4] Backfilling exchange rates (Frankfurter)…")
    print("      If MISSING_FX_RATES errors appear, stop and re-run on a stable network —")
    print("      the upsert would otherwise freeze fallback rates into the report tables.")
    await ensure_exchange_rates_for_range(since.date())

    print(f"\n[4/4] Running the payment upsert since {since.isoformat()}…")
    print("      (no progress output until this completes — it is one transaction)")
    return await run_upsert(since=since, job_name=ETLJobName.UPSERT)


def main() -> None:
    assert_local_reporting()
    confirm()

    started = time.monotonic()
    try:
        counts = asyncio.run(_run())
    except KeyboardInterrupt:
        die("Interrupted — the reporting write rolled back. Safe to re-run.")
    except Exception as exc:
        die(
            f"Backfill failed: {type(exc).__name__}: {exc}",
            "",
            "The reporting write is a single transaction, so it rolled back.",
            "Re-running is safe — every write is an upsert.",
        )

    elapsed = time.monotonic() - started
    print(f"\n{RULE}")
    print("  Local dev reporting DB backfilled")
    print("")
    print(f"    source (read)  : {settings.host}:{settings.port}/{settings.dbname}  [PROD]")
    print(
        f"    target (write) : {settings.reporting_db_host}:{settings.reporting_db_port}"
        f"/{settings.reporting_db_name}  [LOCAL]"
    )
    print("")
    print(f"    payments       : {counts['payments']:>10,}")
    print(f"    line_items     : {counts['line_items']:>10,}")
    print(f"    allocations    : {counts['allocations']:>10,}")
    print(f"    deleted        : {counts['deleted']:>10,}")
    print(f"    elapsed        : {elapsed:>10.1f}s")
    print("")
    print("  An etl_meta row (job_name='upsert', status='success') was written, so")
    print("  your next `make dev` skips the automatic startup backfill for 3 hours,")
    print("  then resumes incremental catch-up. This is expected.")
    print("")
    print("  Next: make dev")
    print(f"{RULE}\n")


if __name__ == "__main__":
    main()
