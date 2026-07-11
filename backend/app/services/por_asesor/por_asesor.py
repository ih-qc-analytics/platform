import asyncio
from collections import defaultdict
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import text

from app.enums import BaseCurrency
from app.reporting.database import ReportingSessionLocal
from app.schemas.pdf import (
    AsesorDetailPDFPayload,
    PDFKpiItem,
    PDFTable,
    PDFTableCellDelta,
    PDFTableRow,
    PorAsesorPDFPayload,
)
from app.schemas.reports import (
    AsesorDetailBase,
    AsesorDetailComparison,
    AsesorDetailResponse,
    AsesorFilters,
    AsesorReportBase,
    AsesorReportComparison,
    AsesorReportResponse,
    AsesorRow,
    BusinessStatusDetail,
    ExamBrandDetail,
    MetricDelta,
)
from app.services.exports.excel import ExcelColumn, ExcelWorksheetSpec
from app.services.exports.pdf_helpers import (
    build_pdf_header,
    format_currency,
    format_delta,
    format_growth,
    format_integer,
    format_percent,
)
from app.services.por_asesor.product_grouping import EXAM_CATEGORY_ORDER
from app.services.por_asesor.repository import (
    fetch_books_courses_presence_rows,
    fetch_comparison_rows_by_seller_ids,
    fetch_detail_exam_breakdown_rows,
    fetch_paginated_summary_rows,
    fetch_school_allocated_revenue_metric_rows,
    fetch_school_product_metric_rows,
    fetch_school_presence_rows,
    fetch_summary_exam_breakdown_rows_by_seller_ids,
    _line_where,
    _payment_where,
)
from app.services.utils.date_utils import (
    percent_change,
    resolve_comparison_range,
)
from app.services.utils.report_currency import (
    line_expected_cost_column,
    line_expected_total_column,
    line_paid_total_column,
    payment_amount_column,
)

ASESOR_SUMMARY_COLUMNS = [
    ExcelColumn("seller_name", "Asesor"),
    *[ExcelColumn(category, category) for category in EXAM_CATEGORY_ORDER],
    ExcelColumn("total_books", "Libros"),
    ExcelColumn("total_courses", "Cursos"),
    ExcelColumn("exam_revenue", "Ingreso Exámenes"),
    ExcelColumn("book_revenue", "Ingreso Libros"),
    ExcelColumn("course_revenue", "Ingreso Cursos"),
    ExcelColumn("ganados", "Ganados"),
    ExcelColumn("perdidos", "Perdidos"),
    ExcelColumn("mantenidos", "Mantenidos"),
    ExcelColumn("books_courses_ganados", "L+C Ganados"),
    ExcelColumn("books_courses_perdidos", "L+C Perdidos"),
    ExcelColumn("books_courses_mantenidos", "L+C Mantenidos"),
    ExcelColumn("uncategorized_revenue", "Ingreso Sin Categorizar"),
    ExcelColumn("total_revenue", "Ingreso Total"),
    ExcelColumn("allocated_revenue", "Ingreso Asignado"),
    ExcelColumn("expected_revenue", "Ingreso Esperado"),
    ExcelColumn("expected_cost", "Costo Esperado"),
    ExcelColumn("profit_margin", "Margen (%)"),
]


async def fetch_seller_name(seller_id: int) -> str | None:
    async with ReportingSessionLocal() as session:
        row = (
            await session.execute(
                text("SELECT seller_name FROM report_payments WHERE seller_id = :id LIMIT 1"),
                {"id": seller_id},
            )
        ).fetchone()
        return row.seller_name if row else None


async def fetch_detail_aggregate_row(
    seller_id: int,
    filters: AsesorFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
):
    payment_where, payment_params = _payment_where(filters, seller_id=seller_id)
    line_where, line_params = _line_where(
        filters, seller_id=seller_id, require_product_breakdown=True
    )
    payment_amount = payment_amount_column(base_currency)
    paid_total = line_paid_total_column(base_currency)
    expected_cost_col = line_expected_cost_column(base_currency)
    expected_total_col = line_expected_total_column(base_currency)

    async def fetch_payment_row():
        async with ReportingSessionLocal() as session:
            return (
                await session.execute(
                    text(f"""
                SELECT
                    COUNT(DISTINCT lead_id) AS total_schools,
                    COALESCE(SUM({payment_amount}), 0) AS total_revenue
                FROM report_payments
                WHERE {payment_where}
            """),
                    payment_params,
                )
            ).fetchone()

    async def fetch_line_row():
        async with ReportingSessionLocal() as session:
            return (
                await session.execute(
                    text(f"""
                SELECT
                    COALESCE(SUM(CASE WHEN product_type = 'exam'   THEN quantity    ELSE 0 END), 0) AS total_exams,
                    COALESCE(SUM(CASE WHEN product_type = 'book'   THEN quantity    ELSE 0 END), 0) AS total_books,
                    COALESCE(SUM(CASE WHEN product_type = 'course' THEN quantity    ELSE 0 END), 0) AS total_courses,
                    COALESCE(SUM({paid_total}), 0)                                                        AS allocated_revenue,
                    COALESCE(SUM(CASE WHEN product_type = 'exam'   THEN {paid_total} ELSE 0 END), 0)      AS exam_revenue,
                    COALESCE(SUM(CASE WHEN product_type = 'book'   THEN {paid_total} ELSE 0 END), 0)      AS book_revenue,
                    COALESCE(SUM(CASE WHEN product_type = 'course' THEN {paid_total} ELSE 0 END), 0)      AS course_revenue,
                    COALESCE(SUM({expected_cost_col}), 0)                                                 AS expected_cost,
                    COALESCE(SUM({expected_total_col}), 0)                                                AS expected_revenue
                FROM report_line_items
                WHERE {line_where}
            """),
                    line_params,
                )
            ).fetchone()

    payment_row, line_row = await asyncio.gather(fetch_payment_row(), fetch_line_row())
    total_revenue = float((payment_row.total_revenue or 0) if payment_row else 0)
    allocated_revenue = float((line_row.allocated_revenue or 0) if line_row else 0)
    exam_revenue = float((line_row.exam_revenue or 0) if line_row else 0)
    book_revenue = float((line_row.book_revenue or 0) if line_row else 0)
    course_revenue = float((line_row.course_revenue or 0) if line_row else 0)
    expected_cost = float((line_row.expected_cost or 0) if line_row else 0)
    expected_revenue = float((line_row.expected_revenue or 0) if line_row else 0)
    return SimpleNamespace(
        total_schools=int((payment_row.total_schools or 0) if payment_row else 0),
        total_revenue=total_revenue,
        total_exams=int((line_row.total_exams or 0) if line_row else 0),
        total_books=int((line_row.total_books or 0) if line_row else 0),
        total_courses=int((line_row.total_courses or 0) if line_row else 0),
        exam_revenue=exam_revenue,
        book_revenue=book_revenue,
        course_revenue=course_revenue,
        uncategorized_revenue=total_revenue - allocated_revenue,
        allocated_revenue=allocated_revenue,
        expected_revenue=expected_revenue,
        expected_cost=expected_cost,
        profit_margin=((allocated_revenue - expected_cost) / allocated_revenue * 100)
        if allocated_revenue > 0
        else 0.0,
    )


