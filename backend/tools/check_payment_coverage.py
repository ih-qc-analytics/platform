from pathlib import Path
import sys
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings


def build_sync_url() -> str:
    user = settings.user
    password = settings.password or ""
    host = settings.host
    port = settings.port
    dbname = settings.dbname

    if not all([user, host, port, dbname]):
        raise ValueError(
            f"Missing DB config for ENVIRONMENT={settings.env_mode}. "
            "Expected PROD_DB_* or DEV_DB_* variables."
        )

    return f"mysql+pymysql://{user}:{quote_plus(password)}@{host}:{port}/{dbname}"


QUERIES = {
    "ja": 
    """
 SELECT COUNT(*) as mismatches
FROM cart c
WHERE ABS(
    (SELECT COALESCE(SUM(total), 0) FROM cart_product WHERE cartId = c.id)
    - (SELECT COALESCE(SUM(quantity), 0) FROM payment WHERE cartId = c.id AND status = 'Aprobado')
) > 1;
    """
  
}


def print_rows(name: str, rows: list[dict]) -> None:
    print(f"\n== {name} ==")
    if not rows:
        print("(no rows)")
        return
    for row in rows:
        print(row)


def main() -> None:
    url = build_sync_url()
    engine = create_engine(url, pool_pre_ping=True)
    print(f"ENVIRONMENT={settings.env_mode}")
    print(f"HOST={settings.host}")
    print(f"DB={settings.dbname}")

    with engine.connect() as conn:
        for name, sql in QUERIES.items():
            result = conn.execute(text(sql))
            rows = [dict(row._mapping) for row in result.fetchall()]
            print_rows(name, rows)


if __name__ == "__main__":
    main()
