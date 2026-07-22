"""
inspect_sin_categorizar.py
──────────────────────────
Diagnostic tool to investigate "sin categorizar" anomalies in the por-asesor
report.  Queries BOTH the MySQL prod source and the PostgreSQL reporting DB to
cross-reference totals and pinpoint where uncategorized revenue originates.

Two known symptoms:
  1. Huge sin_categorizar  → investigate with --seller "Kena Orozco ..."
  2. Negative sin_categorizar → investigate with --seller "Elvis Gomez ..."

Usage (run from backend/ with ENVIRONMENT=prod in .env):
  python -m tools.inspect_sin_categorizar --seller "Kena Orozco" \
      --date-from 2026-01-01 --date-to 2026-07-19

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

# Exact date expressions mirror app/services/shared.py
# report_payments date:   COALESCE(payment_date, created_at::date)
# report_line_items date: COALESCE(payment_day, payment_date, created_at::date)

# ── 1. Seller lookup in reporting DB ─────────────────────────────────────────
RDB_SELLER_LOOKUP = """
SELECT DISTINCT seller_id, seller_name
FROM report_payments
WHERE seller_name ILIKE :name_like
ORDER BY seller_name, seller_id;
"""

# ── 2. Top-level sin_categorizar summary ─────────────────────────────────────
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
      AND COALESCE(payment_date, created_at::date) BETWEEN :date_from AND :date_to
      AND seller_name ILIKE :name_like
    GROUP BY seller_id
),
line_agg AS (
    SELECT
        seller_id,
        COUNT(*)                                                         AS line_item_count,
        SUM(CASE WHEN include_in_product_breakdown THEN 1 ELSE 0 END)   AS included_count,
        SUM(CASE WHEN NOT include_in_product_breakdown THEN 1 ELSE 0 END) AS excluded_count,
        COALESCE(SUM(CASE WHEN include_in_product_breakdown THEN paid_total_mxn ELSE 0 END),0)
                                                                         AS allocated_mxn,
        COALESCE(SUM(CASE WHEN include_in_product_breakdown THEN paid_total_usd ELSE 0 END),0)
                                                                         AS allocated_usd,
        COALESCE(SUM(CASE WHEN NOT include_in_product_breakdown THEN expected_total_mxn ELSE 0 END),0)
                                                                         AS excluded_expected_mxn
    FROM report_line_items
    WHERE is_active = TRUE
      AND payment_status = 'Aprobado'
      AND COALESCE(payment_day, payment_date, created_at::date) BETWEEN :date_from AND :date_to
      AND seller_name ILIKE :name_like
    GROUP BY seller_id
)
SELECT
    p.seller_id,
    p.seller_name,
    p.payment_count,
    p.total_revenue_mxn,
    p.total_revenue_usd,
    p.total_revenue_base,
    COALESCE(l.line_item_count,  0) AS line_item_count,
    COALESCE(l.included_count,   0) AS included_count,
    COALESCE(l.excluded_count,   0) AS excluded_count,
    COALESCE(l.allocated_mxn,    0) AS allocated_mxn,
    COALESCE(l.allocated_usd,    0) AS allocated_usd,
    p.total_revenue_mxn - COALESCE(l.allocated_mxn, 0) AS sin_categorizar_mxn,
    p.total_revenue_usd - COALESCE(l.allocated_usd, 0) AS sin_categorizar_usd,
    COALESCE(l.excluded_expected_mxn, 0) AS excluded_items_expected_mxn
FROM pay_agg p
LEFT JOIN line_agg l ON l.seller_id = p.seller_id
ORDER BY p.seller_name;
"""

# ── 3. Line items breakdown by (include_in_product_breakdown, product_type) ──
RDB_LINE_ITEMS_BREAKDOWN = """
SELECT
    include_in_product_breakdown,
    product_type,
    COUNT(*)                            AS count,
    COALESCE(SUM(paid_total_mxn),  0)  AS paid_total_mxn,
    COALESCE(SUM(paid_total_usd),  0)  AS paid_total_usd,
    COALESCE(SUM(expected_total_mxn),0) AS expected_total_mxn
FROM report_line_items
WHERE is_active = TRUE
  AND payment_status = 'Aprobado'
  AND COALESCE(payment_day, payment_date, created_at::date) BETWEEN :date_from AND :date_to
  AND seller_name ILIKE :name_like
GROUP BY include_in_product_breakdown, product_type
ORDER BY include_in_product_breakdown DESC, product_type;
"""

