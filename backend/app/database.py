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
    engine = create_async_engine(get_async_url())
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession)
except ValueError:
    # No source DB config — tests override these via conftest; production always has config.
    engine = None  # type: ignore[assignment]
    SessionLocal = None  # type: ignore[assignment]
