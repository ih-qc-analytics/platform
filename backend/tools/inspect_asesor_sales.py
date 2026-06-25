import argparse
import json
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
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


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "seller"


def rows_to_dicts(result) -> list[dict]:
    return [dict(row._mapping) for row in result.fetchall()]


def make_json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: make_json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    return value


def run_query(conn, sql: str, params: dict) -> list[dict]:
    return rows_to_dicts(conn.execute(text(sql), params))


SELLER_LOOKUP_SQL = """
SELECT
    s.id AS seller_id,
    CONCAT(s.name, ' ', s.lastName) AS seller_name
FROM seller s
WHERE CONCAT(s.name, ' ', s.lastName) = :seller_name
ORDER BY s.id;
"""


SELLER_CANDIDATES_SQL = """
SELECT
    s.id AS seller_id,
    CONCAT(s.name, ' ', s.lastName) AS seller_name
FROM seller s
WHERE CONCAT(s.name, ' ', s.lastName) LIKE :seller_name_like
ORDER BY seller_name, s.id;
"""


RAW_PAYMENTS_SQL = """
SELECT
    pay.id AS payment_id,
    COALESCE(pay.paymentDate, DATE(pay.createdAt)) AS payment_day,
    pay.createdAt AS payment_created_at,
    pay.paymentDate AS payment_date_raw,
    pay.status AS payment_status,
    pay.quantity AS paid_amount,
    c.id AS cart_id,
    c.billingStatus AS cart_billing_status,
    sl.id AS seller_lead_id,
    l.id AS lead_id,
    l.name AS school_name,
    l.site AS country,
    z.name AS zone_name
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
LEFT JOIN zone z ON z.id = l.zoneId
WHERE sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND pay.status = 'Aprobado'
  AND YEAR(COALESCE(pay.paymentDate, DATE(pay.createdAt))) = :year
  AND CONCAT(s.name, ' ', s.lastName) = :seller_name
ORDER BY payment_day, pay.id;
"""


PAYMENT_SUMMARY_BY_LEAD_SQL = """
SELECT
    l.id AS lead_id,
    l.name AS school_name,
    l.site AS country,
    COUNT(*) AS approved_payments,
    SUM(pay.quantity) AS total_paid_amount
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
WHERE sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND pay.status = 'Aprobado'
  AND YEAR(COALESCE(pay.paymentDate, DATE(pay.createdAt))) = :year
  AND CONCAT(s.name, ' ', s.lastName) = :seller_name
GROUP BY l.id, l.name, l.site
ORDER BY total_paid_amount DESC, school_name ASC;
"""


RAW_ALLOCATIONS_SQL = """
SELECT
    sp.payment_id,
    COALESCE(pay.paymentDate, DATE(pay.createdAt)) AS payment_day,
    pay.quantity AS payment_amount,
    sp.student_id,
    sp.amount AS allocated_amount,
    st.cartProductId AS cart_product_id,
    cp.quantity AS cart_product_quantity,
    cp.total AS cart_product_total,
    cp.cost AS cart_product_cost,
    cp.testDate AS exam_date,
    p.id AS product_id,
    p.name AS product_name,
    p.productType AS product_type,
    ec.name AS exam_name,
    c.id AS cart_id,
    l.id AS lead_id,
    l.name AS school_name,
    l.site AS country
FROM student_payments sp
JOIN payment pay ON pay.id = sp.payment_id
JOIN student st ON st.id = sp.student_id
JOIN cart_product cp ON cp.id = st.cartProductId
JOIN product p ON p.id = cp.productId
LEFT JOIN exam_cat ec ON ec.id = p.examId
JOIN cart c ON c.id = cp.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
WHERE cp.deletedAt IS NULL
  AND sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND p.productType = 'exam'
  AND pay.status = 'Aprobado'
  AND YEAR(COALESCE(pay.paymentDate, DATE(pay.createdAt))) = :year
  AND CONCAT(s.name, ' ', s.lastName) = :seller_name
ORDER BY payment_day, sp.payment_id, st.cartProductId, sp.student_id;
"""


ALLOCATION_SUMMARY_BY_EXAM_SQL = """
SELECT
    COALESCE(ec.name, '(null exam)') AS exam_name,
    COUNT(*) AS allocation_rows,
    COUNT(DISTINCT st.cartProductId) AS cart_products,
    COUNT(DISTINCT sl.leadId) AS schools,
    SUM(cp.quantity) AS summed_cart_product_quantity_fanout,
    SUM(sp.amount) AS total_allocated_amount
FROM student_payments sp
JOIN payment pay ON pay.id = sp.payment_id
JOIN student st ON st.id = sp.student_id
JOIN cart_product cp ON cp.id = st.cartProductId
JOIN product p ON p.id = cp.productId
LEFT JOIN exam_cat ec ON ec.id = p.examId
JOIN cart c ON c.id = cp.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
WHERE cp.deletedAt IS NULL
  AND sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND p.productType = 'exam'
  AND pay.status = 'Aprobado'
  AND YEAR(COALESCE(pay.paymentDate, DATE(pay.createdAt))) = :year
  AND CONCAT(s.name, ' ', s.lastName) = :seller_name
GROUP BY COALESCE(ec.name, '(null exam)')
ORDER BY total_allocated_amount DESC, exam_name ASC;
"""