# ── 4. Excluded line items detail (include_in_product_breakdown = FALSE) ─────
#    These are the items that SHOULD contribute to allocated_revenue but don't
#    because paid_total = 0.  Their expected_total_mxn flows straight into
#    sin_categorizar.
RDB_EXCLUDED_LINE_ITEMS = """
SELECT
    cart_product_id,
    cart_id,
    product_type,
    exam_category,
    exam_canonical_name,
    school_name,
    site,
    COALESCE(payment_day, payment_date, created_at::date) AS effective_date,
    payment_date,
    payment_day,
    paid_total,
    paid_total_mxn,
    paid_total_usd,
    expected_total,
    expected_total_mxn,
    student_count,
    payment_count,
    year,
    month,
    base_currency
FROM report_line_items
WHERE is_active = TRUE
  AND payment_status = 'Aprobado'
  AND include_in_product_breakdown = FALSE
  AND COALESCE(payment_day, payment_date, created_at::date) BETWEEN :date_from AND :date_to
  AND seller_name ILIKE :name_like
ORDER BY effective_date, cart_id, cart_product_id;
"""

# ── 5. report_payments with no matching report_line_items at all ──────────────
#    If a cart has zero line items (not even excluded ones) the entire payment
#    becomes sin_categorizar.
RDB_PAYMENTS_WITHOUT_LINE_ITEMS = """
SELECT
    rp.payment_id,
    rp.cart_id,
    rp.school_name,
    rp.site,
    COALESCE(rp.payment_date, rp.created_at::date) AS effective_date,
    rp.amount,
    rp.amount_mxn,
    rp.amount_usd,
    rp.base_currency,
    rp.year,
    rp.month
FROM report_payments rp
WHERE rp.is_active = TRUE
  AND rp.payment_status = 'Aprobado'
  AND COALESCE(rp.payment_date, rp.created_at::date) BETWEEN :date_from AND :date_to
  AND rp.seller_name ILIKE :name_like
  AND NOT EXISTS (
      SELECT 1 FROM report_line_items rli
      WHERE rli.cart_id = rp.cart_id
        AND rli.is_active = TRUE
        AND rli.seller_name ILIKE :name_like
  )
ORDER BY effective_date, rp.cart_id;
"""

# ── 6. Per-payment gap: report_payments vs sum of included line items ─────────
RDB_PAYMENT_GAP = """
SELECT
    rp.payment_id,
    rp.cart_id,
    rp.school_name,
    rp.site,
    COALESCE(rp.payment_date, rp.created_at::date) AS effective_date,
    rp.amount_mxn                                   AS payment_mxn,
    rp.amount_usd                                   AS payment_usd,
    rp.base_currency,
    COALESCE(li_agg.allocated_mxn, 0)               AS allocated_mxn,
    COALESCE(li_agg.allocated_usd, 0)               AS allocated_usd,
    rp.amount_mxn - COALESCE(li_agg.allocated_mxn, 0) AS gap_mxn,
    rp.amount_usd - COALESCE(li_agg.allocated_usd, 0) AS gap_usd,
    COALESCE(li_agg.included_items, 0)              AS included_items,
    COALESCE(li_agg.excluded_items, 0)              AS excluded_items
FROM report_payments rp
LEFT JOIN (
    SELECT
        cart_id,
        SUM(CASE WHEN include_in_product_breakdown THEN paid_total_mxn ELSE 0 END) AS allocated_mxn,
        SUM(CASE WHEN include_in_product_breakdown THEN paid_total_usd ELSE 0 END) AS allocated_usd,
        SUM(CASE WHEN include_in_product_breakdown THEN 1 ELSE 0 END)              AS included_items,
        SUM(CASE WHEN NOT include_in_product_breakdown THEN 1 ELSE 0 END)          AS excluded_items
    FROM report_line_items
    WHERE is_active = TRUE
      AND payment_status = 'Aprobado'
      AND seller_name ILIKE :name_like
    GROUP BY cart_id
) li_agg ON li_agg.cart_id = rp.cart_id
WHERE rp.is_active = TRUE
  AND rp.payment_status = 'Aprobado'
  AND COALESCE(rp.payment_date, rp.created_at::date) BETWEEN :date_from AND :date_to
  AND rp.seller_name ILIKE :name_like
ORDER BY ABS(rp.amount_mxn - COALESCE(li_agg.allocated_mxn, 0)) DESC, effective_date;
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
    COALESCE(pay.paymentDate, DATE(pay.createdAt)) AS payment_day,
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
  AND COALESCE(pay.paymentDate, DATE(pay.createdAt)) BETWEEN :date_from AND :date_to
ORDER BY payment_day, pay.id;
"""