async def fetch_detail_geo_rows(seller_id: int, filters: AsesorFilters) -> list:
    where, params = _payment_where(filters, seller_id=seller_id)
    async with ReportingSessionLocal() as session:
        return (
            await session.execute(
                text(f"""
            SELECT DISTINCT
                site AS country,
                zone_name AS zone,
                state_name AS state,
                city AS city
            FROM report_payments
            WHERE {where}
        """),
                params,
            )
        ).fetchall()


def fill_summary_exam_categories(breakdown: dict) -> dict:
    return {cat: int(breakdown.get(cat, 0) or 0) for cat in EXAM_CATEGORY_ORDER}


def map_summary_exam_breakdowns(rows) -> dict[int, dict[str, int]]:
    exam_breakdowns: dict[int, dict[str, int]] = {}
    for row in rows:
        seller_breakdown = exam_breakdowns.setdefault(
            int(row.seller_id), {cat: 0 for cat in EXAM_CATEGORY_ORDER}
        )
        if row.exam_category in seller_breakdown:
            seller_breakdown[row.exam_category] += int(row.exam_count or 0)
    return {
        sid: fill_summary_exam_categories(breakdown) for sid, breakdown in exam_breakdowns.items()
    }


def map_detail_exam_breakdown(rows) -> dict[str, ExamBrandDetail]:
    breakdown = {
        cat: ExamBrandDetail(exams=0, schools=0, revenue=0.0) for cat in EXAM_CATEGORY_ORDER
    }
    for row in rows:
        if row.exam_category in breakdown:
            current = breakdown[row.exam_category]
            breakdown[row.exam_category] = ExamBrandDetail(
                exams=current.exams + int(row.exams or 0),
                schools=current.schools + int(row.schools or 0),
                revenue=current.revenue + float(row.revenue or 0),
            )
    return breakdown


def unique_sorted_values(rows, field: str) -> list[str]:
    return sorted({getattr(row, field) for row in rows if getattr(row, field)})


def empty_status() -> BusinessStatusDetail:
    return BusinessStatusDetail(schools=0, exams=0, books=0, courses=0, revenue=0.0)


def build_status_map(
    current_rows,
    comparison_rows,
    current_allocated_metric_rows,
    comparison_allocated_metric_rows,
    current_exam_metric_rows,
    comparison_exam_metric_rows,
):
    current_by_seller: dict[int, set[int]] = defaultdict(set)
    comparison_by_seller: dict[int, set[int]] = defaultdict(set)
    current_allocated_metrics: dict[tuple[int, int], float] = {}
    comparison_allocated_metrics: dict[tuple[int, int], float] = {}
    current_exam_metrics: dict[tuple[int, int], int] = {}
    comparison_exam_metrics: dict[tuple[int, int], int] = {}
    current_book_metrics: dict[tuple[int, int], int] = {}
    comparison_book_metrics: dict[tuple[int, int], int] = {}
    current_course_metrics: dict[tuple[int, int], int] = {}
    comparison_course_metrics: dict[tuple[int, int], int] = {}

    for row in current_rows:
        current_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in comparison_rows:
        comparison_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in current_allocated_metric_rows:
        current_allocated_metrics[(int(row.seller_id), int(row.lead_id))] = float(row.revenue or 0)
    for row in comparison_allocated_metric_rows:
        comparison_allocated_metrics[(int(row.seller_id), int(row.lead_id))] = float(
            row.revenue or 0
        )
    for row in current_exam_metric_rows:
        key = (int(row.seller_id), int(row.lead_id))
        current_exam_metrics[key] = int(row.exams or 0)
        current_book_metrics[key] = int(row.books or 0)
        current_course_metrics[key] = int(row.courses or 0)
    for row in comparison_exam_metric_rows:
        key = (int(row.seller_id), int(row.lead_id))
        comparison_exam_metrics[key] = int(row.exams or 0)
        comparison_book_metrics[key] = int(row.books or 0)
        comparison_course_metrics[key] = int(row.courses or 0)

    status_map: dict[int, dict[str, BusinessStatusDetail]] = {}
    for seller_id in set(current_by_seller) | set(comparison_by_seller):
        current = current_by_seller.get(seller_id, set())
        comparison = comparison_by_seller.get(seller_id, set())
        buckets = {
            "ganado": current - comparison,
            "perdido": comparison - current,
            "mantenido": current & comparison,
        }
        seller_statuses: dict[str, BusinessStatusDetail] = {}
        for status, lead_ids in buckets.items():
            is_perdido = status == "perdido"
            exam_src = comparison_exam_metrics if is_perdido else current_exam_metrics
            book_src = comparison_book_metrics if is_perdido else current_book_metrics
            course_src = comparison_course_metrics if is_perdido else current_course_metrics
            revenue_src = comparison_allocated_metrics if is_perdido else current_allocated_metrics
            seller_statuses[status] = BusinessStatusDetail(
                schools=len(lead_ids),
                exams=sum(exam_src.get((seller_id, lead_id), 0) for lead_id in lead_ids),
                books=sum(book_src.get((seller_id, lead_id), 0) for lead_id in lead_ids),
                courses=sum(course_src.get((seller_id, lead_id), 0) for lead_id in lead_ids),
                revenue=sum(revenue_src.get((seller_id, lead_id), 0.0) for lead_id in lead_ids),
            )
        status_map[seller_id] = seller_statuses
    return status_map


