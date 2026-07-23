from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

reporting_engine = create_async_engine(
    settings.reporting_db_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    # PgBouncer session-mode hard limit is 15. pool_size=10 leaves headroom for ETL
    # and other processes. max_overflow=0 forces SQLAlchemy to queue rather than
    # open new connections past pool_size, preventing EMAXCONNSESSION crashes.
    pool_size=10,
    max_overflow=0,
    pool_timeout=60,
)

ReportingSessionLocal = async_sessionmaker(
    bind=reporting_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
