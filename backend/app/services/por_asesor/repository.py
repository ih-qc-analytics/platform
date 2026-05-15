import base64
import json

from sqlalchemy import text

from app.reporting.database import ReportingSessionLocal
from app.enums import PaymentStatus
from app.schemas.reports import AsesorFilters


# ─────────────────────────────────────────────────────────────
# Cursor helpers (unchanged — same pagination contract)
# ─────────────────────────────────────────────────────────────

def encode_cursor(total_revenue: float, seller_name: str, seller_id: int) -> str:
    payload = {"total_revenue": total_revenue, "seller_name": seller_name, "seller_id": seller_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    padding = "=" * (-len(cursor) % 4)
    payload = json.loads(base64.urlsafe_b64decode((cursor + padding).encode()).decode())
    return {
        "cursor_total_revenue": float(payload["total_revenue"]),
        "cursor_seller_name":   str(payload["seller_name"]),
        "cursor_seller_id":     int(payload["seller_id"]),
    }


# ─────────────────────────────────────────────────────────────
# Internal WHERE builder for report_line_items
# ─────────────────────────────────────────────────────────────

def _base_where(
    filters: AsesorFilters,
    *,
    year: int | None = None,
    seller_id: int | None = None,
) -> tuple[str, dict]:
    """
    Builds WHERE for report_line_items asesor queries.
    Always: is_active, payment_status = Aprobado, year.
    Optionally: geo filters, seller name filter, seller_id filter.
    """
    year_val = year if year is not None else filters.year
    conditions = [
        "is_active = TRUE",
        "payment_status = :payment_status",
        "year = :year",
    ]
    params: dict = {
        "payment_status": PaymentStatus.APROBADO.value,
        "year":           year_val,
    }

    if getattr(filters, "countries", None):
        conditions.append("site = ANY(:countries)")
        params["countries"] = list(filters.countries)
    if getattr(filters, "zones", None):
        conditions.append("zone_name = ANY(:zones)")
        params["zones"] = list(filters.zones)
    if getattr(filters, "states", None):
        conditions.append("state_name = ANY(:states)")
        params["states"] = list(filters.states)
    if getattr(filters, "cities", None):
        conditions.append("city = ANY(:cities)")
        params["cities"] = list(filters.cities)
    if getattr(filters, "sellers", None):
        conditions.append("seller_name = ANY(:sellers)")
        params["sellers"] = list(filters.sellers)
    if seller_id is not None:
        conditions.append("seller_id = :seller_id")
        params["seller_id"] = seller_id

    return " AND ".join(conditions), params


# ─────────────────────────────────────────────────────────────
# Summary queries
# ─────────────────────────────────────────────────────────────

async def fetch_paginated_summary_rows(
    filters: AsesorFilters,
    limit: int,
    cursor: str | None,
) -> tuple[list, bool, str | None]:
    where, params = _base_where(filters)

    cursor_clause = ""
    if cursor:
        cp = decode_cursor(cursor)
        cursor_clause = """
            HAVING
                SUM(total_mxn) < :cursor_total_revenue
                OR (SUM(total_mxn) = :cursor_total_revenue AND MIN(seller_name) > :cursor_seller_name)
                OR (SUM(total_mxn) = :cursor_total_revenue AND MIN(seller_name) = :cursor_seller_name
                    AND seller_id > :cursor_seller_id)
        """
        params.update(cp)

    params["page_size"] = limit + 1

    query = f"""
        SELECT
            seller_id,
            MIN(seller_name)   AS seller_name,
            SUM(total_mxn)     AS total_revenue
        FROM report_line_items
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


async def fetch_summary_exam_breakdown_rows_by_seller_ids(
    seller_ids: list[int],
    filters: AsesorFilters,
) -> list:
    if not seller_ids:
        return []
    where, params = _base_where(filters)
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


# ─────────────────────────────────────────────────────────────
# Presence / metric queries (for ganado/perdido/mantenido)
# ─────────────────────────────────────────────────────────────

async def fetch_school_presence_rows(
    filters: AsesorFilters,
    year: int,
    *,
    seller_id: int | None = None,
) -> list:
    """Returns (seller_id, lead_id) pairs for approved payments in the given year."""
    where, params = _base_where(filters, year=year, seller_id=seller_id)
    query = f"""
        SELECT DISTINCT seller_id, lead_id
        FROM report_line_items
        WHERE {where}
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()


async def fetch_school_metric_rows(
    filters: AsesorFilters,
    year: int,
    *,
    seller_id: int | None = None,
) -> list:
    """Returns (seller_id, lead_id, exams, revenue) per seller-school for the given year."""
    where, params = _base_where(filters, year=year, seller_id=seller_id)
    query = f"""
        SELECT
            seller_id,
            lead_id,
            SUM(quantity)  AS exams,
            SUM(total_mxn) AS revenue
        FROM report_line_items
        WHERE {where}
          AND product_type = 'exam'
        GROUP BY seller_id, lead_id
    """
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(query), params)).fetchall()