# ── C. Cart-product detail for those carts ───────────────────────────────────
#    Shows for each cart_product: what type it is, what was expected, and
#    how much was actually allocated via student_payments.
#    Products with student_paid_total = 0 will get include_in_product_breakdown
#    = FALSE in the reporting DB → they feed sin_categorizar.
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
    CASE
        WHEN p.productType = 'exam'
        THEN COALESCE(sp_agg.student_paid_total, 0) > 0
        ELSE NULL
    END                                                 AS would_include_if_exam,
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
  AND COALESCE(pay.paymentDate, DATE(pay.createdAt)) BETWEEN :date_from AND :date_to
ORDER BY c.id, cp.id;
"""

# ── D. Payments with ZERO student_payment rows ────────────────────────────────
#    For exam products, if there are no student_payments entries, paid_total
#    stays 0 → include_in_product_breakdown = FALSE.
MYSQL_PAYMENTS_NO_STUDENT_PAYMENTS = """
SELECT
    pay.id                                          AS payment_id,
    COALESCE(pay.paymentDate, DATE(pay.createdAt)) AS payment_day,
    pay.quantity                                    AS payment_amount,
    c.id                                            AS cart_id,
    l.name                                          AS school_name,
    l.site                                          AS country,
    COUNT(DISTINCT cp.id)                           AS cart_product_count,
    COUNT(DISTINCT sp.id)                           AS student_payment_rows
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
LEFT JOIN cart_product cp ON cp.cartId = c.id AND cp.deletedAt IS NULL
LEFT JOIN student_payments sp ON sp.payment_id = pay.id
WHERE sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND pay.status = 'Aprobado'
  AND CONCAT(s.name, ' ', s.lastName) LIKE :name_like
  AND COALESCE(pay.paymentDate, DATE(pay.createdAt)) BETWEEN :date_from AND :date_to
GROUP BY pay.id, payment_day, pay.quantity, c.id, l.name, l.site
HAVING COUNT(DISTINCT sp.id) = 0
ORDER BY payment_day, pay.id;
"""

# ── E. Per-payment allocation gap in MySQL ────────────────────────────────────
#    How much of each payment is covered by student_payments vs how much is
#    left unaccounted.  Unaccounted portion → sin_categorizar.
MYSQL_PAYMENT_ALLOCATION_GAP = """
SELECT
    pay.id                                          AS payment_id,
    COALESCE(pay.paymentDate, DATE(pay.createdAt)) AS payment_day,
    pay.quantity                                    AS payment_amount,
    c.id                                            AS cart_id,
    l.name                                          AS school_name,
    l.site                                          AS country,
    COALESCE(SUM(sp.amount), 0)                    AS total_student_allocated,
    pay.quantity - COALESCE(SUM(sp.amount), 0)     AS unallocated_gap,
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
  AND COALESCE(pay.paymentDate, DATE(pay.createdAt)) BETWEEN :date_from AND :date_to
