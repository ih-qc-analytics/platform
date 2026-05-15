from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

reporting_engine = create_async_engine(
    settings.reporting_db_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)

ReportingSessionLocal = async_sessionmaker(
    bind=reporting_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
