from dotenv import dotenv_values
from sqlalchemy import create_engine
from pathlib import Path
from app.config import settings


## para obtener un engine de conexión a la base de datos
## este engine es sincronizado 
def get_engine(): 
    env = dotenv_values(Path(__file__).parent.parent / ".env")
    db_string = settings.source_db_url
    if not db_string:
        raise ValueError("SOURCE_DB_URL not set in .env")
    url = db_string.replace("mysql://", "mysql+pymysql://")
    return create_engine(url)
    
