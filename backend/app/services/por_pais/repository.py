from app.enums import BaseCurrency
from sqlalchemy import text

from app.reporting.database import ReportingSessionLocal
from app.schemas.reports import PorPaisFilters
from app.services.utils.report_currency import alloc_amount_column, payment_amount_column
from app.services.shared import (
    build_alloc_where_clause,
    build_line_item_where_clause,
    build_payment_where_clause,
)


def _payment_where(filters: PorPaisFilters) -> tuple[str, dict]:
    return build_payment_where_clause(filters)


def _line_where(
    filters: PorPaisFilters, *, require_product_breakdown: bool = False
) -> tuple[str, dict]:
    return build_line_item_where_clause(
        filters, require_product_breakdown=require_product_breakdown
    )


def _alloc_where(filters: PorPaisFilters) -> tuple[str, dict]:
    return build_alloc_where_clause(filters)


async def fetch_country_payment_rows(
    filters: PorPaisFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> list:
    where, params = _payment_where(filters)
    payment_amount = payment_amount_column(base_currency)
    async with ReportingSessionLocal() as session:
        return (
            await session.execute(
                text(f"""
            SELECT
                site AS country,
                COUNT(DISTINCT lead_id) AS total_schools,
                COALESCE(SUM({payment_amount}), 0) AS total_revenue
            FROM report_payments
            WHERE {where} AND site IS NOT NULL
            GROUP BY site
            ORDER BY site ASC
        """),
                params,
            )
        ).fetchall()


async def fetch_country_allocated_revenue_rows(
    filters: PorPaisFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> list:
    alloc_where, params = _alloc_where(filters)
    line_where, line_params = _line_where(filters, require_product_breakdown=True)
    # Both where clauses use the same parameter names and values — merge safely.
    params.update(line_params)
    alloc_amount = alloc_amount_column(base_currency)
    async with ReportingSessionLocal() as session:
        return (
            await session.execute(
                text(f"""
            WITH alloc_agg AS (
                SELECT
                    rpa.site,
                    COALESCE(SUM({alloc_amount}), 0)                                                              AS allocated_revenue,
                    COALESCE(SUM(CASE WHEN rpa.product_type = 'exam'   THEN {alloc_amount} ELSE 0 END), 0)       AS exam_revenue,
                    COALESCE(SUM(CASE WHEN rpa.product_type = 'book'   THEN {alloc_amount} ELSE 0 END), 0)       AS book_revenue,
                    COALESCE(SUM(CASE WHEN rpa.product_type = 'course' THEN {alloc_amount} ELSE 0 END), 0)       AS course_revenue
                FROM report_payment_allocations rpa
                WHERE {alloc_where} AND rpa.site IS NOT NULL
                GROUP BY rpa.site
            ),
            qty_agg AS (
                SELECT
                    site,
                    COALESCE(SUM(CASE WHEN product_type = 'book'   THEN quantity ELSE 0 END), 0) AS total_books,
                    COALESCE(SUM(CASE WHEN product_type = 'course' THEN quantity ELSE 0 END), 0) AS total_courses
                FROM report_line_items
                WHERE {line_where} AND site IS NOT NULL
                GROUP BY site
            )
            SELECT
                a.site AS country,
                a.allocated_revenue,
                a.exam_revenue,
                a.book_revenue,
                a.course_revenue,
                COALESCE(q.total_books,   0) AS total_books,
                COALESCE(q.total_courses, 0) AS total_courses
            FROM alloc_agg a
            LEFT JOIN qty_agg q ON q.site = a.site
            ORDER BY a.site ASC
        """),
                params,
            )
        ).fetchall()


async def fetch_country_exam_rows(filters: PorPaisFilters) -> list:
    where, params = _line_where(filters, require_product_breakdown=True)
    async with ReportingSessionLocal() as session:
        return (
            await session.execute(
                text(f"""
            SELECT
                site AS country,
                exam_canonical_name AS exam_name,
                SUM(quantity) AS exam_count
            FROM report_line_items
            WHERE {where} AND product_type = 'exam' AND site IS NOT NULL
            GROUP BY site, exam_canonical_name
            ORDER BY site ASC, exam_canonical_name ASC
        """),
                params,
            )
        ).fetchall()


async def fetch_country_presence_rows(filters: PorPaisFilters) -> list:
    where, params = _payment_where(filters)
    async with ReportingSessionLocal() as session:
        return (
            await session.execute(
                text(f"""
            SELECT DISTINCT
                site AS country,
                lead_id
            FROM report_payments
            WHERE {where} AND site IS NOT NULL
            ORDER BY country ASC, lead_id ASC
        """),
                params,
            )
        ).fetchall()


async def fetch_country_books_courses_presence_rows(filters: PorPaisFilters) -> list:
    where, params = _line_where(filters, require_product_breakdown=True)
    async with ReportingSessionLocal() as session:
        return (
            await session.execute(
                text(f"""
            SELECT DISTINCT
                site AS country,
                lead_id
            FROM report_line_items
            WHERE product_type IN ('book', 'course')
              AND {where} AND site IS NOT NULL
            ORDER BY country ASC, lead_id ASC
        """),
                params,
            )
        ).fetchall()


async def fetch_country_product_metric_rows(filters: PorPaisFilters) -> list:
    where, params = _line_where(filters, require_product_breakdown=True)
    async with ReportingSessionLocal() as session:
        return (
            await session.execute(
                text(f"""
            SELECT
                site AS country,
                lead_id,
                SUM(CASE WHEN product_type = 'exam'   THEN quantity ELSE 0 END) AS exams,
                SUM(CASE WHEN product_type = 'book'   THEN quantity ELSE 0 END) AS books,
                SUM(CASE WHEN product_type = 'course' THEN quantity ELSE 0 END) AS courses
            FROM report_line_items
            WHERE {where} AND site IS NOT NULL
            GROUP BY site, lead_id
            ORDER BY country ASC, lead_id ASC
        """),
                params,
            )
        ).fetchall()
