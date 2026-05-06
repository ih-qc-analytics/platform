import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    env_mode = os.getenv("ENVIRONMENT", "dev").lower()
    
    if env_mode == "prod":
        user = os.getenv("PROD_DB_USER")
        password = os.getenv("PROD_DB_PASS")
        host = os.getenv("PROD_DB_HOST")
        port = os.getenv("PROD_DB_PORT")
        dbname = os.getenv("PROD_DB_NAME")
    else:
        user = os.getenv("DEV_DB_USER")
        password = os.getenv("DEV_DB_PASS")
        host = os.getenv("DEV_DB_HOST")
        port = os.getenv("DEV_DB_PORT")
        dbname = os.getenv("DEV_DB_NAME")

settings = Settings()