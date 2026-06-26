import asyncio
from datetime import datetime

from sqlalchemy import text

from app.enums import BaseCurrency
from app.reporting.database import ReportingSessionLocal
from app.schemas.pdf import PDFGeoPoint, PDFKpiItem, PDFTrendPoint, VentasTotalesPDFPayload
from app.schemas.reports import (
    GeoPoint,
    MetricDelta,
    ProductMix,
    ReportFilters,
    TotalSalesBase,
    TotalSalesComparison,
    TotalSalesResponse,
    TrendPoint,
)
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
from app.services.utils.date_utils import percent_change, resolve_comparison_range
from app.services.utils.report_currency import (
    line_expected_cost_column,
    line_expected_total_column,
    line_paid_total_column,
    payment_amount_column,
)
from app.services.shared import (
    build_line_item_where_clause,
    build_payment_where_clause,
    line_item_date_expr,
    payment_date_expr,
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
    ExcelColumn("expected_revenue", "Expected Revenue"),
    ExcelColumn("expected_cost", "Expected Cost"),
    ExcelColumn("uncategorized_revenue", "Uncategorized Revenue"),
    ExcelColumn("unknown_site_revenue", "Unknown Site Revenue"),
    ExcelColumn("unknown_site_expected_revenue", "Unknown Site Expected Revenue"),
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


async def _get_total_sales_base(
    filters: ReportFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> TotalSalesBase:
    payment_where, payment_params = build_payment_where_clause(filters)
    line_where, line_params = build_line_item_where_clause(filters, require_product_breakdown=True)
    payment_amount = payment_amount_column(base_currency)
    paid_total = line_paid_total_column(base_currency)
    expected_total = line_expected_total_column(base_currency)
    expected_cost = line_expected_cost_column(base_currency)

    async def fetch_payment_summary():
        async with ReportingSessionLocal() as session:
            return (
                await session.execute(
                    text(f"""
                SELECT
                    COUNT(DISTINCT lead_id) AS total_clients,
                    COALESCE(SUM({payment_amount}), 0) AS total_revenue,
                    COALESCE(SUM(CASE WHEN base_currency = 'UNKNOWN' THEN amount ELSE 0 END), 0) AS unknown_site_revenue
                FROM report_payments
                WHERE {payment_where}
            """),
                    payment_params,
                )
            ).fetchone()

    async def fetch_line_summary():
        async with ReportingSessionLocal() as session:
            return (
                await session.execute(
                    text(f"""
                SELECT
                    COALESCE(SUM(CASE WHEN product_type = 'exam' THEN quantity ELSE 0 END), 0) AS total_exams,
                    COALESCE(SUM(CASE WHEN product_type = 'exam' THEN {paid_total} ELSE 0 END), 0) AS exam_revenue,
                    COALESCE(SUM(CASE WHEN product_type = 'book' THEN quantity ELSE 0 END), 0) AS total_books,
                    COALESCE(SUM(CASE WHEN product_type = 'book' THEN {paid_total} ELSE 0 END), 0) AS book_revenue,
                    COALESCE(SUM(CASE WHEN product_type = 'course' THEN quantity ELSE 0 END), 0) AS total_courses,
                    COALESCE(SUM(CASE WHEN product_type = 'course' THEN {paid_total} ELSE 0 END), 0) AS course_revenue,
                    COALESCE(SUM(CASE WHEN product_type = 'UNCATEGORIZED' THEN quantity ELSE 0 END), 0) AS total_otros,
                    COALESCE(SUM(CASE WHEN product_type = 'UNCATEGORIZED' THEN {paid_total} ELSE 0 END), 0) AS otros_revenue,
                    COALESCE(SUM({paid_total}), 0) AS allocated_paid_revenue,
                    COALESCE(SUM({expected_total}), 0) AS expected_revenue,
                    COALESCE(SUM({expected_cost}), 0) AS expected_cost,
                    COALESCE(SUM(CASE WHEN base_currency = 'UNKNOWN' THEN expected_total ELSE 0 END), 0) AS unknown_site_expected_revenue
                FROM report_line_items
                WHERE {line_where}
            """),
                    line_params,
                )
            ).fetchone()

    async def fetch_trend_rows():
        async with ReportingSessionLocal() as session:
            return (
                await session.execute(
                    text(f"""
                SELECT
                    TO_CHAR({payment_date_expr()}, 'YYYY-MM') AS month,
                    COALESCE(SUM({payment_amount}), 0) AS revenue
                FROM report_payments
                WHERE {payment_where}
                GROUP BY TO_CHAR({payment_date_expr()}, 'YYYY-MM')
                ORDER BY month ASC
            """),
                    payment_params,
                )
            ).fetchall()

    async def fetch_geo_rows():
        async with ReportingSessionLocal() as session:
            return (
                await session.execute(
                    text(f"""
                SELECT
                    site AS dimension,
                    COALESCE(SUM({payment_amount}), 0) AS revenue
                FROM report_payments
                WHERE {payment_where}
                AND site IS NOT NULL
                GROUP BY site
                ORDER BY site ASC
            """),
                    payment_params,
                )
            ).fetchall()

    payment_row, line_row, trend_rows, geo_rows = await asyncio.gather(
        fetch_payment_summary(),
        fetch_line_summary(),
        fetch_trend_rows(),
        fetch_geo_rows(),
    )

    total_revenue = float(payment_row.total_revenue or 0)
    allocated_paid_revenue = float(line_row.allocated_paid_revenue or 0)
    expected_cost = float(line_row.expected_cost or 0)
    uncategorized_revenue = total_revenue - allocated_paid_revenue
    profit_margin = (
        ((allocated_paid_revenue - expected_cost) / allocated_paid_revenue * 100)
        if allocated_paid_revenue > 0
        else 0.0
    )

    trend_points = _build_trend_points(filters, trend_rows)
    geo_points = [GeoPoint(dimension=r.dimension, revenue=float(r.revenue or 0)) for r in geo_rows]

    response = TotalSalesBase(
        total_clients=int(payment_row.total_clients or 0),
        total_exams=int(line_row.total_exams or 0),
        exam_revenue=float(line_row.exam_revenue or 0),
        total_books=int(line_row.total_books or 0),
        book_revenue=float(line_row.book_revenue or 0),
        total_courses=int(line_row.total_courses or 0),
        course_revenue=float(line_row.course_revenue or 0),
        total_otros=int(line_row.total_otros or 0),
        otros_revenue=float(line_row.otros_revenue or 0),
        total_revenue=total_revenue,
        expected_revenue=float(line_row.expected_revenue or 0),
        expected_cost=expected_cost,
        uncategorized_revenue=uncategorized_revenue,
        unknown_site_revenue=float(payment_row.unknown_site_revenue or 0),
        unknown_site_expected_revenue=float(line_row.unknown_site_expected_revenue or 0),
        profit_margin=profit_margin,
        trend_points=trend_points,
        geo_points=geo_points,
        product_mix=None,
    )

    if response.total_revenue:
        response.product_mix = ProductMix(
            exams_pct=round(response.exam_revenue / response.total_revenue * 100, 1),
            books_pct=round(response.book_revenue / response.total_revenue * 100, 1),
            courses_pct=round(response.course_revenue / response.total_revenue * 100, 1),
            unknown_pct=round(response.uncategorized_revenue / response.total_revenue * 100, 1),
        )

    return response


def _total_sales_kpi_deltas(
    current: TotalSalesBase, comparison: TotalSalesBase
) -> dict[str, MetricDelta]:
    values = {
        "total_clients": (current.total_clients, comparison.total_clients),
        "total_exams": (current.total_exams, comparison.total_exams),
        "exam_revenue": (current.exam_revenue, comparison.exam_revenue),
        "total_books": (current.total_books, comparison.total_books),
        "book_revenue": (current.book_revenue, comparison.book_revenue),
        "total_courses": (current.total_courses, comparison.total_courses),
        "course_revenue": (current.course_revenue, comparison.course_revenue),
        "total_otros": (current.total_otros, comparison.total_otros),
        "otros_revenue": (current.otros_revenue, comparison.otros_revenue),
        "total_revenue": (current.total_revenue, comparison.total_revenue),
        "expected_revenue": (current.expected_revenue, comparison.expected_revenue),
        "expected_cost": (current.expected_cost, comparison.expected_cost),
        "uncategorized_revenue": (current.uncategorized_revenue, comparison.uncategorized_revenue),
        "unknown_site_revenue": (current.unknown_site_revenue, comparison.unknown_site_revenue),
        "unknown_site_expected_revenue": (
            current.unknown_site_expected_revenue,
            comparison.unknown_site_expected_revenue,
        ),
        "profit_margin": (current.profit_margin, comparison.profit_margin),
    }
    return {
        key: MetricDelta(
            comparison_value=float(comparison_value),
            pct_change=percent_change(current_value, comparison_value),
        )
        for key, (current_value, comparison_value) in values.items()
    }


async def getTotalSalesData(
    filters: ReportFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> TotalSalesResponse:
    comparison_meta = resolve_comparison_range(filters)
    current_filters = filters.model_copy(
        update={
            "show_comparison": False,
            "comparison_date_from": None,
            "comparison_date_to": None,
        }
    )

    if comparison_meta is None:
        current = await _get_total_sales_base(
            current_filters,
            country_rates=country_rates,
            base_currency=base_currency,
        )
        return TotalSalesResponse(current=current, comparison_mode=None, comparison=None)

    comparison_filters = current_filters.model_copy(
        update={
            "date_from": comparison_meta.date_from,
            "date_to": comparison_meta.date_to,
        }
    )

    current, comparison = await asyncio.gather(
        _get_total_sales_base(
            current_filters, country_rates=country_rates, base_currency=base_currency
        ),
        _get_total_sales_base(
            comparison_filters, country_rates=country_rates, base_currency=base_currency
        ),
    )

    return TotalSalesResponse(
        current=current,
        comparison_mode=comparison_meta.mode,
        comparison=TotalSalesComparison(
            meta=comparison_meta,
            data=comparison,
            deltas=_total_sales_kpi_deltas(current, comparison),
        ),
    )


def _build_trend_points(filters: ReportFilters, trend_rows) -> list[TrendPoint]:
    revenue_by_month = {row.month: float(row.revenue or 0) for row in trend_rows}
    if not filters.date_from or not filters.date_to:
        return [
            TrendPoint(month=month, revenue=revenue) for month, revenue in revenue_by_month.items()
        ]
    if not trend_rows:
        return []

    months = sorted(revenue_by_month)
    current = datetime.strptime(months[0], "%Y-%m").date()
    end = datetime.strptime(months[-1], "%Y-%m").date()
    points: list[TrendPoint] = []
    while current <= end:
        month_key = current.strftime("%Y-%m")
        points.append(TrendPoint(month=month_key, revenue=revenue_by_month.get(month_key, 0.0)))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return points


async def build_ventas_totales_pdf_payload(
    filters: ReportFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> VentasTotalesPDFPayload:
    response = await getTotalSalesData(
        filters, country_rates=country_rates, base_currency=base_currency
    )
    base = response.current

    comp = response.comparison
    # Comparison trend: match by index (months shift by a year in PREVIOUS_YEAR mode so key lookup fails)
    comp_trend_pts = comp.data.trend_points if comp else []
    comp_geo_by_dim = {p.dimension: p.revenue for p in comp.data.geo_points} if comp else {}

    trend_values = [point.revenue for point in base.trend_points]
    comp_trend_values = [
        comp_trend_pts[i].revenue if i < len(comp_trend_pts) else 0.0
        for i in range(len(base.trend_points))
    ]
    geo_values = [point.revenue for point in base.geo_points]
    comp_geo_values = [comp_geo_by_dim.get(p.dimension, 0.0) for p in base.geo_points]

    max_trend = max(trend_values + comp_trend_values) if trend_values else 1.0
    max_geo = max(geo_values + comp_geo_values) if geo_values else 1.0
    scaled_trend = [v / max_trend if max_trend else 0.0 for v in trend_values]
    scaled_comp_trend = [v / max_trend if max_trend else 0.0 for v in comp_trend_values]
    scaled_geo = [v / max_geo if max_geo else 0.0 for v in geo_values]
    scaled_comp_geo = [v / max_geo if max_geo else 0.0 for v in comp_geo_values]

    def _kw(delta_key: str) -> dict:
        if not comp:
            return {}
        delta = comp.deltas.get(delta_key)
        growth_str, positive = format_growth(delta.pct_change if delta else None)
        return {
            "growth": growth_str if growth_str is not None else "N/A",
            "growth_positive": positive,
        }

    kpis = [
        PDFKpiItem(label="Total Clientes", value=str(base.total_clients), **_kw("total_clients")),
        PDFKpiItem(label="Total Exámenes", value=str(base.total_exams), **_kw("total_exams")),
        PDFKpiItem(
            label="Ingreso por Exámenes",
            value=format_currency(base.exam_revenue, base_currency),
            **_kw("exam_revenue"),
        ),
        PDFKpiItem(label="Total Libros", value=str(base.total_books), **_kw("total_books")),
        PDFKpiItem(
            label="Ingreso por Libros",
            value=format_currency(base.book_revenue, base_currency),
            **_kw("book_revenue"),
        ),
        PDFKpiItem(label="Total Cursos", value=str(base.total_courses), **_kw("total_courses")),
        PDFKpiItem(
            label="Ingreso por Cursos",
            value=format_currency(base.course_revenue, base_currency),
            **_kw("course_revenue"),
        ),
        PDFKpiItem(label="Otros", value=str(base.total_otros), **_kw("total_otros")),
        PDFKpiItem(
            label="Ingreso por Otros",
            value=format_currency(base.otros_revenue, base_currency),
            **_kw("otros_revenue"),
        ),
        PDFKpiItem(
            label="Ingreso Esperado",
            value=format_currency(base.expected_revenue, base_currency),
            **_kw("expected_revenue"),
        ),
        PDFKpiItem(
            label="Costo Esperado",
            value=format_currency(base.expected_cost, base_currency),
            **_kw("expected_cost"),
        ),
        PDFKpiItem(
            label="Sin Categorizar",
            value=format_currency(base.uncategorized_revenue, base_currency),
            **_kw("uncategorized_revenue"),
        ),
        PDFKpiItem(
            label="Ingreso Sitio Desconocido",
            value=format_currency(base.unknown_site_revenue, base_currency),
            **_kw("unknown_site_revenue"),
        ),
        PDFKpiItem(
            label="Esperado Sitio Desconocido",
            value=format_currency(base.unknown_site_expected_revenue, base_currency),
            **_kw("unknown_site_expected_revenue"),
        ),
        PDFKpiItem(
            label="Ingreso Total",
            value=format_currency(base.total_revenue, base_currency),
            **_kw("total_revenue"),
        ),
        PDFKpiItem(
            label="Margen de Utilidad",
            value=format_percent(base.profit_margin),
            **_kw("profit_margin"),
        ),
    ]

    return VentasTotalesPDFPayload(
        header=build_pdf_header(
            "Ventas Totales",
            "Resumen general de ventas por período y región",
            filters,
            comparison_meta=comp.meta if comp else None,
        ),
        kpis=kpis,
        trend_points=[
            PDFTrendPoint(
                label=format_month_label(point.month),
                value=point.revenue,
                scaled=scaled_trend[index],
                comparison_value=comp_trend_pts[index].revenue
                if comp and index < len(comp_trend_pts)
                else None,
                comparison_scaled=scaled_comp_trend[index]
                if comp and index < len(comp_trend_pts)
                else None,
            )
            for index, point in enumerate(base.trend_points)
        ],
        geo_points=[
            PDFGeoPoint(
                label=point.dimension,
                value=point.revenue,
                scaled=scaled_geo[index],
                comparison_value=comp_geo_by_dim.get(point.dimension) if comp else None,
                comparison_scaled=scaled_comp_geo[index] if comp else None,
            )
            for index, point in enumerate(base.geo_points)
        ],
    )


def build_total_sales_export_filters_for_all(filters: ReportFilters) -> ReportFilters:
    return filters.model_copy(update={"countries": [], "zones": [], "states": [], "cities": []})


_COMPARISON_KPI_KEYS: list[tuple[str, str]] = [
    ("total_clients", "Total Clientes"),
    ("total_exams", "Total Exámenes"),
    ("exam_revenue", "Ingreso por Exámenes"),
    ("total_books", "Total Libros"),
    ("book_revenue", "Ingreso por Libros"),
    ("total_courses", "Total Cursos"),
    ("course_revenue", "Ingreso por Cursos"),
    ("total_otros", "Otros"),
    ("otros_revenue", "Ingreso por Otros"),
    ("total_revenue", "Ingreso Total"),
    ("expected_revenue", "Ingreso Esperado"),
    ("expected_cost", "Costo Esperado"),
    ("uncategorized_revenue", "Sin Categorizar"),
    ("unknown_site_revenue", "Ingreso Sitio Desconocido"),
    ("unknown_site_expected_revenue", "Esperado Sitio Desconocido"),
    ("profit_margin", "Margen de Utilidad"),
]

_COMPARISON_COLUMNS = [
    ExcelColumn("metric", "Métrica"),
    ExcelColumn("actual", "Actual"),
    ExcelColumn("anterior", "Anterior"),
    ExcelColumn("delta_pct", "Δ%"),
]


def build_total_sales_export_worksheets(
    response: TotalSalesResponse,
    *,
    include_charts: bool = True,
) -> list[ExcelWorksheetSpec]:
    base = response.current
    comp = response.comparison
    summary_row = {
        "total_clients": base.total_clients,
        "total_exams": base.total_exams,
        "exam_revenue": base.exam_revenue,
        "total_books": base.total_books,
        "book_revenue": base.book_revenue,
        "total_courses": base.total_courses,
        "course_revenue": base.course_revenue,
        "total_otros": base.total_otros,
        "otros_revenue": base.otros_revenue,
        "total_revenue": base.total_revenue,
        "expected_revenue": base.expected_revenue,
        "expected_cost": base.expected_cost,
        "uncategorized_revenue": base.uncategorized_revenue,
        "unknown_site_revenue": base.unknown_site_revenue,
        "unknown_site_expected_revenue": base.unknown_site_expected_revenue,
        "profit_margin": base.profit_margin,
        "prior_year_revenue": comp.data.total_revenue if comp else 0.0,
        "growth_pct": comp.deltas.get("total_revenue").pct_change if comp else None,
    }
    worksheets = [
        ExcelWorksheetSpec(
            name="Ventas Totales",
            columns=TOTAL_SALES_SUMMARY_COLUMNS,
            rows=[summary_row],
        )
    ]

    if comp:
        comp_data = comp.data
        comp_rows = []
        for key, label in _COMPARISON_KPI_KEYS:
            actual = getattr(base, key)
            anterior = getattr(comp_data, key)
            delta = comp.deltas.get(key)
            delta_pct = (
                round(delta.pct_change, 1) if delta and delta.pct_change is not None else None
            )
            comp_rows.append(
                {"metric": label, "actual": actual, "anterior": anterior, "delta_pct": delta_pct}
            )
        worksheets.append(
            ExcelWorksheetSpec(
                name="Comparación",
                columns=_COMPARISON_COLUMNS,
                rows=comp_rows,
                note=f"Período comparativo: {comp.meta.date_from} – {comp.meta.date_to}",
            )
        )

    if include_charts:
        comp_trend_pts = comp.data.trend_points if comp else []
        comp_geo_by_dim = {p.dimension: p.revenue for p in comp.data.geo_points} if comp else {}
        max_length = max(len(base.trend_points), len(base.geo_points), 1)
        chart_rows = []
        for index in range(max_length):
            trend_point = base.trend_points[index] if index < len(base.trend_points) else None
            geo_point = base.geo_points[index] if index < len(base.geo_points) else None
            row: dict = {
                "month": trend_point.month if trend_point else "",
                "trend_revenue": trend_point.revenue if trend_point else 0,
                "dimension": geo_point.dimension if geo_point else "",
                "geo_revenue": geo_point.revenue if geo_point else 0,
            }
            if comp:
                row["comp_trend_revenue"] = (
                    comp_trend_pts[index].revenue if index < len(comp_trend_pts) else 0
                )
                row["comp_geo_revenue"] = (
                    comp_geo_by_dim.get(geo_point.dimension, 0) if geo_point else 0
                )
            chart_rows.append(row)
        chart_columns = list(TOTAL_SALES_CHART_COLUMNS)
        if comp:
            chart_columns = [
                ExcelColumn("month", "Month"),
                ExcelColumn("trend_revenue", "Ingresos (Actual)"),
                ExcelColumn("comp_trend_revenue", "Ingresos (Anterior)"),
                ExcelColumn("dimension", "Country"),
                ExcelColumn("geo_revenue", "Ingresos (Actual)"),
                ExcelColumn("comp_geo_revenue", "Ingresos (Anterior)"),
            ]
        worksheets.append(
            ExcelWorksheetSpec(
                name="Ventas Totales Charts",
                columns=chart_columns,
                rows=chart_rows,
                post_process=add_total_sales_charts,
                note=f"Período comparativo: {comp.meta.date_from} – {comp.meta.date_to}"
                if comp
                else None,
            )
        )
    return worksheets
