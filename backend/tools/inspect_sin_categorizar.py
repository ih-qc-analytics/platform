"""
inspect_sin_categorizar.py
──────────────────────────
Diagnostic tool to investigate "sin categorizar" anomalies in the por-asesor
report.  Queries BOTH the MySQL prod source and the PostgreSQL reporting DB to
cross-reference totals and pinpoint where uncategorized revenue originates.

Architecture (post-fix):
  - Revenue  → report_payment_allocations (one row per payment × cart_product)
  - Quantity → report_line_items (filtered by first_payment_date)
  - Total    → report_payments

  sin_categorizar = report_payments.amount_mxn − SUM(rpa.allocated_amount_mxn)
  By construction this should be ≈ 0 after a complete ETL run.
  Positive → payment exists with no/partial allocation rows (ETL gap)
  Negative → student_payment entries exceed actual payment (source data error)

Usage (run from backend/ with ENVIRONMENT=prod in .env):
  python -m tools.inspect_sin_categorizar --seller "Fernanda Fraga" \\
      --date-from 2026-01-01 --date-to 2026-07-22

Output: backend/tools/output/<slug>-<date_from>-<date_to>.json
"""

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


# ── helpers ─────────────────────────────────────────────────────────────────


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "seller"


def make_json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return {k: make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_json_safe(i) for i in value]
    return value


def rows(result) -> list[dict]:
    return [dict(row._mapping) for row in result.fetchall()]


def run(conn, sql: str, params: dict) -> list[dict]:
    return rows(conn.execute(text(sql), params))


# ── engine builders ──────────────────────────────────────────────────────────


def mysql_engine():
    user = settings.user
    password = settings.password or ""
    host = settings.host
    port = settings.port
    dbname = settings.dbname
    if not all([user, host, port, dbname]):
        raise ValueError("Missing PROD_DB_* variables in .env")
    url = f"mysql+pymysql://{user}:{quote_plus(password)}@{host}:{port}/{dbname}"
    return create_engine(url, pool_pre_ping=True)


def reporting_engine():
    u = settings.reporting_db_user
    p = settings.reporting_db_pass or ""
    h = settings.reporting_db_host
    port = settings.reporting_db_port
    db = settings.reporting_db_name
    if not all([u, h, db]):
        raise ValueError("Missing PROD_REPORTING_DB_* variables in .env")
    url = f"postgresql+psycopg2://{u}:{quote_plus(p)}@{h}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True)


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING DB QUERIES (PostgreSQL / Supabase)
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. Seller lookup ──────────────────────────────────────────────────────────
RDB_SELLER_LOOKUP = """
SELECT DISTINCT seller_id, seller_name
FROM report_payments
WHERE seller_name ILIKE :name_like
ORDER BY seller_name, seller_id;
"""

