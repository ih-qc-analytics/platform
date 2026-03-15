from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings

db_string = settings.source_db_url
if not db_string:
    raise ValueError("SOURCE_DB_URL not set in .env")

url = db_string.replace("mysql://", "mysql+aiomysql://")
engine = create_async_engine(
    url,
    echo=False,
    pool_pre_ping=True,       
    pool_recycle=3600,     
)

SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession)

## para generar una session que se puede usar para hacer queries a la base de datos
## cada sesion generada es independiente
async def get_db():
    async with SessionLocal() as session:
        yield session