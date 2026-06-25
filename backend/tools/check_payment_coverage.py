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
    "payment_date_coverage": """
        SELECT
            COUNT(*)                                                        AS total_aprobado,
            SUM(CASE WHEN paymentDate IS NOT NULL THEN 1 ELSE 0 END)       AS has_payment_date,
            SUM(CASE WHEN paymentDate IS NULL THEN 1 ELSE 0 END)           AS missing_payment_date,
            ROUND(100.0 * SUM(CASE WHEN paymentDate IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_with_date
        FROM payment
        WHERE status = 'Aprobado'
    """,

    "payment_date_by_year": """
        SELECT
            YEAR(c.createdAt)                                               AS cart_year,
            COUNT(*)                                                        AS total,
            SUM(CASE WHEN p.paymentDate IS NOT NULL THEN 1 ELSE 0 END)     AS has_date,
            SUM(CASE WHEN p.paymentDate IS NULL THEN 1 ELSE 0 END)         AS no_date
        FROM payment p
        JOIN cart c ON c.id = p.cartId
        WHERE p.status = 'Aprobado'
          AND c.deletedAt IS NULL
        GROUP BY YEAR(c.createdAt)
        ORDER BY cart_year DESC
    """,
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