# ── 2. Top-level sin_categorizar summary ─────────────────────────────────────
#    Revenue source: report_payment_allocations (filtered by payment_date).
#    Total source:   report_payments (filtered by payment_date).
#    sin_cat = total_revenue_mxn − allocated_revenue_mxn.
#    Should be ≈ 0 after a complete ETL run.
RDB_SUMMARY = """
WITH pay_agg AS (
    SELECT
        seller_id,
        MIN(seller_name)            AS seller_name,
        COUNT(*)                    AS payment_count,
        COALESCE(SUM(amount_mxn),0) AS total_revenue_mxn,
        COALESCE(SUM(amount_usd),0) AS total_revenue_usd,
        COALESCE(SUM(amount),0)     AS total_revenue_base
    FROM report_payments
    WHERE is_active = TRUE
      AND payment_status = 'Aprobado'
      AND payment_date BETWEEN :date_from AND :date_to
      AND seller_name ILIKE :name_like
    GROUP BY seller_id
),
alloc_agg AS (
    SELECT
        rpa.seller_id,
        COUNT(*)                                        AS allocation_row_count,
        COALESCE(SUM(rpa.allocated_amount_mxn), 0)     AS allocated_mxn,
        COALESCE(SUM(rpa.allocated_amount_usd), 0)     AS allocated_usd,
        COALESCE(SUM(CASE WHEN rpa.product_type = 'exam'          THEN rpa.allocated_amount_mxn ELSE 0 END), 0) AS exam_mxn,
        COALESCE(SUM(CASE WHEN rpa.product_type = 'book'          THEN rpa.allocated_amount_mxn ELSE 0 END), 0) AS book_mxn,
        COALESCE(SUM(CASE WHEN rpa.product_type = 'course'        THEN rpa.allocated_amount_mxn ELSE 0 END), 0) AS course_mxn,
        COALESCE(SUM(CASE WHEN rpa.product_type = 'UNCATEGORIZED' THEN rpa.allocated_amount_mxn ELSE 0 END), 0) AS otros_mxn
    FROM report_payment_allocations rpa
    WHERE rpa.is_active = TRUE
      AND rpa.payment_date BETWEEN :date_from AND :date_to
      AND rpa.seller_name ILIKE :name_like
    GROUP BY rpa.seller_id
)
SELECT
    p.seller_id,
    p.seller_name,
    p.payment_count,
    p.total_revenue_mxn,
    p.total_revenue_usd,
    p.total_revenue_base,
    COALESCE(a.allocation_row_count, 0)  AS allocation_row_count,
    COALESCE(a.allocated_mxn,        0) AS allocated_mxn,
    COALESCE(a.allocated_usd,        0) AS allocated_usd,
    COALESCE(a.exam_mxn,             0) AS exam_mxn,
    COALESCE(a.book_mxn,             0) AS book_mxn,
    COALESCE(a.course_mxn,           0) AS course_mxn,
    COALESCE(a.otros_mxn,            0) AS otros_mxn,
    p.total_revenue_mxn - COALESCE(a.allocated_mxn, 0) AS sin_categorizar_mxn,
    p.total_revenue_usd - COALESCE(a.allocated_usd, 0) AS sin_categorizar_usd
FROM pay_agg p
LEFT JOIN alloc_agg a ON a.seller_id = p.seller_id
ORDER BY p.seller_name;
"""

# ── 3. Per-payment gap: report_payments vs report_payment_allocations ─────────
#    Ordered by absolute gap descending — the biggest offenders first.
#    gap_mxn > 0: payment has no/partial allocation rows (ETL gap)
#    gap_mxn < 0: allocated more than collected (student entry error)
RDB_PAYMENT_GAP = """
SELECT
    rp.payment_id,
    rp.cart_id,
    rp.school_name,
    rp.site,
    rp.payment_date                                  AS payment_date,
    rp.amount_mxn                                    AS payment_mxn,
    rp.amount_usd                                    AS payment_usd,
    rp.base_currency,
    COALESCE(a.allocated_mxn, 0)                     AS allocated_mxn,
    COALESCE(a.allocated_usd, 0)                     AS allocated_usd,
    rp.amount_mxn - COALESCE(a.allocated_mxn, 0)    AS gap_mxn,
    rp.amount_usd - COALESCE(a.allocated_usd, 0)    AS gap_usd,
    COALESCE(a.allocation_rows, 0)                   AS allocation_rows
FROM report_payments rp
LEFT JOIN (
    SELECT
        payment_id,
        COUNT(*)                            AS allocation_rows,
        SUM(allocated_amount_mxn)           AS allocated_mxn,
        SUM(allocated_amount_usd)           AS allocated_usd
    FROM report_payment_allocations
    WHERE is_active = TRUE
      AND seller_name ILIKE :name_like
    GROUP BY payment_id
) a ON a.payment_id = rp.payment_id
WHERE rp.is_active = TRUE
  AND rp.payment_status = 'Aprobado'
  AND rp.payment_date BETWEEN :date_from AND :date_to
  AND rp.seller_name ILIKE :name_like
ORDER BY ABS(rp.amount_mxn - COALESCE(a.allocated_mxn, 0)) DESC, rp.payment_date;
"""

