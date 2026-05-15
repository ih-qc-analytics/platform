from sqlalchemy import text
from app.reporting.database import ReportingSessionLocal
from app.enums import PaymentStatus


def _por_pais_where(date_from: str, date_to: str) -> tuple[str, dict]:
    return (
        "is_active = TRUE AND payment_status = :payment_status"
        " AND created_at >= :date_from AND created_at <= :date_to",
        {
            "payment_status": PaymentStatus.APROBADO.value,
            "date_from":      date_from,
            "date_to":        date_to,
        },
    )


async def fetch_country_school_rows(date_from: str, date_to: str) -> list:
    where, params = _por_pais_where(date_from, date_to)
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(f"""
            SELECT
                site                    AS country,
                COUNT(DISTINCT lead_id) AS total_schools
            FROM report_line_items
            WHERE {where}
            GROUP BY site
            ORDER BY site ASC
        """), params)).fetchall()


async def fetch_country_exam_rows(date_from: str, date_to: str) -> list:
    where, params = _por_pais_where(date_from, date_to)
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(f"""
            SELECT
                site                 AS country,
                exam_canonical_name  AS exam_name,
                SUM(quantity)        AS exam_count
            FROM report_line_items
            WHERE {where} AND product_type = 'exam'
            GROUP BY site, exam_canonical_name
            ORDER BY site ASC, exam_canonical_name ASC
        """), params)).fetchall()


async def fetch_country_presence_rows(date_from: str, date_to: str) -> list:
    """Distinct (country, lead_id) pairs — used for ganado/perdido/mantenido classification."""
    where, params = _por_pais_where(date_from, date_to)
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(f"""
            SELECT DISTINCT
                site     AS country,
                lead_id
            FROM report_line_items
            WHERE {where}
            ORDER BY country ASC, lead_id ASC
        """), params)).fetchall()


async def fetch_country_metric_rows(date_from: str, date_to: str) -> list:
    """Exam count per (country, lead_id) — used to compute ganado/perdido/mantenido exam totals."""
    where, params = _por_pais_where(date_from, date_to)
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(f"""
            SELECT
                site          AS country,
                lead_id,
                SUM(quantity) AS exams
            FROM report_line_items
            WHERE {where} AND product_type = 'exam'
            GROUP BY site, lead_id
            ORDER BY country ASC, lead_id ASC
        """), params)).fetchall()
