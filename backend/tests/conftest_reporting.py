import pytest
import pytest_asyncio
from pathlib import Path
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
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
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_REPORTING_SYNC_URL)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session")
async def reporting_engine():
    _run_alembic_upgrade()  # applies all migrations including cost_mxn
    engine = create_async_engine(TEST_REPORTING_DB_URL, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def reporting_session_factory(reporting_engine):
    return async_sessionmaker(
        bind=reporting_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def clean_reporting_db(reporting_engine):
    """Truncate reporting tables between tests."""
    yield
    async with reporting_engine.begin() as conn:
        await conn.execute(text("TRUNCATE report_line_items, etl_meta RESTART IDENTITY"))


def bind_test_reporting_database(session_factory):
    """Patch ReportingSessionLocal in ETL and reporting modules to use the test DB."""
    import app.etl.payment_upsert as pu
    import app.etl.dimensional_refresh as dr
    import app.reporting.database as rdb
    rdb.ReportingSessionLocal = session_factory
    pu.ReportingSessionLocal = session_factory
    dr.ReportingSessionLocal = session_factory
