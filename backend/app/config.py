from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    source_db_url: str = ""
    environment: str = "development"

    class Config:
        env_file = ".env"

settings = Settings() 