from sqlalchemy import create_engine
from pathlib import Path  # noqa: F401
from app.config import settings


## para obtener un engine de conexión a la base de datos
## este engine es sincronizado
def get_engine():
    db_string = settings.source_db_url
    if not db_string:
        raise ValueError("SOURCE_DB_URL not set in .env")
    url = db_string.replace("mysql://", "mysql+pymysql://")
    return create_engine(url)
