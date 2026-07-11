import base64
import json

from sqlalchemy import text

from app.enums import BaseCurrency
from app.reporting.database import ReportingSessionLocal
from app.schemas.reports import AsesorFilters
from app.services.utils.report_currency import line_paid_total_column, payment_amount_column
from app.services.shared import build_line_item_where_clause, build_payment_where_clause


def encode_cursor(total_revenue: float, seller_name: str, seller_id: int) -> str:
    payload = {"total_revenue": total_revenue, "seller_name": seller_name, "seller_id": seller_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    padding = "=" * (-len(cursor) % 4)
    payload = json.loads(base64.urlsafe_b64decode((cursor + padding).encode()).decode())
    return {
        "cursor_total_revenue": float(payload["total_revenue"]),
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


async def fetch_paginated_summary_rows(
    filters: AsesorFilters,
    limit: int,
    cursor: str | None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> tuple[list, bool, str | None]:
    where, params = _payment_where(filters)
    payment_amount = payment_amount_column(base_currency)

    cursor_clause = ""
    if cursor:
        cp = decode_cursor(cursor)
        cursor_clause = f"""
            HAVING
                SUM({payment_amount}) < :cursor_total_revenue
                OR (SUM({payment_amount}) = :cursor_total_revenue AND MIN(seller_name) > :cursor_seller_name)
                OR (SUM({payment_amount}) = :cursor_total_revenue AND MIN(seller_name) = :cursor_seller_name
                    AND seller_id > :cursor_seller_id)
        """
        params.update(cp)

    params["page_size"] = limit + 1
    query = f"""
        SELECT
            seller_id,
            MIN(seller_name) AS seller_name,
            COALESCE(SUM({payment_amount}), 0) AS total_revenue
        FROM report_payments
        WHERE {where}
        GROUP BY seller_id
        {cursor_clause}
        ORDER BY total_revenue DESC, seller_name ASC, seller_id ASC
        LIMIT :page_size
    """
    async with ReportingSessionLocal() as session:
        rows = (await session.execute(text(query), params)).fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = encode_cursor(
            total_revenue=float(last.total_revenue or 0),
            seller_name=last.seller_name,
            seller_id=int(last.seller_id),
        )
    return page_rows, has_more, next_cursor


async def fetch_summary_allocated_revenue_rows_by_seller_ids(
    seller_ids: list[int],
    filters: AsesorFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> list:
    if not seller_ids:
        return []
    where, params = _line_where(filters, require_product_breakdown=True)
    params["seller_ids"] = seller_ids
    paid_total = line_paid_total_column(base_currency)
    query = f"""
        SELECT
            seller_id,
            COALESCE(SUM({paid_total}), 0)                                                    AS allocated_revenue,
            COALESCE(SUM(CASE WHEN product_type = 'exam'   THEN {paid_total} ELSE 0 END), 0)  AS exam_revenue,
            COALESCE(SUM(CASE WHEN product_type = 'book'   THEN {paid_total} ELSE 0 END), 0)  AS book_revenue,
            COALESCE(SUM(CASE WHEN product_type = 'course' THEN {paid_total} ELSE 0 END), 0)  AS course_revenue,
            COALESCE(SUM(CASE WHEN product_type = 'book'   THEN quantity     ELSE 0 END), 0)  AS total_books,
            COALESCE(SUM(CASE WHEN product_type = 'course' THEN quantity     ELSE 0 END), 0)  AS total_courses
        FROM report_line_items
        WHERE {where}
          AND seller_id = ANY(:seller_ids)
        GROUP BY seller_id
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_summary_rows_by_seller_ids(
    seller_ids: list[int],
    filters: AsesorFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> list:
    if not seller_ids:
        return []
    where, params = _payment_where(filters)
    params["seller_ids"] = seller_ids
    payment_amount = payment_amount_column(base_currency)
    query = f"""
        SELECT
            seller_id,
            MIN(seller_name) AS seller_name,
            COALESCE(SUM({payment_amount}), 0) AS total_revenue
        FROM report_payments
        WHERE {where}
          AND seller_id = ANY(:seller_ids)
        GROUP BY seller_id
    """
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
