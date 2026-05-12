from sqlalchemy import text

from app.database import SessionLocal
from app.enums import ProductType
from app.schemas.pdf import PDFGeoPoint, PDFKpiItem, PDFTrendPoint, VentasTotalesPDFPayload
from app.schemas.reports import GeoPoint, ProductMix, ReportFilters, TotalSalesResponse, TrendPoint
from app.services.exports.excel import (
    ExcelColumn,
    ExcelWorksheetSpec,
    add_total_sales_charts,
)
from app.services.exports.pdf_helpers import (
    build_pdf_header,
    format_currency,
    format_growth,
    format_month_label,
    format_percent,
    scale_series,
)
from app.services.utils.date_utils import rewind_date_range_one_year
from app.services.utils.fact_subqueries import (
    build_deduped_paid_cart_product_fact_subquery,
    build_paid_payment_fact_subquery,
    build_paid_student_allocation_fact_subquery,
)
from app.services.utils.report_filters import (
    build_payment_fact_where_clause,
    build_student_payment_fact_where_clause,
)

TOTAL_SALES_SUMMARY_COLUMNS = [
    ExcelColumn("total_clients", "Total Clients"),
    ExcelColumn("total_exams", "Total Exams"),
    ExcelColumn("exam_revenue", "Exam Revenue"),
    ExcelColumn("total_books", "Total Books"),
    ExcelColumn("book_revenue", "Book Revenue"),
    ExcelColumn("total_courses", "Total Courses"),
    ExcelColumn("course_revenue", "Course Revenue"),
    ExcelColumn("total_otros", "Total Otros"),
    ExcelColumn("otros_revenue", "Otros Revenue"),
    ExcelColumn("total_revenue", "Total Revenue"),
    ExcelColumn("profit_margin", "Profit Margin"),
    ExcelColumn("prior_year_revenue", "Prior Year Revenue"),
    ExcelColumn("growth_pct", "Growth %"),
]

TOTAL_SALES_CHART_COLUMNS = [
    ExcelColumn("month", "Month"),
    ExcelColumn("trend_revenue", "Trend Revenue"),
    ExcelColumn("dimension", "Country"),
    ExcelColumn("geo_revenue", "Geo Revenue"),
]


# NOTE:
# This comparison implementation intentionally keeps two separate fact grains:
# - payment for total paid cash metrics, trend, geo, and prior-year comparison
# - student_payments for paid revenue breakdown
# - deduped cart_product rows for paid unit counts and line cost
#
# Assumptions based on clarified business rules:
# - payment.quantity is the amount to sum for approved payments
# - paid product attribution is reached through:
#     payment -> student_payments -> student -> cart_product -> product
# - cp.quantity represents the number of units sold for that cart-product line
# - geo filters should avoid one-to-many fanout by using EXISTS for address checks


def build_payment_where_clause(filters: ReportFilters) -> tuple[str, dict[str, object]]:
    where_clause, params, _ = build_payment_fact_where_clause(filters)
    return where_clause, params


def build_student_payment_where_clause(filters: ReportFilters) -> tuple[str, dict[str, object]]:
    where_clause, params, _ = build_student_payment_fact_where_clause(filters)
    return where_clause, params


async def run_payment_summary_query(
    session, where_clause: str, params: dict[str, object]
) -> tuple[int, float]:
    query = f"""
        SELECT
            COUNT(DISTINCT qp.lead_id) AS total_clients,
            COALESCE(SUM(qp.paid_amount), 0) AS total_revenue
        FROM ({build_paid_payment_fact_subquery(where_clause)}) qp
    """
    row = (await session.execute(text(query), params)).fetchone()
    return int(row.total_clients or 0), float(row.total_revenue or 0)