# ── 4. Payments with zero allocation rows ─────────────────────────────────────
#    These payments contribute 100% to sin_categorizar.
#    Most likely cause: ETL has not run for these payments yet.
RDB_PAYMENTS_WITHOUT_ALLOCATIONS = """
SELECT
    rp.payment_id,
    rp.cart_id,
    rp.school_name,
    rp.site,
    rp.payment_date,
    rp.amount,
    rp.amount_mxn,
    rp.amount_usd,
    rp.base_currency,
    rp.year,
    rp.month
FROM report_payments rp
WHERE rp.is_active = TRUE
  AND rp.payment_status = 'Aprobado'
  AND rp.payment_date BETWEEN :date_from AND :date_to
  AND rp.seller_name ILIKE :name_like
  AND NOT EXISTS (
      SELECT 1 FROM report_payment_allocations rpa
      WHERE rpa.payment_id = rp.payment_id
        AND rpa.is_active = TRUE
  )
ORDER BY rp.payment_date, rp.payment_id;
"""

# ── 5. Allocation rows breakdown by product_type ──────────────────────────────
RDB_ALLOCATION_BREAKDOWN = """
SELECT
    rpa.product_type,
    COUNT(*)                                    AS allocation_rows,
    COUNT(DISTINCT rpa.payment_id)              AS distinct_payments,
    COALESCE(SUM(rpa.allocated_amount_mxn), 0)  AS total_mxn,
    COALESCE(SUM(rpa.allocated_amount_usd), 0)  AS total_usd,
    MIN(rpa.allocated_amount_mxn)               AS min_allocation_mxn,
    MAX(rpa.allocated_amount_mxn)               AS max_allocation_mxn
FROM report_payment_allocations rpa
WHERE rpa.is_active = TRUE
  AND rpa.payment_date BETWEEN :date_from AND :date_to
  AND rpa.seller_name ILIKE :name_like
GROUP BY rpa.product_type
ORDER BY total_mxn DESC;
"""

# ── 6. Line items summary (quantities only, no revenue) ───────────────────────
RDB_LINE_ITEMS_SUMMARY = """
SELECT
    product_type,
    COUNT(*)                                            AS line_item_count,
    SUM(quantity)                                       AS total_quantity,
    COALESCE(SUM(expected_total_mxn), 0)                AS expected_total_mxn,
    COALESCE(SUM(expected_cost_mxn),  0)                AS expected_cost_mxn,
    MIN(first_payment_date)                             AS earliest_first_payment_date,
    MAX(first_payment_date)                             AS latest_first_payment_date
FROM report_line_items
WHERE is_active = TRUE
  AND payment_status = 'Aprobado'
  AND include_in_product_breakdown = TRUE
  AND first_payment_date BETWEEN :date_from AND :date_to
  AND seller_name ILIKE :name_like
GROUP BY product_type
ORDER BY product_type;
"""

# ── 7. Negative allocations (data quality signal) ─────────────────────────────
#    allocated_amount_mxn < 0 → student entries exceeded payment amount for this product
RDB_NEGATIVE_ALLOCATIONS = """
SELECT
    rpa.payment_id,
    rpa.cart_product_id,
    rpa.product_type,
    rpa.payment_date,
    rpa.allocated_amount,
    rpa.allocated_amount_mxn,
    rpa.allocated_amount_usd,
    rp.amount_mxn   AS payment_total_mxn,
    rp.cart_id,
    rp.school_name
FROM report_payment_allocations rpa
JOIN report_payments rp ON rp.payment_id = rpa.payment_id
WHERE rpa.is_active = TRUE
  AND rpa.payment_date BETWEEN :date_from AND :date_to
  AND rpa.seller_name ILIKE :name_like
  AND rpa.allocated_amount_mxn < 0
ORDER BY rpa.allocated_amount_mxn ASC;
"""


# ══════════════════════════════════════════════════════════════════════════════
# MYSQL QUERIES (source / prod)
# ══════════════════════════════════════════════════════════════════════════════

