from app.enums import BaseCurrency
from sqlalchemy import text

from app.reporting.database import ReportingSessionLocal
from app.schemas.reports import PorPaisFilters
from app.services.utils.report_currency import line_paid_total_column, payment_amount_column
from app.services.shared import build_line_item_where_clause, build_payment_where_clause


def _payment_where(filters: PorPaisFilters) -> tuple[str, dict]:
    return build_payment_where_clause(filters)


def _line_where(
    filters: PorPaisFilters, *, require_product_breakdown: bool = False
) -> tuple[str, dict]:
    return build_line_item_where_clause(
        filters, require_product_breakdown=require_product_breakdown
    )


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
            WHERE {where}
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
    where, params = _line_where(filters, require_product_breakdown=True)
    paid_total = line_paid_total_column(base_currency)
    async with ReportingSessionLocal() as session:
        return (
            await session.execute(
                text(f"""
            SELECT
                site AS country,
                COALESCE(SUM({paid_total}), 0) AS allocated_revenue
            FROM report_line_items
            WHERE {where}
            GROUP BY site
            ORDER BY site ASC
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
            WHERE {where} AND product_type = 'exam'
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
            WHERE {where}
            ORDER BY country ASC, lead_id ASC
        """),
                params,
            )
        ).fetchall()


async def fetch_country_metric_rows(filters: PorPaisFilters) -> list:
    where, params = _line_where(filters, require_product_breakdown=True)
    async with ReportingSessionLocal() as session:
        return (
            await session.execute(
                text(f"""
            SELECT
                site AS country,
                lead_id,
                SUM(quantity) AS exams
            FROM report_line_items
            WHERE {where} AND product_type = 'exam'
            GROUP BY site, lead_id
            ORDER BY country ASC, lead_id ASC
        """),
                params,
            )
        ).fetchall()
