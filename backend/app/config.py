import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

class Settings:
    env_mode = os.getenv("ENVIRONMENT", "dev").lower()

    # Source DB (Jones MySQL) — same vars regardless of naming, prod = source
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

    # Reporting DB (PostgreSQL / Supabase) — mirrors prod/dev split of source DB
    if env_mode == "prod":
        reporting_db_user = os.getenv("PROD_REPORTING_DB_USER")
        reporting_db_pass = os.getenv("PROD_REPORTING_DB_PASS")
        reporting_db_host = os.getenv("PROD_REPORTING_DB_HOST")
        reporting_db_port = os.getenv("PROD_REPORTING_DB_PORT", "5432")
        reporting_db_name = os.getenv("PROD_REPORTING_DB_NAME")
    else:
        reporting_db_user = os.getenv("DEV_REPORTING_DB_USER")
        reporting_db_pass = os.getenv("DEV_REPORTING_DB_PASS")
        reporting_db_host = os.getenv("DEV_REPORTING_DB_HOST")
        reporting_db_port = os.getenv("DEV_REPORTING_DB_PORT", "5432")
        reporting_db_name = os.getenv("DEV_REPORTING_DB_NAME")

    @property
    def source_db_url(self) -> str | None:
        """Truthy if the source (Jones MySQL) DB is configured."""
        return self.host

    @property
    def reporting_db_url(self) -> str | None:
        """asyncpg URL for the PostgreSQL reporting DB."""
        if not all([self.reporting_db_user, self.reporting_db_host, self.reporting_db_name]):
            return None
        safe_pass = quote_plus(self.reporting_db_pass) if self.reporting_db_pass else ""
        return (
            f"postgresql+asyncpg://{self.reporting_db_user}:{safe_pass}"
            f"@{self.reporting_db_host}:{self.reporting_db_port}/{self.reporting_db_name}"
        )

settings = Settings()