GROUP BY pay.id, payment_day, pay.quantity, c.id, l.name, l.site
ORDER BY ABS(pay.quantity - COALESCE(SUM(sp.amount), 0)) DESC, payment_day;
"""

# ── F. Proportional allocation check (non-exam products) ─────────────────────
#    For books/courses the ETL uses proportional allocation, not student_payments.
#    This shows how much each non-exam cart_product would receive via allocation.
MYSQL_PROPORTIONAL_ALLOCATION = """
SELECT
    cp.id                                               AS cart_product_id,
    c.id                                                AS cart_id,
    p.productType                                       AS product_type,
    cp.quantity                                         AS quantity,
    cp.total                                            AS cp_expected_total,
    ct.cart_total                                       AS cart_total,
    pay.id                                              AS payment_id,
    COALESCE(pay.paymentDate, DATE(pay.createdAt))     AS payment_day,
    pay.quantity                                        AS payment_amount,
    ROUND(pay.quantity * cp.total / NULLIF(ct.cart_total, 0), 2) AS proportional_allocation,
    l.name                                              AS school_name,
    l.site                                              AS country
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN cart_product cp ON cp.cartId = c.id AND cp.deletedAt IS NULL
JOIN product p ON p.id = cp.productId
JOIN seller_lead sl ON sl.id = c.sellerLeadId
JOIN seller s ON s.id = sl.sellerId
JOIN `lead` l ON l.id = sl.leadId
JOIN (
    SELECT cartId, SUM(total) AS cart_total
    FROM cart_product
    WHERE deletedAt IS NULL
    GROUP BY cartId
) ct ON ct.cartId = c.id
WHERE sl.deletedAt IS NULL
  AND l.deletedAt IS NULL
  AND c.deletedAt IS NULL
  AND pay.status = 'Aprobado'
  AND p.productType IN ('book', 'course')
  AND CONCAT(s.name, ' ', s.lastName) LIKE :name_like
  AND COALESCE(pay.paymentDate, DATE(pay.createdAt)) BETWEEN :date_from AND :date_to