# ── A. Seller lookup ──────────────────────────────────────────────────────────
MYSQL_SELLER_LOOKUP = """
SELECT s.id AS seller_id, CONCAT(s.name, ' ', s.lastName) AS seller_name
FROM seller s
WHERE CONCAT(s.name, ' ', s.lastName) LIKE :name_like
ORDER BY seller_name, s.id;
"""

# ── B. All approved payments in date range ────────────────────────────────────
MYSQL_PAYMENTS = """
SELECT
    pay.id                                          AS payment_id,
    CASE
        WHEN pay.paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
        THEN pay.paymentDate
        ELSE DATE(pay.createdAt)
    END                                             AS payment_date,
    pay.quantity                                    AS payment_amount,
    pay.status                                      AS payment_status,
    c.id                                            AS cart_id,
    l.id                                            AS lead_id,
    l.name                                          AS school_name,
    l.site                                          AS country,
    z.name                                          AS zone_name
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
LEFT JOIN zone z ON z.id = l.zoneId
WHERE sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND pay.status = 'Aprobado'
  AND CONCAT(s.name, ' ', s.lastName) LIKE :name_like
  AND CASE
        WHEN pay.paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
        THEN pay.paymentDate
        ELSE DATE(pay.createdAt)
      END BETWEEN :date_from AND :date_to
ORDER BY payment_date, pay.id;
"""

# ── C. Cart-product detail for those carts ───────────────────────────────────
#    Shows each cart_product: type, expected amount, and student_payments total.
#    student_paid_total > 0 → that product gets exact student amounts in allocations.
#    student_paid_total = 0 → that product gets remainder (proportional to expected_total).
MYSQL_CART_PRODUCTS = """
SELECT
    cp.id                                               AS cart_product_id,
    c.id                                                AS cart_id,
    p.productType                                       AS product_type,
    COALESCE(ec.name, '(no exam cat)')                  AS exam_cat,
    cp.quantity                                         AS quantity,
    cp.total                                            AS expected_total,
    cp.cost                                             AS expected_cost,
    cp.deletedAt IS NOT NULL                            AS is_deleted,
    COALESCE(sp_agg.student_paid_total, 0)              AS student_paid_total,
    COALESCE(sp_agg.student_count,      0)              AS student_count,
    COALESCE(sp_agg.payment_count,      0)              AS payment_count,
    l.name                                              AS school_name,
    l.site                                              AS country
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN cart_product cp ON cp.cartId = c.id
JOIN product p ON p.id = cp.productId
LEFT JOIN exam_cat ec ON ec.id = p.examId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
LEFT JOIN (
    SELECT
        st.cartProductId                    AS cart_product_id,
        SUM(sp.amount)                      AS student_paid_total,
        COUNT(DISTINCT st.id)               AS student_count,
        COUNT(DISTINCT sp.payment_id)       AS payment_count
    FROM student_payments sp
    JOIN student st ON st.id = sp.student_id
    JOIN payment pay2 ON pay2.id = sp.payment_id
    WHERE pay2.status = 'Aprobado'
    GROUP BY st.cartProductId
) sp_agg ON sp_agg.cart_product_id = cp.id
WHERE sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND pay.status = 'Aprobado'
  AND CONCAT(s.name, ' ', s.lastName) LIKE :name_like
  AND CASE
        WHEN pay.paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
        THEN pay.paymentDate
        ELSE DATE(pay.createdAt)
      END BETWEEN :date_from AND :date_to
ORDER BY c.id, cp.id;
"""

