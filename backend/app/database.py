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
        # Discard connections older than 10 minutes at checkout, so a connection
        # dropped while idle is never reused. The failure this prevents: the upsert
        # that runs ~12 minutes after the dimensional refresh reuses a connection
        # the network path already killed, and dies with "Lost connection to MySQL
        # server during query" — same cause as intermittent 503s on /auth/login.
        #
        # Do NOT switch this to pool_pre_ping. It looks like the right tool and it
        # is not usable on aiomysql: SQLAlchemy's pymysql dialect picks its ping
        # call by inspecting PyMySQL's signature, and from PyMySQL 1.2.0 (where
        # `reconnect` defaults to False) it calls `ping()` with no arguments, while
        # the async adapter declares `ping(self, reconnect)` with no default. Every
        # pooled checkout then raises TypeError and all ETL jobs die. PyMySQL is
        # pinned in requirements.txt for the same reason.
        pool_recycle=600,
    )
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession)
except ValueError:
    # No source DB config — tests override these via conftest; production always has config.
    engine = None  # type: ignore[assignment]
    SessionLocal = None  # type: ignore[assignment]
