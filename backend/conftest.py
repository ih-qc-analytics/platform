import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

load_dotenv(Path(__file__).parent / ".env.test")
TEST_DB_URL = os.getenv("SOURCE_DB_URL", "").replace("mysql://", "mysql+aiomysql://")
SEEDS_DIR = Path(__file__).parent / "tests" / "seeds"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False, pool_pre_ping=True)
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


async def truncate_all(engine):
    tables = [
        "cart_product", "cart", "seller_lead",
        "lead_address", "`lead`", "seller",
        "product", "exam_cat", "auth", "zone"
    ]
    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in tables:
            await conn.execute(text(f"TRUNCATE TABLE {table}"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest_asyncio.fixture(loop_scope="session")
async def ventas_totales_db(test_engine, session_factory):
    await truncate_all(test_engine)
    await load_seed(test_engine, "ventas_totales.sql")
    import app.database as db
    db.SessionLocal = session_factory
    db.engine = test_engine
    yield
    await truncate_all(test_engine)


@pytest_asyncio.fixture(loop_scope="session")
async def ui_dev_db(test_engine, session_factory):
    await truncate_all(test_engine)
    await load_seed(test_engine, "ui_dev.sql")
    import app.database as db
    db.SessionLocal = session_factory
    db.engine = test_engine
    yield
    await truncate_all(test_engine)


@pytest_asyncio.fixture(loop_scope="session")
async def por_asesor_db(test_engine, session_factory):
    await truncate_all(test_engine)
    await load_seed(test_engine, "por_asesor.sql")
    import app.database as db
    db.SessionLocal = session_factory
    db.engine = test_engine
    yield
    await truncate_all(test_engine)


@pytest_asyncio.fixture(loop_scope="session")
async def detalle_asesor_db(test_engine, session_factory):
    await truncate_all(test_engine)
    await load_seed(test_engine, "detalle_asesor.sql")
    import app.database as db
    db.SessionLocal = session_factory
    db.engine = test_engine
    yield
    await truncate_all(test_engine)
