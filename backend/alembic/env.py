from logging.config import fileConfig
from urllib.parse import quote_plus
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv
from pathlib import Path
import os

# Load .env from backend root
load_dotenv(Path(__file__).parent.parent / ".env")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Mirror the prod/dev split from config.py
_env = os.getenv("ENVIRONMENT", "dev").lower()
_prefix = "PROD_REPORTING" if _env == "prod" else "DEV_REPORTING"
_user = os.getenv(f"{_prefix}_DB_USER")
_pass = os.getenv(f"{_prefix}_DB_PASS")
_host = os.getenv(f"{_prefix}_DB_HOST")
_port = os.getenv(f"{_prefix}_DB_PORT", "5432")
_name = os.getenv(f"{_prefix}_DB_NAME")
_safe_pass = quote_plus(_pass) if _pass else ""
_reporting_url = f"postgresql://{_user}:{_safe_pass}@{_host}:{_port}/{_name}"

# configparser interprets % as interpolation syntax, so escape any % in the URL
config.set_main_option("sqlalchemy.url", _reporting_url.replace("%", "%%"))

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