ORDER BY c.id, cp.id, payment_day;
"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Investigate sin_categorizar anomalies in the por-asesor report."
    )
    parser.add_argument(
        "--seller", required=True,
        help='Advisor name (partial match OK), e.g. "Kena Orozco"'
    )
    parser.add_argument(
        "--date-from", required=True,
        help="Start date inclusive, YYYY-MM-DD"
    )
    parser.add_argument(
        "--date-to", required=True,
        help="End date inclusive, YYYY-MM-DD"
    )
    parser.add_argument(
        "--output",
        help="Output JSON path (defaults to tools/output/<slug>-<date_from>-<date_to>.json)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    date_from = args.date_from
    date_to = args.date_to
    seller = args.seller
    name_like = f"%{seller}%"

    output_path = (
        Path(args.output) if args.output
        else Path(__file__).resolve().parent / "output"
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
        rdb_seller_lookup       = run(conn, RDB_SELLER_LOOKUP, params)
        rdb_summary             = run(conn, RDB_SUMMARY, params)
        rdb_line_items_breakdown= run(conn, RDB_LINE_ITEMS_BREAKDOWN, params)
        rdb_excluded_items      = run(conn, RDB_EXCLUDED_LINE_ITEMS, params)
        rdb_payments_no_lines   = run(conn, RDB_PAYMENTS_WITHOUT_LINE_ITEMS, params)
        rdb_payment_gap         = run(conn, RDB_PAYMENT_GAP, params)

    print(f"[2/2] Querying MySQL prod for '{seller}' …")
    mysql = mysql_engine()
    with mysql.connect() as conn:
        mysql_seller_lookup   = run(conn, MYSQL_SELLER_LOOKUP, params)
        mysql_payments        = run(conn, MYSQL_PAYMENTS, params)
        mysql_cart_products   = run(conn, MYSQL_CART_PRODUCTS, params)
        mysql_no_sp           = run(conn, MYSQL_PAYMENTS_NO_STUDENT_PAYMENTS, params)
        mysql_alloc_gap       = run(conn, MYSQL_PAYMENT_ALLOCATION_GAP, params)
        mysql_proportional    = run(conn, MYSQL_PROPORTIONAL_ALLOCATION, params)

    # ── derived quick-look numbers ────────────────────────────────────────────
    total_mxn      = sum(float(r.get("total_revenue_mxn") or 0) for r in rdb_summary)
    allocated_mxn  = sum(float(r.get("allocated_mxn")     or 0) for r in rdb_summary)
    sin_cat_mxn    = sum(float(r.get("sin_categorizar_mxn") or 0) for r in rdb_summary)
    total_usd      = sum(float(r.get("total_revenue_usd") or 0) for r in rdb_summary)
    allocated_usd  = sum(float(r.get("allocated_usd")     or 0) for r in rdb_summary)
    sin_cat_usd    = sum(float(r.get("sin_categorizar_usd") or 0) for r in rdb_summary)

    output = {
        "metadata": {
            "generated_at"  : datetime.now().isoformat(timespec="seconds"),
            "environment"   : settings.env_mode,
            "seller_query"  : seller,
            "date_from"     : date_from,
            "date_to"       : date_to,
            "mysql_host"    : settings.host,
            "mysql_db"      : settings.dbname,
            "rdb_host"      : settings.reporting_db_host,
        },

        # ── Quick diagnosis summary ───────────────────────────────────────────
        "quick_summary": {
            "total_revenue_mxn"    : total_mxn,
            "allocated_revenue_mxn": allocated_mxn,
            "sin_categorizar_mxn"  : sin_cat_mxn,
            "total_revenue_usd"    : total_usd,
            "allocated_revenue_usd": allocated_usd,
            "sin_categorizar_usd"  : sin_cat_usd,
            "is_negative"          : sin_cat_mxn < 0,
            "mysql_payment_count"  : len(mysql_payments),
            "rdb_excluded_items"   : len(rdb_excluded_items),
            "rdb_payments_no_lines": len(rdb_payments_no_lines),
            "mysql_payments_no_sp" : len(mysql_no_sp),
        },

        # ── Reporting DB results ──────────────────────────────────────────────
        "reporting_db": {
            "seller_lookup"            : rdb_seller_lookup,
            "summary_per_seller"       : rdb_summary,
            "line_items_breakdown"     : rdb_line_items_breakdown,
            "excluded_line_items"      : rdb_excluded_items,       # paid_total=0 items
            "payments_with_no_lines"   : rdb_payments_no_lines,    # 100% sin_cat payments
            "payment_gap_per_payment"  : rdb_payment_gap,          # ordered by gap desc
        },

        # ── MySQL / source DB results ─────────────────────────────────────────
        "mysql": {
            "seller_lookup"            : mysql_seller_lookup,
            "payments"                 : mysql_payments,
            "cart_products"            : mysql_cart_products,       # incl. deleted flag & student_paid_total
            "payments_with_no_student_payments": mysql_no_sp,
            "payment_allocation_gap"   : mysql_alloc_gap,           # ordered by gap desc
            "proportional_allocation"  : mysql_proportional,        # books/courses non-exam
        },
    }

    output_path.write_text(
        json.dumps(make_json_safe(output), indent=2, ensure_ascii=False)
    )

    print()
    print("═" * 60)
    print(f"  Seller query  : {seller}")
    print(f"  Date range    : {date_from} → {date_to}")
    print(f"  Environment   : {settings.env_mode}")
    print()
    print(f"  total_revenue_mxn     : {total_mxn:>12,.2f}")
    print(f"  allocated_revenue_mxn : {allocated_mxn:>12,.2f}")
    print(f"  sin_categorizar_mxn   : {sin_cat_mxn:>12,.2f}  {'⚠ NEGATIVE' if sin_cat_mxn < 0 else ''}")
    print()
    print(f"  MySQL payments found        : {len(mysql_payments)}")
    print(f"  Reporting DB excluded items : {len(rdb_excluded_items)}  (paid_total=0)")
    print(f"  Payments with NO line items : {len(rdb_payments_no_lines)}")
    print(f"  MySQL payments w/ no sp rows: {len(mysql_no_sp)}")
    print("═" * 60)
    print(f"\n✓ Output written to: {output_path}\n")


if __name__ == "__main__":
    main()
