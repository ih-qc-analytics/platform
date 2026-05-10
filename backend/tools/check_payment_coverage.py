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
    "cart_billing_status": """
        SELECT 
            CASE 
                WHEN status IS NULL THEN 'IS NULL'
                WHEN status = '' THEN 'EMPTY STRING'
                ELSE status 
            END AS status_check,
            COUNT(*) AS occurrences
        FROM cart_billing
        GROUP BY 
            CASE 
                WHEN status IS NULL THEN 'IS NULL'
                WHEN status = '' THEN 'EMPTY STRING'
                ELSE status 
            END
        ORDER BY occurrences DESC;
    """,
    "payment_status" : """
    SELECT status, COUNT(*) as count
    FROM payment
    GROUP BY status
    ORDER BY count DESC;
    """,
    "orphan": """
            SELECT COUNT(*) AS orphan_student_payments
        FROM student_payments sp
        LEFT JOIN payment p ON p.id = sp.payment_id
        WHERE p.id IS NULL;
    """, 
    "version": 
    """ 
    SELECT VERSION();
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
