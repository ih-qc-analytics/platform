"""
Diagnostic: explore payment.use values and negative amounts to understand
what the ETL should be filtering out.

Run from backend/tools/:
    python inspect_payment_types.py
"""
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
    return f"mysql+pymysql://{user}:{quote_plus(password)}@{host}:{port}/{dbname}"


QUERIES = {
    # --- payment.quantity (already confirmed clean, kept for reference) ---
    "negative_aprobado_payments": """
        SELECT COUNT(*) AS cnt, SUM(pay.quantity) AS total
        FROM payment pay
        WHERE pay.quantity < 0 AND pay.status = 'Aprobado'
    """,

    # --- cart_product.total / cost ---
    "negative_cart_products": """
        SELECT
            cp.total < 0 AS total_negative,
            cp.cost  < 0 AS cost_negative,
            COUNT(*) AS cnt,
            MIN(cp.total) AS min_total,
            MAX(cp.total) AS max_total,
            MIN(cp.cost)  AS min_cost
        FROM cart_product cp
        JOIN cart c ON c.id = cp.cartId
        WHERE c.deletedAt IS NULL
          AND cp.deletedAt IS NULL
          AND EXISTS (
              SELECT 1 FROM payment p
              WHERE p.cartId = c.id AND p.status = 'Aprobado'
          )
        GROUP BY total_negative, cost_negative
        ORDER BY total_negative DESC, cost_negative DESC
    """,

    # Sample negative cart_product.total rows with site context
    "negative_cart_product_samples": """
        SELECT
            cp.id AS cart_product_id,
            cp.total,
            cp.cost,
            cp.discount,
            cp.quantity,
            l.site,
            l.name AS school_name,
            c.billingStatus AS cart_billing_status
        FROM cart_product cp
        JOIN cart c ON c.id = cp.cartId
        JOIN seller_lead sl ON sl.id = c.sellerLeadId
        JOIN `lead` l ON l.id = sl.leadId
        WHERE cp.total < 0
          AND c.deletedAt IS NULL
          AND cp.deletedAt IS NULL
          AND EXISTS (
              SELECT 1 FROM payment p
              WHERE p.cartId = c.id AND p.status = 'Aprobado'
          )
        ORDER BY cp.total ASC
        LIMIT 20
    """,

    # --- student_payments.amount ---
    # First, check if the table and column exist
    "student_payments_schema": """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'student_payments'
        ORDER BY ORDINAL_POSITION
    """,

    "negative_student_payments": """
        SELECT
            sp.amount < 0 AS amount_negative,
            pay.status,
            COUNT(*) AS cnt,
            SUM(sp.amount) AS total_amount,
            MIN(sp.amount) AS min_amount
        FROM student_payments sp
        JOIN payment pay ON pay.id = sp.payment_id
        WHERE pay.status = 'Aprobado'
        GROUP BY amount_negative, pay.status
        ORDER BY amount_negative DESC
    """,

    # Aggregated paid_total per cart_product — can the SUM go negative?
    "negative_paid_total_aggregates": """
        SELECT
            st.cartProductId AS cart_product_id,
            SUM(sp.amount) AS paid_total,
            COUNT(DISTINCT sp.payment_id) AS payment_count,
            l.site
        FROM student_payments sp
        JOIN student st ON sp.student_id = st.id
        JOIN payment pay ON sp.payment_id = pay.id
        JOIN cart_product cp ON cp.id = st.cartProductId
        JOIN cart c ON c.id = cp.cartId
        JOIN seller_lead sl ON sl.id = c.sellerLeadId
        JOIN `lead` l ON l.id = sl.leadId
        WHERE pay.status = 'Aprobado'
        GROUP BY st.cartProductId, l.site
        HAVING SUM(sp.amount) < 0
        ORDER BY paid_total ASC
        LIMIT 20
    """,
}


def print_rows(name: str, rows: list[dict]) -> None:
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    if not rows:
        print("  (no rows)")
        return
    headers = list(rows[0].keys())
    col_widths = {h: max(len(str(h)), max(len(str(r.get(h, ""))) for r in rows)) for h in headers}
    header_line = "  " + "  ".join(str(h).ljust(col_widths[h]) for h in headers)
    print(header_line)
    print("  " + "-" * (len(header_line) - 2))
    for row in rows:
        print("  " + "  ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers))


def main() -> None:
    url = build_sync_url()
    engine = create_engine(url, pool_pre_ping=True)
    print(f"ENVIRONMENT={settings.env_mode}")
    print(f"HOST={settings.host}")
    print(f"DB={settings.dbname}")

    with engine.connect() as conn:
        for name, sql in QUERIES.items():
            try:
                result = conn.execute(text(sql))
                rows = [dict(row._mapping) for row in result.fetchall()]
                print_rows(name, rows)
            except Exception as exc:
                print(f"\n[ERROR] {name}: {exc}")

    print("\n")


if __name__ == "__main__":
    main()