# ── D. Per-payment allocation gap in MySQL ────────────────────────────────────
#    Compares payment.quantity vs SUM(student_payments.amount) per payment.
#    gap > 0  → remainder that gets split proportionally across non-student products
#    gap < 0  → student amounts exceed payment (data entry error → negative allocation)
MYSQL_PAYMENT_ALLOCATION_GAP = """
SELECT
    pay.id                                          AS payment_id,
    CASE
        WHEN pay.paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
        THEN pay.paymentDate
        ELSE DATE(pay.createdAt)
    END                                             AS payment_date,
    pay.quantity                                    AS payment_amount,
    c.id                                            AS cart_id,
    l.name                                          AS school_name,
    l.site                                          AS country,
    COALESCE(SUM(sp.amount), 0)                     AS total_student_allocated,
    pay.quantity - COALESCE(SUM(sp.amount), 0)      AS remainder,
    COUNT(DISTINCT sp.id)                           AS student_payment_rows
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
LEFT JOIN student_payments sp ON sp.payment_id = pay.id
WHERE sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND pay.status = 'Aprobado'
  AND CONCAT(s.name, ' ', s.lastName) LIKE :name_like
  AND CASE
        WHEN pay.paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
        THEN pay.paymentDate
        ELSE DATE(pay.createdAt)
      END BETWEEN :date_from AND :date_to
GROUP BY pay.id, pay.paymentDate, pay.createdAt, pay.quantity, c.id, l.name, l.site
ORDER BY ABS(pay.quantity - COALESCE(SUM(sp.amount), 0)) DESC, payment_date;
"""

