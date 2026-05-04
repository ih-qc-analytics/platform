from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    source_db_url: str = ""
    environment: str = "development"

    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False, 
        extra='ignore'        
    )

settings = Settings()