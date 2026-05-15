import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
import importlib

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


def bind_test_database(session_factory, engine):
    import app.database as db

    db.SessionLocal = session_factory
    db.engine = engine

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