async def fetch_summary_status_counts(
    current_filters: AsesorFilters,
    comparison_filters: AsesorFilters,
    seller_ids: list[int],
) -> dict[int, dict[str, int]]:
    if not seller_ids:
        return {}
    (
        current_rows,
        comparison_rows,
        current_bc_rows,
        comparison_bc_rows,
    ) = await asyncio.gather(
        fetch_school_presence_rows(current_filters),
        fetch_school_presence_rows(comparison_filters),
        fetch_books_courses_presence_rows(current_filters),
        fetch_books_courses_presence_rows(comparison_filters),
    )
    current_by_seller: dict[int, set[int]] = defaultdict(set)
    comparison_by_seller: dict[int, set[int]] = defaultdict(set)
    current_bc_by_seller: dict[int, set[int]] = defaultdict(set)
    comparison_bc_by_seller: dict[int, set[int]] = defaultdict(set)
    for row in current_rows:
        current_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in comparison_rows:
        comparison_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in current_bc_rows:
        current_bc_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in comparison_bc_rows:
        comparison_bc_by_seller[int(row.seller_id)].add(int(row.lead_id))
    return {
        seller_id: {
            "ganado": len(
                current_by_seller.get(seller_id, set()) - comparison_by_seller.get(seller_id, set())
            ),
            "perdido": len(
                comparison_by_seller.get(seller_id, set()) - current_by_seller.get(seller_id, set())
            ),
            "mantenido": len(
                current_by_seller.get(seller_id, set()) & comparison_by_seller.get(seller_id, set())
            ),
            "bc_ganado": len(
                current_bc_by_seller.get(seller_id, set())
                - comparison_bc_by_seller.get(seller_id, set())
            ),
            "bc_perdido": len(
                comparison_bc_by_seller.get(seller_id, set())
                - current_bc_by_seller.get(seller_id, set())
            ),
            "bc_mantenido": len(
                current_bc_by_seller.get(seller_id, set())
                & comparison_bc_by_seller.get(seller_id, set())
            ),
        }
        for seller_id in seller_ids
    }


def build_asesor_report_base(
    summary_rows,
    exam_breakdowns: dict[int, dict[str, int]],
    status_counts: dict[int, dict[str, int]],
    *,
    next_cursor: str | None,
    has_more: bool,
) -> AsesorReportBase:
    rows = []
    for row in summary_rows:
        sid = int(row.seller_id)
        total_revenue = float(row.total_revenue or 0)
        allocated_rev = float(getattr(row, "allocated_revenue", 0) or 0)
        expected_cost = float(getattr(row, "expected_cost", 0) or 0)
        rows.append(
            AsesorRow(
                seller_id=sid,
                seller_name=row.seller_name,
                exam_breakdown=exam_breakdowns.get(sid, fill_summary_exam_categories({})),
                ganados=int(status_counts.get(sid, {}).get("ganado", 0)),
                perdidos=int(status_counts.get(sid, {}).get("perdido", 0)),
                mantenidos=int(status_counts.get(sid, {}).get("mantenido", 0)),
                total_revenue=total_revenue,
                uncategorized_revenue=total_revenue - allocated_rev,
                allocated_revenue=allocated_rev,
                expected_revenue=float(getattr(row, "expected_revenue", 0) or 0),
                total_books=int(getattr(row, "total_books", 0) or 0),
                total_courses=int(getattr(row, "total_courses", 0) or 0),
                exam_revenue=float(getattr(row, "exam_revenue", 0) or 0),
                book_revenue=float(getattr(row, "book_revenue", 0) or 0),
                course_revenue=float(getattr(row, "course_revenue", 0) or 0),
                books_courses_ganados=int(status_counts.get(sid, {}).get("bc_ganado", 0)),
                books_courses_perdidos=int(status_counts.get(sid, {}).get("bc_perdido", 0)),
                books_courses_mantenidos=int(status_counts.get(sid, {}).get("bc_mantenido", 0)),
                expected_cost=expected_cost,
                profit_margin=float(getattr(row, "profit_margin", 0) or 0),
            )
        )
    return AsesorReportBase(rows=rows, next_cursor=next_cursor, has_more=has_more)


def build_asesor_detail_base(
    seller_name: str,
    aggregate_row,
    geo_rows,
    exam_breakdown: dict[str, ExamBrandDetail],
    status_map: dict[str, BusinessStatusDetail],
) -> AsesorDetailBase:
    return AsesorDetailBase(
        seller_name=seller_name,
        countries=unique_sorted_values(geo_rows, "country"),
        zones=unique_sorted_values(geo_rows, "zone"),
        states=unique_sorted_values(geo_rows, "state"),
        cities=unique_sorted_values(geo_rows, "city"),
        total_schools=int((aggregate_row.total_schools or 0) if aggregate_row else 0),
        total_exams=int((aggregate_row.total_exams or 0) if aggregate_row else 0),
        total_revenue=float((aggregate_row.total_revenue or 0) if aggregate_row else 0),
        uncategorized_revenue=float(
            (aggregate_row.uncategorized_revenue or 0) if aggregate_row else 0
        ),
        exam_breakdown=exam_breakdown,
        ganados=status_map.get("ganado", empty_status()),
        perdidos=status_map.get("perdido", empty_status()),
        mantenidos=status_map.get("mantenido", empty_status()),
        total_books=int((aggregate_row.total_books or 0) if aggregate_row else 0),
        total_courses=int((aggregate_row.total_courses or 0) if aggregate_row else 0),
        book_revenue=float((aggregate_row.book_revenue or 0) if aggregate_row else 0),
        course_revenue=float((aggregate_row.course_revenue or 0) if aggregate_row else 0),
        allocated_revenue=float((aggregate_row.allocated_revenue or 0) if aggregate_row else 0),
        expected_revenue=float((aggregate_row.expected_revenue or 0) if aggregate_row else 0),
        expected_cost=float((aggregate_row.expected_cost or 0) if aggregate_row else 0),
        profit_margin=float((aggregate_row.profit_margin or 0) if aggregate_row else 0),
    )


def _report_deltas(
    current: AsesorReportBase, comparison: AsesorReportBase
) -> dict[str, MetricDelta]:
    current_total_revenue = sum(row.total_revenue for row in current.rows)
    comparison_total_revenue = sum(row.total_revenue for row in comparison.rows)
    current_uncategorized = sum(row.uncategorized_revenue for row in current.rows)
    comparison_uncategorized = sum(row.uncategorized_revenue for row in comparison.rows)
    current_exams = sum(sum(row.exam_breakdown.values()) for row in current.rows)
    comparison_exams = sum(sum(row.exam_breakdown.values()) for row in comparison.rows)
    return {
        "total_revenue": MetricDelta(
            comparison_value=comparison_total_revenue,
            pct_change=percent_change(current_total_revenue, comparison_total_revenue),
        ),
        "uncategorized_revenue": MetricDelta(
            comparison_value=comparison_uncategorized,
            pct_change=percent_change(current_uncategorized, comparison_uncategorized),
        ),
        "total_exams": MetricDelta(
            comparison_value=float(comparison_exams),
            pct_change=percent_change(current_exams, comparison_exams),
        ),
    }


