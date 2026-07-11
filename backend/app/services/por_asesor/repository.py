import base64
import json

from sqlalchemy import text

from app.enums import BaseCurrency
from app.reporting.database import ReportingSessionLocal
from app.schemas.reports import AsesorFilters
from app.services.utils.report_currency import (
    line_expected_cost_column,
    line_expected_total_column,
    line_paid_total_column,
    payment_amount_column,
)
from app.services.shared import build_line_item_where_clause, build_payment_where_clause

# Whitelist — only these strings ever reach SQL interpolation
SORTABLE_COLUMNS: dict[str, str] = {
    "seller_name": "seller_name",
    "total_revenue": "total_revenue",
    "allocated_revenue": "allocated_revenue",
    "expected_revenue": "expected_revenue",
    "expected_cost": "expected_cost",
    "profit_margin": "profit_margin",
}


def encode_cursor(sort_by: str, sort_dir: str, sort_value, seller_name: str, seller_id: int) -> str:
    payload = {
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "sort_value": sort_value,
        "seller_name": seller_name,
        "seller_id": seller_id,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    padding = "=" * (-len(cursor) % 4)
    payload = json.loads(base64.urlsafe_b64decode((cursor + padding).encode()).decode())
    return {
        "cursor_sort_by": str(payload["sort_by"]),
        "cursor_sort_dir": str(payload["sort_dir"]),
        "cursor_sort_value": payload["sort_value"],
        "cursor_seller_name": str(payload["seller_name"]),
        "cursor_seller_id": int(payload["seller_id"]),
    }


def _payment_where(
    filters: AsesorFilters,
    *,
    seller_id: int | None = None,
) -> tuple[str, dict]:
    where, params = build_payment_where_clause(filters)
    if getattr(filters, "sellers", None):
        where += " AND seller_name = ANY(:sellers)"
        params["sellers"] = list(filters.sellers)
    if seller_id is not None:
        where += " AND seller_id = :seller_id"
        params["seller_id"] = seller_id
    return where, params


def _line_where(
    filters: AsesorFilters,
    *,
    seller_id: int | None = None,
    require_product_breakdown: bool = False,
) -> tuple[str, dict]:
    where, params = build_line_item_where_clause(
        filters,
        require_product_breakdown=require_product_breakdown,
    )
    if getattr(filters, "sellers", None):
        where += " AND seller_name = ANY(:sellers)"
        params["sellers"] = list(filters.sellers)
    if seller_id is not None:
        where += " AND seller_id = :seller_id"
        params["seller_id"] = seller_id
    return where, params


def _build_cte_query(
    payment_where: str,
    line_where: str,
    payment_amount: str,
    paid_total: str,
    expected_cost: str,
    expected_total: str,
    *,
    cursor_clause: str = "",
    sort_col: str = "total_revenue",
    sort_dir_sql: str = "DESC",
    limit_clause: str = "",
    seller_ids_clause: str = "",
) -> str:
    return f"""
        WITH payment_agg AS (
            SELECT
                seller_id,
                MIN(seller_name)                   AS seller_name,
                COALESCE(SUM({payment_amount}), 0) AS total_revenue
            FROM report_payments
            WHERE {payment_where}
            {seller_ids_clause}
            GROUP BY seller_id
        ),
        line_agg AS (
            SELECT
                seller_id,
                COALESCE(SUM({paid_total}), 0)                                                    AS allocated_revenue,
                COALESCE(SUM(CASE WHEN product_type = 'exam'   THEN {paid_total} ELSE 0 END), 0)  AS exam_revenue,
                COALESCE(SUM(CASE WHEN product_type = 'book'   THEN {paid_total} ELSE 0 END), 0)  AS book_revenue,
                COALESCE(SUM(CASE WHEN product_type = 'course' THEN {paid_total} ELSE 0 END), 0)  AS course_revenue,
                COALESCE(SUM(CASE WHEN product_type = 'book'   THEN quantity     ELSE 0 END), 0)  AS total_books,
                COALESCE(SUM(CASE WHEN product_type = 'course' THEN quantity     ELSE 0 END), 0)  AS total_courses,
                COALESCE(SUM({expected_cost}), 0)                                                 AS expected_cost,
                COALESCE(SUM({expected_total}), 0)                                                AS expected_revenue
            FROM report_line_items
            WHERE {line_where}
              AND include_in_product_breakdown = TRUE
            {seller_ids_clause}
            GROUP BY seller_id
        ),
        combined AS (
            SELECT
                p.seller_id,
                p.seller_name,
                p.total_revenue,
                COALESCE(li.allocated_revenue, 0) AS allocated_revenue,
                COALESCE(li.exam_revenue,      0) AS exam_revenue,
                COALESCE(li.book_revenue,      0) AS book_revenue,
                COALESCE(li.course_revenue,    0) AS course_revenue,
                COALESCE(li.total_books,       0) AS total_books,
                COALESCE(li.total_courses,     0) AS total_courses,
                COALESCE(li.expected_cost,     0) AS expected_cost,
                COALESCE(li.expected_revenue,  0) AS expected_revenue,
                CASE
                    WHEN COALESCE(li.allocated_revenue, 0) > 0
                    THEN (COALESCE(li.allocated_revenue, 0) - COALESCE(li.expected_cost, 0))
                         / li.allocated_revenue * 100
                    ELSE 0
                END AS profit_margin
            FROM payment_agg p
            LEFT JOIN line_agg li ON li.seller_id = p.seller_id
        )
        SELECT * FROM combined
        {cursor_clause}
        ORDER BY {sort_col} {sort_dir_sql}, seller_name ASC, seller_id ASC
        {limit_clause}
    """


async def fetch_paginated_summary_rows(
    filters: AsesorFilters,
    limit: int,
    cursor: str | None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> tuple[list, bool, str | None]:
    payment_where, params = _payment_where(filters)
    line_where, line_params = _line_where(filters, require_product_breakdown=True)
    # Merge params — both WHERE clauses use identical filter keys/values
    params.update(line_params)

    payment_amount = payment_amount_column(base_currency)
    paid_total = line_paid_total_column(base_currency)
    expected_cost_col = line_expected_cost_column(base_currency)
    expected_total_col = line_expected_total_column(base_currency)

    sort_by = filters.sort_by if filters.sort_by in SORTABLE_COLUMNS else "total_revenue"
    sort_dir = filters.sort_dir if filters.sort_dir in ("asc", "desc") else "desc"
    sort_col = SORTABLE_COLUMNS[sort_by]
    sort_dir_sql = sort_dir.upper()

    cursor_clause = ""
    if cursor:
        cp = decode_cursor(cursor)
        cv = cp["cursor_sort_value"]
        csn = cp["cursor_seller_name"]
        csi = cp["cursor_seller_id"]
        params["cursor_sort_value"] = cv
        params["cursor_seller_name"] = csn
        params["cursor_seller_id"] = csi
        cmp_op = "<" if sort_dir == "desc" else ">"
        cursor_clause = f"""
            WHERE {sort_col} {cmp_op} :cursor_sort_value
               OR ({sort_col} = :cursor_sort_value AND seller_name > :cursor_seller_name)
               OR ({sort_col} = :cursor_sort_value AND seller_name = :cursor_seller_name
                   AND seller_id > :cursor_seller_id)
        """

    params["page_size"] = limit + 1
    query = _build_cte_query(
        payment_where,
        line_where,
        payment_amount,
        paid_total,
        expected_cost_col,
        expected_total_col,
        cursor_clause=cursor_clause,
        sort_col=sort_col,
        sort_dir_sql=sort_dir_sql,
        limit_clause="LIMIT :page_size",
    )

    async with ReportingSessionLocal() as session:
        rows = (await session.execute(text(query), params)).fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        sort_value = getattr(last, sort_col, None)
        # Normalize: strings for seller_name, floats for all numeric columns (Decimal not JSON-safe)
        if sort_by == "seller_name":
            sort_value = str(sort_value) if sort_value is not None else ""
        else:
            sort_value = float(sort_value) if sort_value is not None else 0.0
        next_cursor = encode_cursor(
            sort_by=sort_by,
            sort_dir=sort_dir,
            sort_value=sort_value,
            seller_name=last.seller_name,
            seller_id=int(last.seller_id),
        )
    return page_rows, has_more, next_cursor


async def fetch_comparison_rows_by_seller_ids(
    seller_ids: list[int],
    filters: AsesorFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> list:
    """Replaces both fetch_summary_rows_by_seller_ids and
    fetch_summary_allocated_revenue_rows_by_seller_ids for the comparison path.
    Returns one row per seller with all aggregated metrics."""
    if not seller_ids:
        return []
    payment_where, params = _payment_where(filters)
    line_where, line_params = _line_where(filters, require_product_breakdown=True)
    params.update(line_params)
    params["seller_ids"] = seller_ids

    payment_amount = payment_amount_column(base_currency)
    paid_total = line_paid_total_column(base_currency)
    expected_cost_col = line_expected_cost_column(base_currency)
    expected_total_col = line_expected_total_column(base_currency)

    query = _build_cte_query(
        payment_where,
        line_where,
        payment_amount,
        paid_total,
        expected_cost_col,
        expected_total_col,
        seller_ids_clause="AND seller_id = ANY(:seller_ids)",
        sort_col="total_revenue",
        sort_dir_sql="DESC",
    )

    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_summary_exam_breakdown_rows_by_seller_ids(
    seller_ids: list[int],
    filters: AsesorFilters,
) -> list:
    if not seller_ids:
        return []
    where, params = _line_where(filters, require_product_breakdown=True)
    params["seller_ids"] = seller_ids
    query = f"""
        SELECT
            seller_id,
            exam_category,
            SUM(quantity) AS exam_count
        FROM report_line_items
        WHERE {where}
          AND seller_id = ANY(:seller_ids)
          AND product_type = 'exam'
        GROUP BY seller_id, exam_category
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_school_presence_rows(
    filters: AsesorFilters,
    *,
    seller_id: int | None = None,
) -> list:
    where, params = _payment_where(filters, seller_id=seller_id)
    query = f"""
        SELECT DISTINCT seller_id, lead_id
        FROM report_payments
        WHERE {where}
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_books_courses_presence_rows(
    filters: AsesorFilters,
    *,
    seller_id: int | None = None,
) -> list:
    where, params = _line_where(filters, seller_id=seller_id, require_product_breakdown=True)
    query = f"""
        SELECT DISTINCT seller_id, lead_id
        FROM report_line_items
        WHERE product_type IN ('book', 'course')
          AND {where}
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_school_allocated_revenue_metric_rows(
    filters: AsesorFilters,
    *,
    seller_id: int | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> list:
    where, params = _line_where(filters, seller_id=seller_id, require_product_breakdown=True)
    paid_total = line_paid_total_column(base_currency)
    query = f"""
        SELECT
            seller_id,
            lead_id,
            COALESCE(SUM({paid_total}), 0) AS revenue
        FROM report_line_items
        WHERE {where}
        GROUP BY seller_id, lead_id
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_school_product_metric_rows(
    filters: AsesorFilters,
    *,
    seller_id: int | None = None,
) -> list:
    where, params = _line_where(filters, seller_id=seller_id, require_product_breakdown=True)
    query = f"""
        SELECT
            seller_id,
            lead_id,
            COALESCE(SUM(CASE WHEN product_type = 'exam'   THEN quantity ELSE 0 END), 0) AS exams,
            COALESCE(SUM(CASE WHEN product_type = 'book'   THEN quantity ELSE 0 END), 0) AS books,
            COALESCE(SUM(CASE WHEN product_type = 'course' THEN quantity ELSE 0 END), 0) AS courses
        FROM report_line_items
        WHERE {where}
        GROUP BY seller_id, lead_id
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_detail_exam_breakdown_rows(
    seller_id: int,
    filters: AsesorFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> list:
    where, params = _line_where(filters, seller_id=seller_id, require_product_breakdown=True)
    paid_total = line_paid_total_column(base_currency)
    query = f"""
        SELECT
            exam_category,
            SUM(quantity) AS exams,
            COUNT(DISTINCT lead_id) AS schools,
            SUM({paid_total}) AS revenue
        FROM report_line_items
        WHERE {where}
          AND product_type = 'exam'
        GROUP BY exam_category
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()