async def run_breakdown_summary_query(session, where_clause: str, params: dict[str, object]):
    student_payment_fact = build_paid_student_allocation_fact_subquery(where_clause)
    paid_cart_product_fact = build_deduped_paid_cart_product_fact_subquery(student_payment_fact)
    query = f"""
        SELECT
            COALESCE(quantity_mix.total_exams, 0) AS total_exams,
            COALESCE(revenue_mix.exam_revenue, 0) AS exam_revenue,
            COALESCE(quantity_mix.total_books, 0) AS total_books,
            COALESCE(revenue_mix.book_revenue, 0) AS book_revenue,
            COALESCE(quantity_mix.total_courses, 0) AS total_courses,
            COALESCE(revenue_mix.course_revenue, 0) AS course_revenue,
            COALESCE(quantity_mix.total_otros, 0) AS total_otros,
            COALESCE(revenue_mix.otros_revenue, 0) AS otros_revenue,
            COALESCE(quantity_mix.total_cost, 0) AS total_cost
        FROM (
            SELECT
                SUM(CASE WHEN pcp.product_type = :product_type_exam THEN pcp.cart_product_quantity ELSE 0 END) AS total_exams,
                SUM(CASE WHEN pcp.product_type = :product_type_book THEN pcp.cart_product_quantity ELSE 0 END) AS total_books,
                SUM(CASE WHEN pcp.product_type = :product_type_course THEN pcp.cart_product_quantity ELSE 0 END) AS total_courses,
                SUM(
                    CASE
                        WHEN pcp.product_type IS NULL
                          OR pcp.product_type NOT IN (
                              :product_type_exam,
                              :product_type_book,
                              :product_type_course
                          )
                        THEN pcp.cart_product_quantity
                        ELSE 0
                    END
                ) AS total_otros,
                SUM(pcp.cart_product_cost) AS total_cost
            FROM ({paid_cart_product_fact}) pcp
        ) quantity_mix
        CROSS JOIN (
            SELECT
                SUM(CASE WHEN ar.product_type = :product_type_exam THEN ar.allocated_amount ELSE 0 END) AS exam_revenue,
                SUM(CASE WHEN ar.product_type = :product_type_book THEN ar.allocated_amount ELSE 0 END) AS book_revenue,
                SUM(CASE WHEN ar.product_type = :product_type_course THEN ar.allocated_amount ELSE 0 END) AS course_revenue,
                SUM(
                    CASE
                        WHEN ar.product_type IS NULL
                          OR ar.product_type NOT IN (
                              :product_type_exam,
                              :product_type_book,
                              :product_type_course
                          )
                        THEN ar.allocated_amount
                        ELSE 0
                    END
                ) AS otros_revenue
            FROM ({student_payment_fact}) ar
        ) revenue_mix
    """
    query_params = {
        **params,
        "product_type_exam": ProductType.EXAM.value,
        "product_type_book": ProductType.BOOK.value,
        "product_type_course": ProductType.COURSE.value,
    }
    return (await session.execute(text(query), query_params)).fetchone()


async def run_main_query(session, filters: ReportFilters) -> TotalSalesResponse:
    payment_where_clause, payment_params = build_payment_where_clause(filters)
    breakdown_where_clause, breakdown_params = build_student_payment_where_clause(filters)

    total_clients, total_revenue = await run_payment_summary_query(
        session, payment_where_clause, payment_params
    )
    breakdown = await run_breakdown_summary_query(session, breakdown_where_clause, breakdown_params)

    total_cost = float(breakdown.total_cost or 0)
    profit_margin = ((total_revenue - total_cost) / total_revenue * 100) if total_revenue > 0 else 0

    return TotalSalesResponse(
        total_clients=total_clients,
        total_exams=int(breakdown.total_exams or 0),
        exam_revenue=float(breakdown.exam_revenue or 0),
        total_books=int(breakdown.total_books or 0),
        book_revenue=float(breakdown.book_revenue or 0),
        total_courses=int(breakdown.total_courses or 0),
        course_revenue=float(breakdown.course_revenue or 0),
        total_otros=int(breakdown.total_otros or 0),
        otros_revenue=float(breakdown.otros_revenue or 0),
        total_revenue=total_revenue,
        profit_margin=profit_margin,
        prior_year_revenue=0,
        growth_pct=0,
        trend_points=[],
        geo_points=[],
        product_mix=None,
    )


