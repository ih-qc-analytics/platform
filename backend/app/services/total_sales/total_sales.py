from sqlalchemy import text

from app.reporting.database import ReportingSessionLocal
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
from app.services.shared import build_geo_where_clause

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


async def getTotalSalesData(
    filters: ReportFilters,
    country_rates: dict | None = None,
) -> TotalSalesResponse:
    where_clause, params = build_geo_where_clause(filters)

    async with ReportingSessionLocal() as session:
        # Main summary
        row = (await session.execute(text(f"""
            SELECT
                COUNT(DISTINCT lead_id)                                                      AS total_clients,
                SUM(CASE WHEN product_type = 'exam'          THEN quantity  ELSE 0 END) AS total_exams,
                SUM(CASE WHEN product_type = 'exam'          THEN total_mxn ELSE 0 END) AS exam_revenue,
                SUM(CASE WHEN product_type = 'book'          THEN quantity  ELSE 0 END) AS total_books,
                SUM(CASE WHEN product_type = 'book'          THEN total_mxn ELSE 0 END) AS book_revenue,
                SUM(CASE WHEN product_type = 'course'        THEN quantity  ELSE 0 END) AS total_courses,
                SUM(CASE WHEN product_type = 'course'        THEN total_mxn ELSE 0 END) AS course_revenue,
                SUM(CASE WHEN product_type = 'UNCATEGORIZED' THEN quantity  ELSE 0 END) AS total_otros,
                SUM(CASE WHEN product_type = 'UNCATEGORIZED' THEN total_mxn ELSE 0 END) AS otros_revenue,
                SUM(total_mxn)                                                           AS total_revenue,
                SUM(cost_mxn)                                                            AS total_cost
            FROM report_line_items
            WHERE {where_clause}
        """), params)).fetchone()

        total_revenue = float(row.total_revenue or 0)
        total_cost    = float(row.total_cost or 0)
        profit_margin = ((total_revenue - total_cost) / total_revenue * 100) if total_revenue > 0 else 0

        # Trend (monthly)
        trend_rows = (await session.execute(text(f"""
            SELECT
                TO_CHAR(created_at, 'YYYY-MM') AS month,
                SUM(total_mxn)                 AS revenue
            FROM report_line_items
            WHERE {where_clause}
            GROUP BY month
            ORDER BY month ASC
        """), params)).fetchall()

        # Geo (by country/site)
        geo_rows = (await session.execute(text(f"""
            SELECT
                site           AS dimension,
                SUM(total_mxn) AS revenue
            FROM report_line_items
            WHERE {where_clause}
            GROUP BY site
            ORDER BY site ASC
        """), params)).fetchall()

        # Prior-year revenue (only when date range is provided)
        prior_year_revenue = 0.0
        if filters.date_from and filters.date_to:
            prior_date_from, prior_date_to = rewind_date_range_one_year(filters.date_from, filters.date_to)
            prior_filters = filters.model_copy(update={"date_from": prior_date_from, "date_to": prior_date_to})
            prior_where, prior_params = build_geo_where_clause(prior_filters)
            prior_row = (await session.execute(text(f"""
                SELECT SUM(total_mxn) AS prior_revenue
                FROM report_line_items
                WHERE {prior_where}
            """), prior_params)).fetchone()
            prior_year_revenue = float(prior_row.prior_revenue or 0)

    growth_pct = None
    if prior_year_revenue > 0:
        growth_pct = (total_revenue - prior_year_revenue) / prior_year_revenue * 100

    trend_points = [TrendPoint(month=r.month, revenue=float(r.revenue or 0)) for r in trend_rows]
    geo_points   = [GeoPoint(dimension=r.dimension, revenue=float(r.revenue or 0)) for r in geo_rows]

    response = TotalSalesResponse(
        total_clients=int(row.total_clients or 0),
        total_exams=int(row.total_exams or 0),
        exam_revenue=float(row.exam_revenue or 0),
        total_books=int(row.total_books or 0),
        book_revenue=float(row.book_revenue or 0),
        total_courses=int(row.total_courses or 0),
        course_revenue=float(row.course_revenue or 0),
        total_otros=int(row.total_otros or 0),
        otros_revenue=float(row.otros_revenue or 0),
        total_revenue=total_revenue,
        profit_margin=profit_margin,
        prior_year_revenue=prior_year_revenue,
        growth_pct=growth_pct,
        trend_points=trend_points,
        geo_points=geo_points,
        product_mix=None,
    )

    if response.total_revenue:
        response.product_mix = ProductMix(
            exams_pct=round(response.exam_revenue / response.total_revenue * 100, 1),
            books_pct=round(response.book_revenue / response.total_revenue * 100, 1),
            courses_pct=round(response.course_revenue / response.total_revenue * 100, 1),
        )

    return response


async def build_ventas_totales_pdf_payload(
    filters: ReportFilters,
    country_rates: dict | None = None,
) -> VentasTotalesPDFPayload:
    response = await getTotalSalesData(filters, country_rates=country_rates)

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
        kpis.append(PDFKpiItem(label="Ingreso Año Anterior", value=format_currency(response.prior_year_revenue)))

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
        update={"countries": [], "zones": [], "states": [], "cities": []}
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
            geo_point   = response.geo_points[index]   if index < len(response.geo_points)   else None
            chart_rows.append({
                "month":        trend_point.month   if trend_point else "",
                "trend_revenue": trend_point.revenue if trend_point else 0,
                "dimension":    geo_point.dimension if geo_point   else "",
                "geo_revenue":  geo_point.revenue   if geo_point   else 0,
            })
        worksheets.append(
            ExcelWorksheetSpec(
                name="Ventas Totales Charts",
                columns=TOTAL_SALES_CHART_COLUMNS,
                rows=chart_rows,
                post_process=add_total_sales_charts,
            )
        )
    return worksheets
