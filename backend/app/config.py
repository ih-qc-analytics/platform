import os
from datetime import datetime
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

    # Auth
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    admin_api_key: str = os.getenv("ADMIN_API_KEY", "")

    # CORS — comma-separated origins, e.g. "https://app.example.com,http://localhost:5173"
    @property
    def cors_origins(self) -> list[str]:
        raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def payment_upsert_lookback_hours(self) -> int:
        return int(os.getenv("PAYMENT_UPSERT_LOOKBACK_HOURS", "3"))

    @property
    def payment_upsert_initial_since(self) -> datetime:
        raw_value = os.getenv("PAYMENT_UPSERT_INITIAL_SINCE", "2023-01-01T00:00:00")
        return datetime.fromisoformat(raw_value)


settings = Settings()