def _detail_deltas(
    current: AsesorDetailBase, comparison: AsesorDetailBase
) -> dict[str, MetricDelta]:
    return {
        "total_schools": MetricDelta(
            comparison_value=float(comparison.total_schools),
            pct_change=percent_change(current.total_schools, comparison.total_schools),
        ),
        "total_exams": MetricDelta(
            comparison_value=float(comparison.total_exams),
            pct_change=percent_change(current.total_exams, comparison.total_exams),
        ),
        "total_revenue": MetricDelta(
            comparison_value=comparison.total_revenue,
            pct_change=percent_change(current.total_revenue, comparison.total_revenue),
        ),
        "uncategorized_revenue": MetricDelta(
            comparison_value=comparison.uncategorized_revenue,
            pct_change=percent_change(
                current.uncategorized_revenue, comparison.uncategorized_revenue
            ),
        ),
    }


async def _get_asesor_report_base(
    current_filters: AsesorFilters,
    comparison_filters: AsesorFilters,
    *,
    limit: int,
    cursor: str | None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
):
    summary_rows, has_more, next_cursor = await fetch_paginated_summary_rows(
        current_filters,
        limit=limit,
        cursor=cursor,
        base_currency=base_currency,
    )
    seller_ids = [int(row.seller_id) for row in summary_rows]
    breakdown_rows, status_counts = await asyncio.gather(
        fetch_summary_exam_breakdown_rows_by_seller_ids(seller_ids, current_filters),
        fetch_summary_status_counts(current_filters, comparison_filters, seller_ids),
    )
    return build_asesor_report_base(
        summary_rows,
        map_summary_exam_breakdowns(breakdown_rows),
        status_counts,
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def get_asesor_report(
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> AsesorReportResponse:
    current_filters = filters.model_copy(
        update={"show_comparison": False, "comparison_date_from": None, "comparison_date_to": None}
    )
    comparison_meta = resolve_comparison_range(filters)

    if comparison_meta is None:
        current = await _get_asesor_report_base(
            current_filters,
            current_filters,
            limit=current_filters.limit,
            cursor=current_filters.cursor,
            base_currency=base_currency,
        )
        return AsesorReportResponse(current=current, comparison_mode=None, comparison=None)

    comparison_filters = current_filters.model_copy(
        update={
            "date_from": comparison_meta.date_from,
            "date_to": comparison_meta.date_to,
            "cursor": None,
        }
    )

    current = await _get_asesor_report_base(
        current_filters,
        comparison_filters,
        limit=current_filters.limit,
        cursor=current_filters.cursor,
        base_currency=base_currency,
    )
    seller_ids = [row.seller_id for row in current.rows]
    (
        comparison_summary_rows,
        comparison_breakdown_rows,
        comparison_status_counts,
    ) = await asyncio.gather(
        fetch_comparison_rows_by_seller_ids(
            seller_ids, comparison_filters, base_currency=base_currency
        ),
        fetch_summary_exam_breakdown_rows_by_seller_ids(seller_ids, comparison_filters),
        fetch_summary_status_counts(comparison_filters, current_filters, seller_ids),
    )
    comparison = build_asesor_report_base(
        comparison_summary_rows,
        map_summary_exam_breakdowns(comparison_breakdown_rows),
        comparison_status_counts,
        next_cursor=None,
        has_more=False,
    )
    return AsesorReportResponse(
        current=current,
        comparison_mode=comparison_meta.mode,
        comparison=AsesorReportComparison(
            meta=comparison_meta, data=comparison, deltas=_report_deltas(current, comparison)
        ),
    )


async def _get_asesor_detail_base(
    seller_id: int,
    filters: AsesorFilters,
    comparison_filters: AsesorFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> AsesorDetailBase:
    seller_name = await fetch_seller_name(seller_id)
    if seller_name is None:
        raise HTTPException(status_code=404, detail="Seller not found")

    (
        aggregate_row,
        geo_rows,
        breakdown_rows,
        current_presence,
        comparison_presence,
        current_allocated_rows,
        comparison_allocated_rows,
        current_exam_rows,
        comparison_exam_rows,
    ) = await asyncio.gather(
        fetch_detail_aggregate_row(seller_id, filters, base_currency=base_currency),
        fetch_detail_geo_rows(seller_id, filters),
        fetch_detail_exam_breakdown_rows(seller_id, filters, base_currency=base_currency),
        fetch_school_presence_rows(filters, seller_id=seller_id),
        fetch_school_presence_rows(comparison_filters, seller_id=seller_id),
        fetch_school_allocated_revenue_metric_rows(
            filters, seller_id=seller_id, base_currency=base_currency
        ),
        fetch_school_allocated_revenue_metric_rows(
            comparison_filters, seller_id=seller_id, base_currency=base_currency
        ),
        fetch_school_product_metric_rows(filters, seller_id=seller_id),
        fetch_school_product_metric_rows(comparison_filters, seller_id=seller_id),
    )
    status_map = build_status_map(
        current_presence,
        comparison_presence,
        current_allocated_rows,
        comparison_allocated_rows,
        current_exam_rows,
        comparison_exam_rows,
    ).get(seller_id, {})
    return build_asesor_detail_base(
        seller_name,
        aggregate_row,
        geo_rows,
        map_detail_exam_breakdown(breakdown_rows),
        status_map,
    )


async def get_asesor_detail(
    seller_id: int,
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> AsesorDetailResponse:
    current_filters = filters.model_copy(
        update={"show_comparison": False, "comparison_date_from": None, "comparison_date_to": None}
    )
    comparison_meta = resolve_comparison_range(filters)

    if comparison_meta is None:
        current = await _get_asesor_detail_base(
            seller_id,
            current_filters,
            current_filters,
            base_currency=base_currency,
        )
        return AsesorDetailResponse(current=current, comparison_mode=None, comparison=None)

    comparison_filters = current_filters.model_copy(
        update={
            "date_from": comparison_meta.date_from,
            "date_to": comparison_meta.date_to,
        }
    )
    current, comparison = await asyncio.gather(
        _get_asesor_detail_base(
            seller_id, current_filters, comparison_filters, base_currency=base_currency
        ),
        _get_asesor_detail_base(
            seller_id, comparison_filters, current_filters, base_currency=base_currency
        ),
    )
    return AsesorDetailResponse(
        current=current,
        comparison_mode=comparison_meta.mode,
        comparison=AsesorDetailComparison(
            meta=comparison_meta, data=comparison, deltas=_detail_deltas(current, comparison)
        ),
    )


async def get_all_asesor_report_rows(
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> AsesorReportResponse:
    comparison_meta = resolve_comparison_range(filters)
    current_filters = filters.model_copy(
        update={"show_comparison": False, "comparison_date_from": None, "comparison_date_to": None}
    )

    # Collect all current rows; suppress per-page comparison (fetched in one batch below)
    all_rows: list[AsesorRow] = []
    cursor = current_filters.cursor
    while True:
        page = await get_asesor_report(
            current_filters.model_copy(update={"cursor": cursor}),
            country_rates=country_rates,
            base_currency=base_currency,
        )
        all_rows.extend(page.current.rows)
        if not page.current.has_more or page.current.next_cursor is None:
            break
        cursor = page.current.next_cursor

    current = AsesorReportBase(rows=all_rows, next_cursor=None, has_more=False)

    if comparison_meta is None:
        return AsesorReportResponse(current=current, comparison_mode=None, comparison=None)

    # One batch comparison fetch for ALL accumulated seller_ids
    seller_ids = [row.seller_id for row in all_rows]
    comparison_filters = current_filters.model_copy(
        update={
            "date_from": comparison_meta.date_from,
            "date_to": comparison_meta.date_to,
            "cursor": None,
        }
    )
    (
        comp_summary_rows,
        comp_breakdown_rows,
        comp_status_counts,
    ) = await asyncio.gather(
        fetch_comparison_rows_by_seller_ids(
            seller_ids, comparison_filters, base_currency=base_currency
        ),
        fetch_summary_exam_breakdown_rows_by_seller_ids(seller_ids, comparison_filters),
        fetch_summary_status_counts(comparison_filters, current_filters, seller_ids),
    )
    comparison_base = build_asesor_report_base(
        comp_summary_rows,
        map_summary_exam_breakdowns(comp_breakdown_rows),
        comp_status_counts,
        next_cursor=None,
        has_more=False,
    )
    return AsesorReportResponse(
        current=current,
        comparison_mode=comparison_meta.mode,
        comparison=AsesorReportComparison(
            meta=comparison_meta,
            data=comparison_base,
            deltas=_report_deltas(current, comparison_base),
        ),
    )


async def get_asesor_details_for_rows(
    rows: list[AsesorRow],
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> list[AsesorDetailBase]:
    if not rows:
        return []
    results = await asyncio.gather(
        *(
            _get_asesor_detail_base(
                row.seller_id,
                filters,
                filters,
                base_currency=base_currency,
            )
            for row in rows
        )
    )
    return list(results)


def build_asesor_export_filters_for_all(filters: AsesorFilters) -> AsesorFilters:
    return filters.model_copy(
        update={
            "countries": [],
            "zones": [],
            "states": [],
            "cities": [],
            "sellers": [],
            "cursor": None,
            "limit": 100,
        }
    )


def build_asesor_filtered_export_filters(filters: AsesorFilters) -> AsesorFilters:
    """Strip cursor/limit so the filtered export fetches all matching rows, not just the current page."""
    return filters.model_copy(
        update={
            "cursor": None,
            "limit": 100,
            "show_comparison": False,
            # countries, zones, states, cities, sellers, sort_by, sort_dir preserved
        }
    )


def build_asesor_export_worksheets(
    report: AsesorReportResponse, details: list[AsesorDetailBase]
) -> list[ExcelWorksheetSpec]:
    summary_rows = []
    for row in report.current.rows:
        summary_row = {
            "seller_name": row.seller_name,
            "ganados": row.ganados,
            "perdidos": row.perdidos,
            "mantenidos": row.mantenidos,
            "total_books": row.total_books,
            "total_courses": row.total_courses,
            "exam_revenue": row.exam_revenue,
            "book_revenue": row.book_revenue,
            "course_revenue": row.course_revenue,
            "uncategorized_revenue": row.uncategorized_revenue,
            "total_revenue": row.total_revenue,
            "allocated_revenue": row.allocated_revenue,
            "expected_revenue": row.expected_revenue,
            "expected_cost": row.expected_cost,
            "profit_margin": row.profit_margin,
        }
        for cat in EXAM_CATEGORY_ORDER:
            summary_row[cat] = int(row.exam_breakdown.get(cat, 0) or 0)
        summary_rows.append(summary_row)

    detail_rows = []
    for detail in details:
        detail_row = {
            "seller_name": detail.seller_name,
            "countries": ", ".join(detail.countries),
            "zones": ", ".join(detail.zones),
            "states": ", ".join(detail.states),
            "cities": ", ".join(detail.cities),
            "total_schools": detail.total_schools,
            "total_exams": detail.total_exams,
            "total_books": detail.total_books,
            "total_courses": detail.total_courses,
            "book_revenue": detail.book_revenue,
            "course_revenue": detail.course_revenue,
            "uncategorized_revenue": detail.uncategorized_revenue,
            "total_revenue": detail.total_revenue,
            "allocated_revenue": detail.allocated_revenue,
            "expected_revenue": detail.expected_revenue,
            "expected_cost": detail.expected_cost,
            "profit_margin": detail.profit_margin,
            "ganados_schools": detail.ganados.schools,
            "ganados_exams": detail.ganados.exams,
            "ganados_revenue": detail.ganados.revenue,
            "perdidos_schools": detail.perdidos.schools,
            "perdidos_exams": detail.perdidos.exams,
            "perdidos_revenue": detail.perdidos.revenue,
            "mantenidos_schools": detail.mantenidos.schools,
            "mantenidos_exams": detail.mantenidos.exams,
            "mantenidos_revenue": detail.mantenidos.revenue,
        }
        for cat in EXAM_CATEGORY_ORDER:
            cat_detail = detail.exam_breakdown.get(
                cat, ExamBrandDetail(exams=0, schools=0, revenue=0.0)
            )
            detail_row[f"{cat}_exams"] = cat_detail.exams
            detail_row[f"{cat}_schools"] = cat_detail.schools
            detail_row[f"{cat}_revenue"] = cat_detail.revenue
        detail_rows.append(detail_row)

    summary_columns = [
        c
        for c in ASESOR_SUMMARY_COLUMNS
        if c.header not in ("Ganados", "Perdidos", "Mantenidos") or report.comparison
    ]

    detail_columns = [
        ExcelColumn("seller_name", "Asesor"),
        ExcelColumn("countries", "Países"),
        ExcelColumn("zones", "Sedes"),
        ExcelColumn("states", "Estados"),
        ExcelColumn("cities", "Ciudades"),
        ExcelColumn("total_schools", "Total Colegios"),
        ExcelColumn("total_exams", "Total Exámenes"),
        ExcelColumn("total_books", "Total Libros"),
        ExcelColumn("total_courses", "Total Cursos"),
        ExcelColumn("book_revenue", "Ingreso Libros"),
        ExcelColumn("course_revenue", "Ingreso Cursos"),
        ExcelColumn("uncategorized_revenue", "Ingreso Sin Categorizar"),
        ExcelColumn("total_revenue", "Ingreso Total"),
        ExcelColumn("allocated_revenue", "Ingreso Asignado"),
        ExcelColumn("expected_revenue", "Ingreso Esperado"),
        ExcelColumn("expected_cost", "Costo Esperado"),
        ExcelColumn("profit_margin", "Margen (%)"),
    ]
    for _cat in EXAM_CATEGORY_ORDER:
        detail_columns.extend(
            [
                ExcelColumn(f"{_cat}_exams", f"{_cat} Exámenes"),
                ExcelColumn(f"{_cat}_schools", f"{_cat} Colegios"),
                ExcelColumn(f"{_cat}_revenue", f"{_cat} Ingresos"),
            ]
        )
    if report.comparison:
        detail_columns.extend(
            [
                ExcelColumn("ganados_schools", "Ganados Colegios"),
                ExcelColumn("ganados_exams", "Ganados Exámenes"),
                ExcelColumn("ganados_revenue", "Ganados Ingresos"),
                ExcelColumn("perdidos_schools", "Perdidos Colegios"),
                ExcelColumn("perdidos_exams", "Perdidos Exámenes"),
                ExcelColumn("perdidos_revenue", "Perdidos Ingresos"),
                ExcelColumn("mantenidos_schools", "Mantenidos Colegios"),
                ExcelColumn("mantenidos_exams", "Mantenidos Exámenes"),
                ExcelColumn("mantenidos_revenue", "Mantenidos Ingresos"),
            ]
        )

    specs = [
        ExcelWorksheetSpec(name="Por Asesor", columns=summary_columns, rows=summary_rows),
        ExcelWorksheetSpec(name="Por Asesor Detalle", columns=detail_columns, rows=detail_rows),
    ]

    if report.comparison:
        comp_by_seller = {r.seller_name: r for r in report.comparison.data.rows}
        comparison_rows = []
        for row in report.current.rows:
            comp = comp_by_seller.get(row.seller_name)

            def _pct(act: float, ant: float) -> float | None:
                return round((act - ant) / ant * 100, 1) if ant else None

            comparison_rows.append(
                {
                    "seller_name": row.seller_name,
                    "ganados_act": row.ganados,
                    "ganados_ant": comp.ganados if comp else None,
                    "ganados_pct": _pct(row.ganados, comp.ganados) if comp else None,
                    "perdidos_act": row.perdidos,
                    "perdidos_ant": comp.perdidos if comp else None,
                    "perdidos_pct": _pct(row.perdidos, comp.perdidos) if comp else None,
                    "uncategorized_act": row.uncategorized_revenue,
                    "uncategorized_ant": comp.uncategorized_revenue if comp else None,
                    "uncategorized_pct": _pct(row.uncategorized_revenue, comp.uncategorized_revenue)
                    if comp
                    else None,
                    "revenue_act": row.total_revenue,
                    "revenue_ant": comp.total_revenue if comp else None,
                    "revenue_pct": _pct(row.total_revenue, comp.total_revenue) if comp else None,
                }
            )
        specs.append(
            ExcelWorksheetSpec(
                name="Comparación",
                columns=[
                    ExcelColumn("seller_name", "Asesor"),
                    ExcelColumn("ganados_act", "Ganados (Act.)"),
                    ExcelColumn("ganados_ant", "Ganados (Ant.)"),
                    ExcelColumn("ganados_pct", "Ganados Δ%"),
                    ExcelColumn("perdidos_act", "Perdidos (Act.)"),
                    ExcelColumn("perdidos_ant", "Perdidos (Ant.)"),
                    ExcelColumn("perdidos_pct", "Perdidos Δ%"),
                    ExcelColumn("uncategorized_act", "Sin Cat. (Act.)"),
                    ExcelColumn("uncategorized_ant", "Sin Cat. (Ant.)"),
                    ExcelColumn("uncategorized_pct", "Sin Cat. Δ%"),
                    ExcelColumn("revenue_act", "Valor Total (Act.)"),
                    ExcelColumn("revenue_ant", "Valor Total (Ant.)"),
                    ExcelColumn("revenue_pct", "Valor Total Δ%"),
                ],
                rows=comparison_rows,
                note=f"Período comparativo: {report.comparison.meta.date_from} – {report.comparison.meta.date_to}",
            )
        )

    return specs


async def build_por_asesor_pdf_payload(
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> PorAsesorPDFPayload:
    report = await get_all_asesor_report_rows(
        build_asesor_export_filters_for_all(filters),
        country_rates=country_rates,
        base_currency=base_currency,
    )
    total_revenue = sum(row.total_revenue for row in report.current.rows)
    total_uncategorized = sum(row.uncategorized_revenue for row in report.current.rows)
    total_exams = sum(sum(row.exam_breakdown.values()) for row in report.current.rows)
    total_ganados = sum(row.ganados for row in report.current.rows)
    total_perdidos = sum(row.perdidos for row in report.current.rows)
    total_mantenidos = sum(row.mantenidos for row in report.current.rows)
    total_allocated = sum(row.allocated_revenue for row in report.current.rows)
    total_expected = sum(row.expected_revenue for row in report.current.rows)
    total_cost = sum(row.expected_cost for row in report.current.rows)
    total_margin = (
        ((total_allocated - total_cost) / total_allocated * 100) if total_allocated > 0 else 0.0
    )

    comp_by_seller = (
        {r.seller_name: r for r in report.comparison.data.rows} if report.comparison else {}
    )

    has_comparison = report.comparison is not None
    # Columns: Asesor(0) Cambridge(1) IELTS(2) MET(3) Otros(4) Libros(5) Cursos(6)
    #           [+Ganados(7) Perdidos(8) Mantenidos(9)] Sin Cat(?) Valor Total(?) Costo Esp.(?) Margen(?)
    n_cols = 16 if has_comparison else 13
    uncategorized_idx = 10 if has_comparison else 7
    revenue_idx = 11 if has_comparison else 8
    allocated_idx = 12 if has_comparison else 9
    expected_idx = 13 if has_comparison else 10
    cost_idx = 14 if has_comparison else 11
    # margin idx not needed for deltas (not computing percent-of-percent)

    # Comparison totals for KPI growth
    comp_rows = report.comparison.data.rows if has_comparison else []
    comp_total_revenue = sum(r.total_revenue for r in comp_rows) if has_comparison else None
    comp_total_exams = (
        sum(sum(r.exam_breakdown.values()) for r in comp_rows) if has_comparison else None
    )
    comp_total_uncategorized = (
        sum(r.uncategorized_revenue for r in comp_rows) if has_comparison else None
    )
    comp_asesores = len(comp_rows) if has_comparison else None
    comp_total_allocated = sum(r.allocated_revenue for r in comp_rows) if has_comparison else None
    comp_total_expected = sum(r.expected_revenue for r in comp_rows) if has_comparison else None
    comp_total_cost = sum(r.expected_cost for r in comp_rows) if has_comparison else None

    def _kw(curr: float, prev: float | None) -> dict:
        if prev is None:
            return {}
        g, gp = format_growth(percent_change(curr, prev))
        return {"growth": g or "N/A", "growth_positive": gp}

    def _cat_exams(breakdown: dict, *keys: str) -> int:
        return sum(int(breakdown.get(k, 0) or 0) for k in keys)

    table_rows = []
    for row in report.current.rows:
        cambridge = _cat_exams(
            row.exam_breakdown, "Cambridge English (Main Suite)", "Cambridge Teaching & Skills"
        )
        ielts = _cat_exams(row.exam_breakdown, "IELTS")
        met = _cat_exams(row.exam_breakdown, "Michigan (MET)")
        otros = _cat_exams(
            row.exam_breakdown, "TEA (Test of English for Aviation)", "Placement & Otros"
        )
        comp = comp_by_seller.get(row.seller_name)
        deltas: list = [None] * n_cols
        if comp:
            comp_cambridge = _cat_exams(
                comp.exam_breakdown, "Cambridge English (Main Suite)", "Cambridge Teaching & Skills"
            )
            comp_ielts = _cat_exams(comp.exam_breakdown, "IELTS")
            comp_met = _cat_exams(comp.exam_breakdown, "Michigan (MET)")
            comp_otros = _cat_exams(
                comp.exam_breakdown, "TEA (Test of English for Aviation)", "Placement & Otros"
            )
            deltas[1] = format_delta(cambridge, comp_cambridge, format_integer)
            deltas[2] = format_delta(ielts, comp_ielts, format_integer)
            deltas[3] = format_delta(met, comp_met, format_integer)
            deltas[4] = format_delta(otros, comp_otros, format_integer)
            deltas[5] = format_delta(row.total_books, comp.total_books, format_integer)
            deltas[6] = format_delta(row.total_courses, comp.total_courses, format_integer)
            deltas[uncategorized_idx] = format_delta(
                row.uncategorized_revenue,
                comp.uncategorized_revenue,
                lambda v: format_currency(v, base_currency),
            )
            deltas[revenue_idx] = format_delta(
                row.total_revenue,
                comp.total_revenue,
                lambda v: format_currency(v, base_currency),
            )
            deltas[allocated_idx] = format_delta(
                row.allocated_revenue,
                comp.allocated_revenue,
                lambda v: format_currency(v, base_currency),
            )
            deltas[expected_idx] = format_delta(
                row.expected_revenue,
                comp.expected_revenue,
                lambda v: format_currency(v, base_currency),
            )
            deltas[cost_idx] = format_delta(
                row.expected_cost,
                comp.expected_cost,
                lambda v: format_currency(v, base_currency),
            )
        cells = [
            row.seller_name,
            format_integer(cambridge),
            format_integer(ielts),
            format_integer(met),
            format_integer(otros),
            format_integer(row.total_books),
            format_integer(row.total_courses),
        ]
        if has_comparison:
            cells += [
                format_integer(row.ganados),
                format_integer(row.perdidos),
                format_integer(row.mantenidos),
            ]
        cells += [
            format_currency(row.uncategorized_revenue, base_currency),
            format_currency(row.total_revenue, base_currency),
            format_currency(row.allocated_revenue, base_currency),
            format_currency(row.expected_revenue, base_currency),
            format_currency(row.expected_cost, base_currency),
            format_percent(row.profit_margin),
        ]
        table_rows.append(PDFTableRow(cells=cells, deltas=deltas))

    status_kpis = (
        [
            PDFKpiItem(label="Ganados", value=format_integer(total_ganados)),
            PDFKpiItem(label="Perdidos", value=format_integer(total_perdidos)),
            PDFKpiItem(label="Mantenidos", value=format_integer(total_mantenidos)),
        ]
        if has_comparison
        else []
    )

    table_headers = ["Asesor", "Cambridge", "IELTS", "MET", "Otros", "Libros", "Cursos"]
    table_widths = [4, 2, 2, 2, 2, 2, 2]
    if has_comparison:
        table_headers += ["Ganados", "Perdidos", "Mantenidos"]
        table_widths += [2, 2, 2]
    table_headers += [
        "Sin Categorizar",
        "Valor Total",
        "Ing. Asignado",
        "Ing. Esperado",
        "Costo Esp.",
        "Margen",
    ]
    table_widths += [3, 3, 3, 3, 3, 2]

    return PorAsesorPDFPayload(
        header=build_pdf_header(
            "Resultados por Asesor",
            "Resumen por asesor con familias de exámenes y valor total",
            filters,
            comparison_meta=report.comparison.meta if report.comparison else None,
        ),
        kpis=[
            PDFKpiItem(
                label="Asesores",
                value=format_integer(len(report.current.rows)),
                **_kw(len(report.current.rows), comp_asesores),
            ),
            PDFKpiItem(
                label="Exámenes",
                value=format_integer(total_exams),
                **_kw(total_exams, comp_total_exams),
            ),
            *status_kpis,
            PDFKpiItem(
                label="Sin Categorizar",
                value=format_currency(total_uncategorized, base_currency),
                **_kw(total_uncategorized, comp_total_uncategorized),
            ),
            PDFKpiItem(
                label="Valor Total",
                value=format_currency(total_revenue, base_currency),
                **_kw(total_revenue, comp_total_revenue),
            ),
            PDFKpiItem(
                label="Ingreso Asignado",
                value=format_currency(total_allocated, base_currency),
                **_kw(total_allocated, comp_total_allocated),
            ),
            PDFKpiItem(
                label="Ingreso Esperado",
                value=format_currency(total_expected, base_currency),
                **_kw(total_expected, comp_total_expected),
            ),
            PDFKpiItem(
                label="Costo Esperado",
                value=format_currency(total_cost, base_currency),
                **_kw(total_cost, comp_total_cost),
            ),
            PDFKpiItem(
                label="Margen de Utilidad",
                value=format_percent(total_margin),
            ),
        ],
        table=PDFTable(
            headers=table_headers,
            rows=table_rows,
            column_widths=table_widths,
        ),
    )


async def build_asesor_detail_pdf_payload(
    seller_id: int,
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> AsesorDetailPDFPayload:
    response = await get_asesor_detail(
        seller_id,
        filters,
        country_rates=country_rates,
        base_currency=base_currency,
    )
    detail = response.current
    comp_detail = response.comparison.data if response.comparison else None
    comp_meta = response.comparison.meta if response.comparison else None

    def _kw(curr: float, prev: float | None) -> dict:
        if prev is None:
            return {}
        g, gp = format_growth(percent_change(curr, prev))
        return {"growth": g or "N/A", "growth_positive": gp}

    empty_bd = ExamBrandDetail(exams=0, schools=0, revenue=0.0)
    category_rows = []
    for cat in EXAM_CATEGORY_ORDER:
        bd = detail.exam_breakdown.get(cat, empty_bd)
        comp_bd = comp_detail.exam_breakdown.get(cat, empty_bd) if comp_detail else None
        deltas: list = [
            None,
            format_delta(bd.exams, comp_bd.exams, format_integer) if comp_bd else None,
            format_delta(bd.schools, comp_bd.schools, format_integer) if comp_bd else None,
            format_delta(bd.revenue, comp_bd.revenue, lambda v: format_currency(v, base_currency))
            if comp_bd
            else None,
        ]
        category_rows.append(
            PDFTableRow(
                cells=[
                    cat,
                    format_integer(bd.exams),
                    format_integer(bd.schools),
                    format_currency(bd.revenue, base_currency),
                ],
                deltas=deltas,
            )
        )

    # Add Libros and Cursos as rows after exam categories
    for product_label, count, revenue, comp_count, comp_revenue in [
        (
            "Libros",
            detail.total_books,
            detail.book_revenue,
            comp_detail.total_books if comp_detail else None,
            comp_detail.book_revenue if comp_detail else None,
        ),
        (
            "Cursos",
            detail.total_courses,
            detail.course_revenue,
            comp_detail.total_courses if comp_detail else None,
            comp_detail.course_revenue if comp_detail else None,
        ),
    ]:
        deltas: list = [
            None,
            format_delta(count, comp_count, format_integer) if comp_count is not None else None,
            None,
            format_delta(revenue, comp_revenue, lambda v: format_currency(v, base_currency))
            if comp_revenue is not None
            else None,
        ]
        category_rows.append(
            PDFTableRow(
                cells=[
                    product_label,
                    format_integer(count),
                    "-",
                    format_currency(revenue, base_currency),
                ],
                deltas=deltas,
            )
        )

    status_rows = []
    for label, curr_status in [
        ("Ganados", detail.ganados),
        ("Perdidos", detail.perdidos),
        ("Mantenidos", detail.mantenidos),
    ]:
        status_rows.append(
            PDFTableRow(
                cells=[
                    label,
                    format_integer(curr_status.schools),
                    format_integer(curr_status.exams),
                    format_currency(curr_status.revenue, base_currency),
                ],
            )
        )

    return AsesorDetailPDFPayload(
        header=build_pdf_header(
            detail.seller_name,
            "Detalle del asesor por geografía, categorías y estado de colegios",
            filters,
            comparison_meta=comp_meta,
        ),
        kpis=[
            PDFKpiItem(
                label="Total Colegios",
                value=format_integer(detail.total_schools),
                **_kw(detail.total_schools, comp_detail.total_schools if comp_detail else None),
            ),
            PDFKpiItem(
                label="Total Exámenes",
                value=format_integer(detail.total_exams),
                **_kw(detail.total_exams, comp_detail.total_exams if comp_detail else None),
            ),
            PDFKpiItem(
                label="Libros",
                value=format_integer(detail.total_books),
                **_kw(detail.total_books, comp_detail.total_books if comp_detail else None),
            ),
            PDFKpiItem(
                label="Cursos",
                value=format_integer(detail.total_courses),
                **_kw(detail.total_courses, comp_detail.total_courses if comp_detail else None),
            ),
            PDFKpiItem(
                label="Sin Categorizar",
                value=format_currency(detail.uncategorized_revenue, base_currency),
                **_kw(
                    detail.uncategorized_revenue,
                    comp_detail.uncategorized_revenue if comp_detail else None,
                ),
            ),
            PDFKpiItem(
                label="Valor Total",
                value=format_currency(detail.total_revenue, base_currency),
                **_kw(detail.total_revenue, comp_detail.total_revenue if comp_detail else None),
            ),
            PDFKpiItem(
                label="Ingreso Asignado",
                value=format_currency(detail.allocated_revenue, base_currency),
                **_kw(
                    detail.allocated_revenue, comp_detail.allocated_revenue if comp_detail else None
                ),
            ),
            PDFKpiItem(
                label="Ingreso Esperado",
                value=format_currency(detail.expected_revenue, base_currency),
                **_kw(
                    detail.expected_revenue, comp_detail.expected_revenue if comp_detail else None
                ),
            ),
            PDFKpiItem(
                label="Costo Esperado",
                value=format_currency(detail.expected_cost, base_currency),
                **_kw(detail.expected_cost, comp_detail.expected_cost if comp_detail else None),
            ),
            PDFKpiItem(
                label="Margen de Utilidad",
                value=format_percent(detail.profit_margin),
            ),
        ],
        geo_table=PDFTable(
            headers=["País", "Sede", "Estado", "Ciudad"],
            rows=[
                PDFTableRow(
                    cells=[
                        ", ".join(detail.countries) or "-",
                        ", ".join(detail.zones) or "-",
                        ", ".join(detail.states) or "-",
                        ", ".join(detail.cities) or "-",
                    ]
                )
            ],
            column_widths=[2, 2, 2, 2],
        ),
        categories_table=PDFTable(
            headers=["Categoría", "Exámenes", "Colegios", "Valor"],
            rows=category_rows,
            column_widths=[4, 2, 2, 2],
        ),
        status_table=PDFTable(
            headers=["Estado", "Colegios", "Exámenes", "Valor"],
            rows=status_rows,
            column_widths=[3, 2, 2, 2],
        ),
    )
