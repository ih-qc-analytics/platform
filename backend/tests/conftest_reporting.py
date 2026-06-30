import pytest
import pytest_asyncio
import importlib
from pathlib import Path
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

load_dotenv(Path(__file__).parent.parent / ".env.test")

_user = os.getenv("DEV_REPORTING_DB_USER")
_pass = os.getenv("DEV_REPORTING_DB_PASS")
_host = os.getenv("DEV_REPORTING_DB_HOST")
_port = os.getenv("DEV_REPORTING_DB_PORT", "5432")
_name = os.getenv("DEV_REPORTING_DB_NAME")
_safe_pass = quote_plus(_pass) if _pass else ""

# asyncpg URL for SQLAlchemy async sessions
TEST_REPORTING_DB_URL = f"postgresql+asyncpg://{_user}:{_safe_pass}@{_host}:{_port}/{_name}"
# sync URL for Alembic (no +asyncpg driver)
TEST_REPORTING_SYNC_URL = f"postgresql://{_user}:{_safe_pass}@{_host}:{_port}/{_name}"

_BACKEND_DIR = Path(__file__).parent.parent


def _run_alembic_upgrade():
    """Run all pending migrations against the test reporting DB."""
    cleanup_engine = create_engine(
        TEST_REPORTING_SYNC_URL, connect_args={"connect_timeout": 10}
    )
    with cleanup_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS report_payment_allocations"))
        conn.execute(text("DROP TABLE IF EXISTS report_payments"))
        conn.execute(text("DROP TABLE IF EXISTS report_line_items"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    cleanup_engine.dispose()

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_REPORTING_SYNC_URL)
    command.stamp(cfg, "base", purge=True)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def reporting_engine():
    _run_alembic_upgrade()  # applies all migrations including cost_mxn
    engine = create_async_engine(TEST_REPORTING_DB_URL, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def reporting_session_factory(reporting_engine):
    return async_sessionmaker(
        bind=reporting_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture(loop_scope="session")
async def clean_reporting_db(reporting_engine):
    """Truncate reporting tables between tests."""
    yield
    async with reporting_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY"
            )
        )


def bind_test_reporting_database(session_factory):
    """Patch ReportingSessionLocal in ETL and reporting modules to use the test DB."""
    import app.etl.exchange_rate_backfill as erb
    import app.etl.dimensional_refresh as dr
    import app.etl.exchange_rates as er
    import app.etl.payment_upsert as pu
    import app.etl.startup_backfill as sb
    import app.etl.shared as shared
    import app.etl.upsert as up
    import app.reporting.database as rdb

    rdb.ReportingSessionLocal = session_factory
    erb.ReportingSessionLocal = session_factory
    er.ReportingSessionLocal = session_factory
    pu.ReportingSessionLocal = session_factory
    sb.ReportingSessionLocal = session_factory
    sb.run_upsert = up.run_upsert
    dr.ReportingSessionLocal = session_factory
    shared.ReportingSessionLocal = session_factory
    up.ReportingSessionLocal = session_factory

    module_names = [
        "app.services.filters.filters",
        "app.services.total_sales.total_sales",
        "app.services.por_asesor.repository",
        "app.services.por_asesor.por_asesor",
        "app.services.detalle_asesor.detalle_asesor",
        "app.services.por_pais.repository",
        "app.services.por_pais.por_pais",
    ]
    for module_name in module_names:
        module = importlib.import_module(module_name)
        setattr(module, "ReportingSessionLocal", session_factory)