# ── E. Payments where student_amounts exceed payment quantity ─────────────────
#    These are the source-side explanation for negative sin_categorizar.
MYSQL_NEGATIVE_REMAINDER = """
SELECT
    pay.id                                          AS payment_id,
    CASE
        WHEN pay.paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
        THEN pay.paymentDate
        ELSE DATE(pay.createdAt)
    END                                             AS payment_date,
    pay.quantity                                    AS payment_amount,
    c.id                                            AS cart_id,
    l.name                                          AS school_name,
    l.site                                          AS country,
    COALESCE(SUM(sp.amount), 0)                     AS total_student_allocated,
    pay.quantity - COALESCE(SUM(sp.amount), 0)      AS remainder,
    COUNT(DISTINCT sp.id)                           AS student_payment_rows
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
LEFT JOIN student_payments sp ON sp.payment_id = pay.id
WHERE sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND pay.status = 'Aprobado'
  AND CONCAT(s.name, ' ', s.lastName) LIKE :name_like
  AND CASE
        WHEN pay.paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
        THEN pay.paymentDate
        ELSE DATE(pay.createdAt)
      END BETWEEN :date_from AND :date_to
GROUP BY pay.id, pay.paymentDate, pay.createdAt, pay.quantity, c.id, l.name, l.site
HAVING pay.quantity - COALESCE(SUM(sp.amount), 0) < 0
ORDER BY remainder ASC;
"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Investigate sin_categorizar anomalies in the por-asesor report."
    )
    parser.add_argument(
        "--seller", required=True, help='Advisor name (partial match OK), e.g. "Fernanda Fraga"'
    )
    parser.add_argument("--date-from", required=True, help="Start date inclusive, YYYY-MM-DD")
    parser.add_argument("--date-to", required=True, help="End date inclusive, YYYY-MM-DD")
    parser.add_argument(
        "--output",
        help="Output JSON path (defaults to tools/output/<slug>-<date_from>-<date_to>.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    date_from = args.date_from
    date_to = args.date_to
    seller = args.seller
    name_like = f"%{seller}%"

    output_path = (
        Path(args.output)
        if args.output
        else Path(__file__).resolve().parent
        / "output"
        / f"{slugify(seller)}-{date_from}-{date_to}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    params = {
        "name_like": name_like,
        "date_from": date_from,
        "date_to": date_to,
    }

    print(f"[1/2] Querying reporting DB (PostgreSQL) for '{seller}' …")
    rdb = reporting_engine()
    with rdb.connect() as conn:
        rdb_seller_lookup = run(conn, RDB_SELLER_LOOKUP, params)
        rdb_summary = run(conn, RDB_SUMMARY, params)
        rdb_payment_gap = run(conn, RDB_PAYMENT_GAP, params)
        rdb_payments_no_alloc = run(conn, RDB_PAYMENTS_WITHOUT_ALLOCATIONS, params)
        rdb_allocation_breakdown = run(conn, RDB_ALLOCATION_BREAKDOWN, params)
        rdb_line_items_summary = run(conn, RDB_LINE_ITEMS_SUMMARY, params)
        rdb_negative_allocations = run(conn, RDB_NEGATIVE_ALLOCATIONS, params)

    print(f"[2/2] Querying MySQL prod for '{seller}' …")
    mysql = mysql_engine()
    with mysql.connect() as conn:
        mysql_seller_lookup = run(conn, MYSQL_SELLER_LOOKUP, params)
        mysql_payments = run(conn, MYSQL_PAYMENTS, params)
        mysql_cart_products = run(conn, MYSQL_CART_PRODUCTS, params)
        mysql_alloc_gap = run(conn, MYSQL_PAYMENT_ALLOCATION_GAP, params)
        mysql_neg_remainder = run(conn, MYSQL_NEGATIVE_REMAINDER, params)

    # ── derived quick-look numbers ────────────────────────────────────────────
    total_mxn = sum(float(r.get("total_revenue_mxn") or 0) for r in rdb_summary)
    allocated_mxn = sum(float(r.get("allocated_mxn") or 0) for r in rdb_summary)
    sin_cat_mxn = sum(float(r.get("sin_categorizar_mxn") or 0) for r in rdb_summary)

    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "environment": settings.env_mode,
            "seller_query": seller,
            "date_from": date_from,
            "date_to": date_to,
            "mysql_host": settings.host,
            "mysql_db": settings.dbname,
            "rdb_host": settings.reporting_db_host,
        },
        "quick_summary": {
            "total_revenue_mxn": total_mxn,
            "allocated_revenue_mxn": allocated_mxn,
            "sin_categorizar_mxn": sin_cat_mxn,
            "is_negative": sin_cat_mxn < 0,
            "is_positive_significant": sin_cat_mxn > 1.0,
            "mysql_payment_count": len(mysql_payments),
            "rdb_payments_no_alloc": len(rdb_payments_no_alloc),
            "rdb_negative_alloc_rows": len(rdb_negative_allocations),
            "mysql_negative_remainder": len(mysql_neg_remainder),
        },
        "reporting_db": {
            "seller_lookup": rdb_seller_lookup,
            "summary_per_seller": rdb_summary,
            "payment_gap_per_payment": rdb_payment_gap,  # ordered by |gap| desc
            "payments_no_allocations": rdb_payments_no_alloc,  # 100% sin_cat payments
            "allocation_breakdown": rdb_allocation_breakdown,  # by product_type
            "line_items_summary": rdb_line_items_summary,
            "negative_allocations": rdb_negative_allocations,  # data quality signal
        },
        "mysql": {
            "seller_lookup": mysql_seller_lookup,
            "payments": mysql_payments,
            "cart_products": mysql_cart_products,  # student_paid_total per cp
            "payment_allocation_gap": mysql_alloc_gap,  # ordered by |remainder| desc
            "negative_remainder_payments": mysql_neg_remainder,  # student > payment amount
        },
    }

    output_path.write_text(json.dumps(make_json_safe(output), indent=2, ensure_ascii=False))

    print()
    print("═" * 60)
    print(f"  Seller query  : {seller}")
    print(f"  Date range    : {date_from} → {date_to}")
    print(f"  Environment   : {settings.env_mode}")
    print()
    print(f"  total_revenue_mxn     : {total_mxn:>14,.2f}")
    print(f"  allocated_revenue_mxn : {allocated_mxn:>14,.2f}")
    flag = (
        "⚠ NEGATIVE" if sin_cat_mxn < -1 else ("⚠ POSITIVE GAP" if sin_cat_mxn > 1 else "✓ clean")
    )
    print(f"  sin_categorizar_mxn   : {sin_cat_mxn:>14,.2f}  {flag}")
    print()
    print(f"  MySQL payments found          : {len(mysql_payments)}")
    print(f"  Payments with NO alloc rows   : {len(rdb_payments_no_alloc)}")
    print(f"  Negative allocation rows (RDB): {len(rdb_negative_allocations)}")
    print(f"  Negative remainder (MySQL)    : {len(mysql_neg_remainder)}")
    print("═" * 60)
    print(f"\n✓ Output written to: {output_path}\n")


if __name__ == "__main__":
    main()