async def run_trend_query(session, where_clause: str, params: dict[str, object]) -> list[TrendPoint]:
    query = f"""
        SELECT
            DATE_FORMAT(qp.payment_day, '%Y-%m') AS month,
            COALESCE(SUM(qp.paid_amount), 0) AS revenue
        FROM ({build_paid_payment_fact_subquery(where_clause)}) qp
        GROUP BY month
        ORDER BY month ASC
    """
    result = await session.execute(text(query), params)
    return [TrendPoint(month=row.month, revenue=float(row.revenue or 0)) for row in result.fetchall()]


async def run_geo_query(session, where_clause: str, params: dict[str, object]) -> list[GeoPoint]:
    query = f"""
        SELECT
            qp.country AS dimension,
            COALESCE(SUM(qp.paid_amount), 0) AS revenue
        FROM ({build_paid_payment_fact_subquery(where_clause)}) qp
        GROUP BY dimension
        ORDER BY dimension ASC
    """
    result = await session.execute(text(query), params)
    return [GeoPoint(dimension=row.dimension, revenue=float(row.revenue or 0)) for row in result.fetchall()]


def rewind_dates_one_year(filters: ReportFilters) -> ReportFilters:
    if filters.date_from is None or filters.date_to is None:
        raise ValueError("Cannot rewind non-existent dates")
    prior_date_from, prior_date_to = rewind_date_range_one_year(filters.date_from, filters.date_to)
    return filters.model_copy(
        update={
            "date_from": prior_date_from,
            "date_to": prior_date_to,
        }
    )


async def run_prior_year_query(session, filters: ReportFilters) -> float:
    prior_filters = rewind_dates_one_year(filters)
    where_clause, params = build_payment_where_clause(prior_filters)
    query = f"""
        SELECT COALESCE(SUM(qp.paid_amount), 0) AS prior_revenue
        FROM ({build_paid_payment_fact_subquery(where_clause)}) qp
    """
    row = (await session.execute(text(query), params)).fetchone()
    return float(row.prior_revenue or 0)


async def getTotalSalesData(filters: ReportFilters) -> TotalSalesResponse:
    payment_where_clause, payment_params = build_payment_where_clause(filters)
    async with SessionLocal() as session:
        response = await run_main_query(session, filters)
        if response.total_revenue:
            response.product_mix = ProductMix(
                exams_pct=round(response.exam_revenue / response.total_revenue * 100, 1),
                books_pct=round(response.book_revenue / response.total_revenue * 100, 1),
                courses_pct=round(response.course_revenue / response.total_revenue * 100, 1),
            )
        response.trend_points = await run_trend_query(session, payment_where_clause, payment_params)
        response.geo_points = await run_geo_query(session, payment_where_clause, payment_params)
        if filters.date_from and filters.date_to:
            response.prior_year_revenue = await run_prior_year_query(session, filters)
            if response.prior_year_revenue > 0:
                response.growth_pct = (
                    (response.total_revenue - response.prior_year_revenue)
                    / response.prior_year_revenue
                    * 100
                )
        return response


