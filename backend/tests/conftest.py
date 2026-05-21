import pytest
import pytest_asyncio
import asyncio
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
import importlib
from app.config import settings
from app.etl.upsert import run_upsert
from app.enums import ETLJobName
from tests.conftest_reporting import bind_test_reporting_database

pytest_plugins = ["conftest_reporting"]

_BACKEND_DIR = Path(__file__).parent.parent

load_dotenv(_BACKEND_DIR / ".env.test")
TEST_DB_URL = os.getenv("SOURCE_DB_URL", "").replace("mysql://", "mysql+aiomysql://")
SEEDS_DIR = _BACKEND_DIR / "tests" / "seeds"
SCHEMA_FILE = _BACKEND_DIR / "tests" / "schema.sql"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False, pool_pre_ping=True)
    await apply_schema(engine)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory(test_engine):
    return async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


async def load_seed(engine, seed_file: str):
    sql = (SEEDS_DIR / seed_file).read_text()
    async with engine.begin() as conn:
        for stmt in sql.split(";"):
            s = stmt.strip()
            if s:
                await conn.execute(text(s))


async def apply_schema(engine):
    schema_sql = SCHEMA_FILE.read_text()
    drop_tables = [
        "student_payments",
        "student",
        "payment",
        "cart_product",
        "cart",
        "seller_lead",
        "lead_address",
        "`lead`",
        "seller",
        "product",
        "exam_cat",
        "auth",
        "zone",
    ]
    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in drop_tables:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        for stmt in schema_sql.split(";"):
            s = stmt.strip()
            if s:
                await conn.execute(text(s))


async def truncate_all(engine):
    tables = [
        "student_payments", "student", "cart_product", "cart", "seller_lead",
        "payment", "lead_address", "`lead`", "seller",
        "product", "exam_cat", "auth", "zone"
    ]
    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in tables:
            await conn.execute(text(f"TRUNCATE TABLE {table}"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


async def truncate_reporting_all(engine):
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY"
        ))


async def seed_identity_exchange_rates(session_factory):
    today = date.today()
    rows = [
        {"date": today, "from_currency": "MXN", "to_currency": "USD", "rate": 1.0},
        {"date": today, "from_currency": "COP", "to_currency": "MXN", "rate": 1.0},
        {"date": today, "from_currency": "COP", "to_currency": "USD", "rate": 1.0},
        {"date": today, "from_currency": "PEN", "to_currency": "MXN", "rate": 1.0},
        {"date": today, "from_currency": "PEN", "to_currency": "USD", "rate": 1.0},
    ]
    async with session_factory() as session:
        async with session.begin():
            for row in rows:
                await session.execute(text("""
                    INSERT INTO exchange_rates (date, from_currency, to_currency, rate)
                    VALUES (:date, :from_currency, :to_currency, :rate)
                    ON CONFLICT (date, from_currency, to_currency) DO UPDATE
                    SET rate = EXCLUDED.rate
                """), row)


def bind_test_database(session_factory, engine):
    import app.database as db
    import app.etl.dimensional_refresh as dr
    import app.etl.exchange_rates as er
    import app.etl.exchange_rate_backfill as erb
    import app.etl.payment_upsert as pu
    import app.etl.startup_backfill as sb
    import app.etl.shared as shared
    import app.etl.upsert as up

    db.SessionLocal = session_factory
    db.engine = engine
    dr.SessionLocal = session_factory
    er.SessionLocal = session_factory
    erb.SessionLocal = session_factory
    pu.SessionLocal = session_factory
    sb.run_upsert = up.run_upsert
    shared.SessionLocal = session_factory
    up.SessionLocal = session_factory

    module_names = [
        "app.services.total_sales.total_sales",
        "app.services.por_asesor.repository",
        "app.services.por_asesor.por_asesor",
        "app.services.detalle_asesor.detalle_asesor",
        "app.services.por_pais.repository",
        "app.services.por_pais.por_pais",
    ]
    for module_name in module_names:
        module = importlib.import_module(module_name)
        setattr(module, "SessionLocal", session_factory)


@pytest_asyncio.fixture(loop_scope="session")
async def ventas_totales_db(test_engine, session_factory):
    await truncate_all(test_engine)
    await load_seed(test_engine, "ui_dev.sql")
    bind_test_database(session_factory, test_engine)
    yield
    await truncate_all(test_engine)


@pytest_asyncio.fixture(loop_scope="session")
async def ui_dev_db(test_engine, session_factory):
    await truncate_all(test_engine)
    await load_seed(test_engine, "ui_dev.sql")
    bind_test_database(session_factory, test_engine)
    yield
    await truncate_all(test_engine)


@pytest_asyncio.fixture(loop_scope="session")
async def por_asesor_db(test_engine, session_factory):
    await truncate_all(test_engine)
    await load_seed(test_engine, "ui_dev.sql")
    bind_test_database(session_factory, test_engine)
    yield
    await truncate_all(test_engine)


@pytest_asyncio.fixture(loop_scope="session")
async def detalle_asesor_db(test_engine, session_factory):
    await truncate_all(test_engine)
    await load_seed(test_engine, "ui_dev.sql")
    bind_test_database(session_factory, test_engine)
    yield
    await truncate_all(test_engine)


@pytest_asyncio.fixture(loop_scope="session")
async def ui_dev_reporting_db(ui_dev_db, reporting_engine, reporting_session_factory):
    await truncate_reporting_all(reporting_engine)
    bind_test_reporting_database(reporting_session_factory)
    await seed_identity_exchange_rates(reporting_session_factory)
    await run_upsert(
        since=settings.payment_upsert_initial_since,
        job_name=ETLJobName.UPSERT,
    )
    yield
    await truncate_reporting_all(reporting_engine)
