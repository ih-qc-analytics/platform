from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# asyncpg requires postgresql+asyncpg:// scheme
db_url = settings.source_db_url.replace("postgresql://", "postgresql+asyncpg://")

engine = None

if db_url and db_url != "+asyncpg://":
    engine = create_async_engine(
        db_url,
        echo=settings.environment == "development",
        pool_size=5,
        max_overflow=10,
    )
    SessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

class Base(DeclarativeBase):
    pass

async def get_db():
    async with SessionLocal() as session:
        yield session