PAYMENT_ALLOCATION_RECONCILIATION_SQL = """
SELECT
    pay.id AS payment_id,
    COALESCE(pay.paymentDate, DATE(pay.createdAt)) AS payment_day,
    pay.quantity AS payment_amount,
    COUNT(sp.student_id) AS allocation_rows,
    COALESCE(SUM(sp.amount), 0) AS allocated_total,
    pay.quantity - COALESCE(SUM(sp.amount), 0) AS unallocated_gap
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
LEFT JOIN student_payments sp ON sp.payment_id = pay.id
WHERE sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND pay.status = 'Aprobado'
  AND YEAR(COALESCE(pay.paymentDate, DATE(pay.createdAt))) = :year
  AND CONCAT(s.name, ' ', s.lastName) = :seller_name
GROUP BY pay.id, payment_day, pay.quantity
ORDER BY payment_day, pay.id;
"""


CURRENT_YEAR_STATUS_INPUTS_SQL = """
SELECT
    l.id AS lead_id,
    l.name AS school_name,
    l.site AS country,
    COUNT(DISTINCT cp.id) AS distinct_cart_products,
    COALESCE(SUM(DISTINCT cp.quantity), 0) AS suspicious_distinct_quantity_sum,
    COALESCE(SUM(sp.amount), 0) AS allocated_revenue
FROM student_payments sp
JOIN payment pay ON pay.id = sp.payment_id
JOIN student st ON st.id = sp.student_id
JOIN cart_product cp ON cp.id = st.cartProductId
JOIN product p ON p.id = cp.productId
JOIN cart c ON c.id = cp.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
WHERE cp.deletedAt IS NULL
  AND sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND p.productType = 'exam'
  AND pay.status = 'Aprobado'
  AND YEAR(COALESCE(pay.paymentDate, DATE(pay.createdAt))) = :year
  AND CONCAT(s.name, ' ', s.lastName) = :seller_name
GROUP BY l.id, l.name, l.site
ORDER BY allocated_revenue DESC, school_name ASC;
"""


def build_output(
    seller_name: str,
    year: int,
    seller_rows: list[dict],
    candidate_rows: list[dict],
    raw_payments: list[dict],
    payment_summary_by_lead: list[dict],
    raw_allocations: list[dict],
    allocation_summary_by_exam: list[dict],
    payment_allocation_reconciliation: list[dict],
    current_year_status_inputs: list[dict],
) -> dict:
    payment_total = sum(float(row["paid_amount"] or 0) for row in raw_payments)
    allocated_total = sum(float(row["allocated_amount"] or 0) for row in raw_allocations)

    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "environment": settings.env_mode,
            "host": settings.host,
            "database": settings.dbname,
            "seller_name": seller_name,
            "year": year,
        },
        "seller_lookup": {
            "exact_matches": seller_rows,
            "candidates": candidate_rows,
        },
        "report_like_totals": {
            "payment_total_revenue": payment_total,
            "allocated_exam_revenue": allocated_total,
            "payment_minus_allocated_gap": payment_total - allocated_total,
            "approved_payment_count": len(raw_payments),
            "allocation_row_count": len(raw_allocations),
        },
        "raw_payments": raw_payments,
        "payment_summary_by_lead": payment_summary_by_lead,
        "raw_exam_allocations": raw_allocations,
        "allocation_summary_by_exam": allocation_summary_by_exam,
        "payment_allocation_reconciliation": payment_allocation_reconciliation,
        "current_year_status_inputs": current_year_status_inputs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dump advisor sales/payment coverage data for report debugging.",
    )
    parser.add_argument(
        "--seller", required=True, help='Exact advisor full name, e.g. "Laura López cdmx"'
    )
    parser.add_argument("--year", required=True, type=int, help="Report year to inspect")
    parser.add_argument(
        "--output",
        help="Output JSON file path. Defaults to backend/tools/output/<slug>-<year>.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = (
        Path(args.output)
        if args.output
        else Path(__file__).resolve().parent / "output" / f"{slugify(args.seller)}-{args.year}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(build_sync_url(), pool_pre_ping=True)
    params = {
        "seller_name": args.seller,
        "seller_name_like": f"%{args.seller}%",
        "year": args.year,
    }

    with engine.connect() as conn:
        seller_rows = run_query(conn, SELLER_LOOKUP_SQL, params)
        candidate_rows = run_query(conn, SELLER_CANDIDATES_SQL, params)
        raw_payments = run_query(conn, RAW_PAYMENTS_SQL, params)
        payment_summary_by_lead = run_query(conn, PAYMENT_SUMMARY_BY_LEAD_SQL, params)
        raw_allocations = run_query(conn, RAW_ALLOCATIONS_SQL, params)
        allocation_summary_by_exam = run_query(conn, ALLOCATION_SUMMARY_BY_EXAM_SQL, params)
        payment_allocation_reconciliation = run_query(
            conn, PAYMENT_ALLOCATION_RECONCILIATION_SQL, params
        )
        current_year_status_inputs = run_query(conn, CURRENT_YEAR_STATUS_INPUTS_SQL, params)

    output = build_output(
        args.seller,
        args.year,
        seller_rows,
        candidate_rows,
        raw_payments,
        payment_summary_by_lead,
        raw_allocations,
        allocation_summary_by_exam,
        payment_allocation_reconciliation,
        current_year_status_inputs,
    )

    output_path.write_text(json.dumps(make_json_safe(output), indent=2, ensure_ascii=False))
    print(f"Wrote advisor audit to {output_path}")


if __name__ == "__main__":
    main()
