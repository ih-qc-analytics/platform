from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    source_db_url: str = ""
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    environment: str = "development"

    class Config:
        env_file = ".env"

settings = Settings() 