async def build_ventas_totales_pdf_payload(filters: ReportFilters) -> VentasTotalesPDFPayload:
    response = await getTotalSalesData(filters)

    trend_values = [point.revenue for point in response.trend_points]
    geo_values = [point.revenue for point in response.geo_points]
    scaled_trend = scale_series(trend_values)
    scaled_geo = scale_series(geo_values)

    growth_value = response.growth_pct if response.prior_year_revenue > 0 else None
    growth, growth_positive = format_growth(growth_value)

    kpis = [
        PDFKpiItem(label="Total Clientes", value=str(response.total_clients)),
        PDFKpiItem(label="Total Exámenes", value=str(response.total_exams)),
        PDFKpiItem(label="Ingreso por Exámenes", value=format_currency(response.exam_revenue)),
        PDFKpiItem(label="Total Libros", value=str(response.total_books)),
        PDFKpiItem(label="Ingreso por Libros", value=format_currency(response.book_revenue)),
        PDFKpiItem(label="Total Cursos", value=str(response.total_courses)),
        PDFKpiItem(label="Ingreso por Cursos", value=format_currency(response.course_revenue)),
        PDFKpiItem(label="Otros", value=str(response.total_otros)),
        PDFKpiItem(label="Ingreso por Otros", value=format_currency(response.otros_revenue)),
        PDFKpiItem(
            label="Ingreso Total",
            value=format_currency(response.total_revenue),
            growth=growth,
            growth_positive=growth_positive,
        ),
        PDFKpiItem(label="Margen de Utilidad", value=format_percent(response.profit_margin)),
    ]
    if response.prior_year_revenue > 0:
        kpis.append(
            PDFKpiItem(
                label="Ingreso Año Anterior",
                value=format_currency(response.prior_year_revenue),
            )
        )

    return VentasTotalesPDFPayload(
        header=build_pdf_header(
            "Ventas Totales",
            "Resumen general de ventas por período y región",
            filters,
        ),
        kpis=kpis,
        trend_points=[
            PDFTrendPoint(
                label=format_month_label(point.month),
                value=point.revenue,
                scaled=scaled_trend[index],
            )
            for index, point in enumerate(response.trend_points)
        ],
        geo_points=[
            PDFGeoPoint(
                label=point.dimension,
                value=point.revenue,
                scaled=scaled_geo[index],
            )
            for index, point in enumerate(response.geo_points)
        ],
    )


def build_total_sales_export_filters_for_all(filters: ReportFilters) -> ReportFilters:
    return filters.model_copy(
        update={
            "countries": [],
            "zones": [],
            "states": [],
            "cities": [],
        }
    )


def build_total_sales_export_worksheets(
    response: TotalSalesResponse,
    *,
    include_charts: bool = True,
) -> list[ExcelWorksheetSpec]:
    summary_row = {
        "total_clients": response.total_clients,
        "total_exams": response.total_exams,
        "exam_revenue": response.exam_revenue,
        "total_books": response.total_books,
        "book_revenue": response.book_revenue,
        "total_courses": response.total_courses,
        "course_revenue": response.course_revenue,
        "total_otros": response.total_otros,
        "otros_revenue": response.otros_revenue,
        "total_revenue": response.total_revenue,
        "profit_margin": response.profit_margin,
        "prior_year_revenue": response.prior_year_revenue,
        "growth_pct": response.growth_pct,
    }
    worksheets = [
        ExcelWorksheetSpec(
            name="Ventas Totales",
            columns=TOTAL_SALES_SUMMARY_COLUMNS,
            rows=[summary_row],
        )
    ]
    if include_charts:
        max_length = max(len(response.trend_points), len(response.geo_points), 1)
        chart_rows = []
        for index in range(max_length):
            trend_point = response.trend_points[index] if index < len(response.trend_points) else None
            geo_point = response.geo_points[index] if index < len(response.geo_points) else None
            chart_rows.append(
                {
                    "month": trend_point.month if trend_point else "",
                    "trend_revenue": trend_point.revenue if trend_point else 0,
                    "dimension": geo_point.dimension if geo_point else "",
                    "geo_revenue": geo_point.revenue if geo_point else 0,
                }
            )
        worksheets.append(
            ExcelWorksheetSpec(
                name="Ventas Totales Charts",
                columns=TOTAL_SALES_CHART_COLUMNS,
                rows=chart_rows,
                post_process=add_total_sales_charts,
            )
        )
    return worksheets
