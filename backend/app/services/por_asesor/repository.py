import base64
import json

from sqlalchemy import text

from app.reporting.database import ReportingSessionLocal
from app.schemas.reports import AsesorFilters
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
    year: int | None = None,
    seller_id: int | None = None,
) -> tuple[str, dict]:
    scoped_filters = filters.model_copy(update={"year": year if year is not None else filters.year})
    where, params = build_payment_where_clause(scoped_filters)
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
    year: int | None = None,
    seller_id: int | None = None,
    require_product_breakdown: bool = False,
) -> tuple[str, dict]:
    scoped_filters = filters.model_copy(update={"year": year if year is not None else filters.year})
    where, params = build_line_item_where_clause(
        scoped_filters,
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
) -> tuple[list, bool, str | None]:
    where, params = _payment_where(filters)

    cursor_clause = ""
    if cursor:
        cp = decode_cursor(cursor)
        cursor_clause = """
            HAVING
                SUM(amount_mxn) < :cursor_total_revenue
                OR (SUM(amount_mxn) = :cursor_total_revenue AND MIN(seller_name) > :cursor_seller_name)
                OR (SUM(amount_mxn) = :cursor_total_revenue AND MIN(seller_name) = :cursor_seller_name
                    AND seller_id > :cursor_seller_id)
        """
        params.update(cp)

    params["page_size"] = limit + 1
    query = f"""
        SELECT
            seller_id,
            MIN(seller_name) AS seller_name,
            COALESCE(SUM(amount_mxn), 0) AS total_revenue
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
) -> list:
    if not seller_ids:
        return []
    where, params = _line_where(filters, require_product_breakdown=True)
    params["seller_ids"] = seller_ids
    query = f"""
        SELECT
            seller_id,
            COALESCE(SUM(paid_total_mxn), 0) AS allocated_revenue
        FROM report_line_items
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
    year: int,
    *,
    seller_id: int | None = None,
) -> list:
    where, params = _payment_where(filters, year=year, seller_id=seller_id)
    query = f"""
        SELECT DISTINCT seller_id, lead_id
        FROM report_payments
        WHERE {where}
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_school_allocated_revenue_metric_rows(
    filters: AsesorFilters,
    year: int,
    *,
    seller_id: int | None = None,
) -> list:
    where, params = _line_where(filters, year=year, seller_id=seller_id, require_product_breakdown=True)
    query = f"""
        SELECT
            seller_id,
            lead_id,
            COALESCE(SUM(paid_total_mxn), 0) AS revenue
        FROM report_line_items
        WHERE {where}
        GROUP BY seller_id, lead_id
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_school_exam_metric_rows(
    filters: AsesorFilters,
    year: int,
    *,
    seller_id: int | None = None,
) -> list:
    where, params = _line_where(filters, year=year, seller_id=seller_id, require_product_breakdown=True)
    query = f"""
        SELECT
            seller_id,
            lead_id,
            COALESCE(SUM(CASE WHEN product_type = 'exam' THEN quantity ELSE 0 END), 0) AS exams
        FROM report_line_items
        WHERE {where}
        GROUP BY seller_id, lead_id
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()
