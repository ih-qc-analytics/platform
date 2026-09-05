from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings


def get_async_url() -> str:
    user = settings.user
    password = settings.password
    host = settings.host
    port = settings.port
    dbname = settings.dbname

    if not all([user, host, dbname]):
        raise ValueError(f"Missing DB config for: {settings.env_mode}")

    safe_password = quote_plus(password) if password else ""

    return f"mysql+aiomysql://{user}:{safe_password}@{host}:{port}/{dbname}"


try:
    engine = create_async_engine(
        get_async_url(),
        # Validate on checkout. pool_recycle alone only helps because the ETL jobs
        # run 3h apart — every connection is older than the recycle window and gets
        # rebuilt. The one exception is the upsert that runs 12 minutes after the
        # dimensional refresh: it reuses a connection young enough to survive
        # recycling but already dropped while idle, and fails with "Lost connection
        # to MySQL server during query". Same cause as intermittent 503s on login.
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession)
except ValueError:
    # No source DB config — tests override these via conftest; production always has config.
    engine = None  # type: ignore[assignment]
    SessionLocal = None  # type: ignore[assignment]
