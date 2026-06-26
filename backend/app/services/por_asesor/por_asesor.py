import asyncio
from collections import defaultdict
from datetime import date
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
)
from app.services.por_asesor.product_grouping import EXAM_CATEGORY_ORDER
from app.services.por_asesor.repository import (
    fetch_detail_exam_breakdown_rows,
    fetch_paginated_summary_rows,
    fetch_school_allocated_revenue_metric_rows,
    fetch_school_exam_metric_rows,
    fetch_school_presence_rows,
    fetch_summary_allocated_revenue_rows_by_seller_ids,
    fetch_summary_exam_breakdown_rows_by_seller_ids,
    fetch_summary_rows_by_seller_ids,
    _line_where,
    _payment_where,
)
from app.services.utils.date_utils import (
    current_year_to_date_range,
    percent_change,
    resolve_comparison_range,
)
from app.services.utils.report_currency import line_paid_total_column, payment_amount_column

ASESOR_SUMMARY_COLUMNS = [
    ExcelColumn("seller_name", "Seller"),
    *[ExcelColumn(category, category) for category in EXAM_CATEGORY_ORDER],
    ExcelColumn("ganados", "Ganados"),
    ExcelColumn("perdidos", "Perdidos"),
    ExcelColumn("mantenidos", "Mantenidos"),
    ExcelColumn("uncategorized_revenue", "Uncategorized Revenue"),
    ExcelColumn("total_revenue", "Total Revenue"),
]

ASESOR_DETAIL_COLUMNS = [
    ExcelColumn("seller_name", "Seller"),
    ExcelColumn("countries", "Countries"),
    ExcelColumn("zones", "Zones"),
    ExcelColumn("states", "States"),
    ExcelColumn("cities", "Cities"),
    ExcelColumn("total_schools", "Total Schools"),
    ExcelColumn("total_exams", "Total Exams"),
    ExcelColumn("uncategorized_revenue", "Uncategorized Revenue"),
    ExcelColumn("total_revenue", "Total Revenue"),
]
for _cat in EXAM_CATEGORY_ORDER:
    ASESOR_DETAIL_COLUMNS.extend(
        [
            ExcelColumn(f"{_cat}_exams", f"{_cat} Exams"),
            ExcelColumn(f"{_cat}_schools", f"{_cat} Schools"),
            ExcelColumn(f"{_cat}_revenue", f"{_cat} Revenue"),
        ]
    )
ASESOR_DETAIL_COLUMNS.extend(
    [
        ExcelColumn("ganados_schools", "Ganados Schools"),
        ExcelColumn("ganados_exams", "Ganados Exams"),
        ExcelColumn("ganados_revenue", "Ganados Revenue"),
        ExcelColumn("perdidos_schools", "Perdidos Schools"),
        ExcelColumn("perdidos_exams", "Perdidos Exams"),
        ExcelColumn("perdidos_revenue", "Perdidos Revenue"),
        ExcelColumn("mantenidos_schools", "Mantenidos Schools"),
        ExcelColumn("mantenidos_exams", "Mantenidos Exams"),
        ExcelColumn("mantenidos_revenue", "Mantenidos Revenue"),
    ]
)


def _normalized_asesor_filters(filters: AsesorFilters) -> AsesorFilters:
    if filters.date_from and filters.date_to:
        return filters
    if filters.year is not None:
        return filters.model_copy(
            update={
                "date_from": date(filters.year, 1, 1).isoformat(),
                "date_to": date(filters.year, 12, 31).isoformat(),
            }
        )
    date_from, date_to = current_year_to_date_range()
    return filters.model_copy(update={"date_from": date_from, "date_to": date_to})


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
                    COALESCE(SUM(CASE WHEN product_type = 'exam' THEN quantity ELSE 0 END), 0) AS total_exams,
                    COALESCE(SUM({paid_total}), 0) AS allocated_revenue
                FROM report_line_items
                WHERE {line_where}
            """),
                    line_params,
                )
            ).fetchone()

    payment_row, line_row = await asyncio.gather(fetch_payment_row(), fetch_line_row())
    return SimpleNamespace(
        total_schools=int((payment_row.total_schools or 0) if payment_row else 0),
        total_revenue=float((payment_row.total_revenue or 0) if payment_row else 0),
        total_exams=int((line_row.total_exams or 0) if line_row else 0),
        uncategorized_revenue=float((payment_row.total_revenue or 0) if payment_row else 0)
        - float((line_row.allocated_revenue or 0) if line_row else 0),
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
    return BusinessStatusDetail(schools=0, exams=0, revenue=0.0)


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
        current_exam_metrics[(int(row.seller_id), int(row.lead_id))] = int(row.exams or 0)
    for row in comparison_exam_metric_rows:
        comparison_exam_metrics[(int(row.seller_id), int(row.lead_id))] = int(row.exams or 0)

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
            exam_src = comparison_exam_metrics if status == "perdido" else current_exam_metrics
            revenue_src = (
                comparison_allocated_metrics if status == "perdido" else current_allocated_metrics
            )
            seller_statuses[status] = BusinessStatusDetail(
                schools=len(lead_ids),
                exams=sum(exam_src.get((seller_id, lead_id), 0) for lead_id in lead_ids),
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
    current_rows, comparison_rows = await asyncio.gather(
        fetch_school_presence_rows(current_filters),
        fetch_school_presence_rows(comparison_filters),
    )
    current_by_seller: dict[int, set[int]] = defaultdict(set)
    comparison_by_seller: dict[int, set[int]] = defaultdict(set)
    for row in current_rows:
        current_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in comparison_rows:
        comparison_by_seller[int(row.seller_id)].add(int(row.lead_id))
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
        }
        for seller_id in seller_ids
    }


def build_asesor_report_base(
    summary_rows,
    exam_breakdowns: dict[int, dict[str, int]],
    status_counts: dict[int, dict[str, int]],
    allocated_by_seller: dict[int, float],
    *,
    next_cursor: str | None,
    has_more: bool,
) -> AsesorReportBase:
    rows = [
        AsesorRow(
            seller_id=int(row.seller_id),
            seller_name=row.seller_name,
            exam_breakdown=exam_breakdowns.get(
                int(row.seller_id), fill_summary_exam_categories({})
            ),
            ganados=int(status_counts.get(int(row.seller_id), {}).get("ganado", 0)),
            perdidos=int(status_counts.get(int(row.seller_id), {}).get("perdido", 0)),
            mantenidos=int(status_counts.get(int(row.seller_id), {}).get("mantenido", 0)),
            total_revenue=float(row.total_revenue or 0),
            uncategorized_revenue=float(row.total_revenue or 0)
            - allocated_by_seller.get(int(row.seller_id), 0.0),
        )
        for row in summary_rows
    ]
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
    breakdown_rows, allocated_rows, status_counts = await asyncio.gather(
        fetch_summary_exam_breakdown_rows_by_seller_ids(seller_ids, current_filters),
        fetch_summary_allocated_revenue_rows_by_seller_ids(
            seller_ids, current_filters, base_currency=base_currency
        ),
        fetch_summary_status_counts(current_filters, comparison_filters, seller_ids),
    )
    return build_asesor_report_base(
        summary_rows,
        map_summary_exam_breakdowns(breakdown_rows),
        status_counts,
        {int(row.seller_id): float(row.allocated_revenue or 0) for row in allocated_rows},
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def getAsesorReport(
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> AsesorReportResponse:
    normalized_filters = _normalized_asesor_filters(filters)
    comparison_meta = resolve_comparison_range(normalized_filters)

    if comparison_meta is None:
        previous_year_from = (
            date.fromisoformat(normalized_filters.date_from)
            .replace(year=date.fromisoformat(normalized_filters.date_from).year - 1)
            .isoformat()
        )
        previous_year_to = (
            date.fromisoformat(normalized_filters.date_to)
            .replace(year=date.fromisoformat(normalized_filters.date_to).year - 1)
            .isoformat()
        )
        current = await _get_asesor_report_base(
            normalized_filters,
            normalized_filters.model_copy(
                update={
                    "date_from": previous_year_from,
                    "date_to": previous_year_to,
                    "show_comparison": False,
                }
            ),
            limit=normalized_filters.limit,
            cursor=normalized_filters.cursor,
            base_currency=base_currency,
        )
        return AsesorReportResponse(current=current, comparison_mode=None, comparison=None)

    current_filters = normalized_filters.model_copy(
        update={"show_comparison": False, "comparison_date_from": None, "comparison_date_to": None}
    )
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
        comparison_allocated_rows,
        comparison_status_counts,
    ) = await asyncio.gather(
        fetch_summary_rows_by_seller_ids(
            seller_ids, comparison_filters, base_currency=base_currency
        ),
        fetch_summary_exam_breakdown_rows_by_seller_ids(seller_ids, comparison_filters),
        fetch_summary_allocated_revenue_rows_by_seller_ids(
            seller_ids, comparison_filters, base_currency=base_currency
        ),
        fetch_summary_status_counts(comparison_filters, current_filters, seller_ids),
    )
    comparison = build_asesor_report_base(
        comparison_summary_rows,
        map_summary_exam_breakdowns(comparison_breakdown_rows),
        comparison_status_counts,
        {
            int(row.seller_id): float(row.allocated_revenue or 0)
            for row in comparison_allocated_rows
        },
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
        fetch_school_exam_metric_rows(filters, seller_id=seller_id),
        fetch_school_exam_metric_rows(comparison_filters, seller_id=seller_id),
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


async def getAsesorDetail(
    seller_id: int,
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> AsesorDetailResponse:
    normalized_filters = _normalized_asesor_filters(filters)
    comparison_meta = resolve_comparison_range(normalized_filters)
    if comparison_meta is None:
        previous_year_from = (
            date.fromisoformat(normalized_filters.date_from)
            .replace(year=date.fromisoformat(normalized_filters.date_from).year - 1)
            .isoformat()
        )
        previous_year_to = (
            date.fromisoformat(normalized_filters.date_to)
            .replace(year=date.fromisoformat(normalized_filters.date_to).year - 1)
            .isoformat()
        )
        current = await _get_asesor_detail_base(
            seller_id,
            normalized_filters,
            normalized_filters.model_copy(
                update={
                    "date_from": previous_year_from,
                    "date_to": previous_year_to,
                    "show_comparison": False,
                }
            ),
            base_currency=base_currency,
        )
        return AsesorDetailResponse(current=current, comparison_mode=None, comparison=None)

    current_filters = normalized_filters.model_copy(
        update={"show_comparison": False, "comparison_date_from": None, "comparison_date_to": None}
    )
    comparison_filters = current_filters.model_copy(
        update={"date_from": comparison_meta.date_from, "date_to": comparison_meta.date_to}
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


async def getAllAsesorReportRows(
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> AsesorReportResponse:
    normalized_filters = _normalized_asesor_filters(filters)
    all_rows: list[AsesorRow] = []
    cursor = normalized_filters.cursor
    while True:
        page = await getAsesorReport(
            normalized_filters.model_copy(update={"cursor": cursor}),
            country_rates=country_rates,
            base_currency=base_currency,
        )
        all_rows.extend(page.current.rows)
        if not page.current.has_more or page.current.next_cursor is None:
            break
        cursor = page.current.next_cursor
    return AsesorReportResponse(
        current=AsesorReportBase(rows=all_rows, next_cursor=None, has_more=False),
        comparison_mode=None,
        comparison=None,
    )


async def getAsesorDetailsForRows(
    rows: list[AsesorRow],
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> list[AsesorDetailBase]:
    if not rows:
        return []
    normalized_filters = _normalized_asesor_filters(filters)
    comparison_filters = normalized_filters
    results = await asyncio.gather(
        *(
            _get_asesor_detail_base(
                row.seller_id,
                normalized_filters,
                comparison_filters,
                base_currency=base_currency,
            )
            for row in rows
        )
    )
    return list(results)


def build_asesor_export_filters_for_all(filters: AsesorFilters) -> AsesorFilters:
    normalized_filters = _normalized_asesor_filters(filters)
    return normalized_filters.model_copy(
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
            "uncategorized_revenue": row.uncategorized_revenue,
            "total_revenue": row.total_revenue,
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
            "uncategorized_revenue": detail.uncategorized_revenue,
            "total_revenue": detail.total_revenue,
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

    specs = [
        ExcelWorksheetSpec(name="Por Asesor", columns=ASESOR_SUMMARY_COLUMNS, rows=summary_rows),
        ExcelWorksheetSpec(
            name="Por Asesor Detail", columns=ASESOR_DETAIL_COLUMNS, rows=detail_rows
        ),
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
                    "uncategorized_pct": _pct(row.uncategorized_revenue, comp.uncategorized_revenue) if comp else None,
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
    report = await getAllAsesorReportRows(
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

    comp_by_seller = (
        {r.seller_name: r for r in report.comparison.data.rows}
        if report.comparison
        else {}
    )

    table_rows = []
    for row in report.current.rows:
        cambridge = int(row.exam_breakdown.get("Cambridge English (Main Suite)", 0) or 0) + int(
            row.exam_breakdown.get("Cambridge Teaching & Skills", 0) or 0
        )
        ielts = int(row.exam_breakdown.get("IELTS", 0) or 0)
        met = int(row.exam_breakdown.get("Michigan (MET)", 0) or 0)
        otros = int(row.exam_breakdown.get("TEA (Test of English for Aviation)", 0) or 0) + int(
            row.exam_breakdown.get("Placement & Otros", 0) or 0
        )
        comp = comp_by_seller.get(row.seller_name)
        deltas: list = [None] * 10
        if comp:
            deltas[8] = format_delta(
                row.uncategorized_revenue,
                comp.uncategorized_revenue,
                lambda v: format_currency(v, base_currency),
            )
            deltas[9] = format_delta(
                row.total_revenue,
                comp.total_revenue,
                lambda v: format_currency(v, base_currency),
            )
        table_rows.append(
            PDFTableRow(
                cells=[
                    row.seller_name,
                    format_integer(cambridge),
                    format_integer(ielts),
                    format_integer(met),
                    format_integer(otros),
                    format_integer(row.ganados),
                    format_integer(row.perdidos),
                    format_integer(row.mantenidos),
                    format_currency(row.uncategorized_revenue, base_currency),
                    format_currency(row.total_revenue, base_currency),
                ],
                deltas=deltas,
            )
        )

    comp_total_revenue = sum(r.total_revenue for r in report.comparison.data.rows) if report.comparison else None
    revenue_growth, revenue_growth_positive = format_growth(
        ((total_revenue - comp_total_revenue) / comp_total_revenue * 100)
        if comp_total_revenue
        else None
    )

    return PorAsesorPDFPayload(
        header=build_pdf_header(
            "Resultados por Asesor",
            "Resumen por asesor con familias de exámenes y valor total",
            _normalized_asesor_filters(filters),
            comparison_meta=report.comparison.meta if report.comparison else None,
        ),
        kpis=[
            PDFKpiItem(label="Asesores", value=format_integer(len(report.current.rows))),
            PDFKpiItem(label="Exámenes", value=format_integer(total_exams)),
            PDFKpiItem(label="Ganados", value=format_integer(total_ganados)),
            PDFKpiItem(label="Perdidos", value=format_integer(total_perdidos)),
            PDFKpiItem(label="Mantenidos", value=format_integer(total_mantenidos)),
            PDFKpiItem(
                label="Sin Categorizar", value=format_currency(total_uncategorized, base_currency)
            ),
            PDFKpiItem(
                label="Valor Total",
                value=format_currency(total_revenue, base_currency),
                growth=revenue_growth,
                growth_positive=revenue_growth_positive,
            ),
        ],
        table=PDFTable(
            headers=[
                "Asesor",
                "Cambridge",
                "IELTS",
                "MET",
                "Otros",
                "Ganados",
                "Perdidos",
                "Mantenidos",
                "Sin Categorizar",
                "Valor Total",
            ],
            rows=table_rows,
            column_widths=[4, 2, 2, 2, 2, 2, 2, 2, 3, 3],
        ),
    )


async def build_asesor_detail_pdf_payload(
    seller_id: int,
    filters: AsesorFilters,
    country_rates: dict | None = None,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> AsesorDetailPDFPayload:
    detail = (
        await getAsesorDetail(
            seller_id,
            filters,
            country_rates=country_rates,
            base_currency=base_currency,
        )
    ).current
    category_rows = [
        PDFTableRow(
            cells=[
                cat,
                format_integer(
                    detail.exam_breakdown.get(
                        cat, ExamBrandDetail(exams=0, schools=0, revenue=0.0)
                    ).exams
                ),
                format_integer(
                    detail.exam_breakdown.get(
                        cat, ExamBrandDetail(exams=0, schools=0, revenue=0.0)
                    ).schools
                ),
                format_currency(
                    detail.exam_breakdown.get(
                        cat, ExamBrandDetail(exams=0, schools=0, revenue=0.0)
                    ).revenue,
                    base_currency,
                ),
            ]
        )
        for cat in EXAM_CATEGORY_ORDER
    ]
    status_rows = [
        PDFTableRow(
            cells=[
                "Ganados",
                format_integer(detail.ganados.schools),
                format_integer(detail.ganados.exams),
                format_currency(detail.ganados.revenue, base_currency),
            ]
        ),
        PDFTableRow(
            cells=[
                "Perdidos",
                format_integer(detail.perdidos.schools),
                format_integer(detail.perdidos.exams),
                format_currency(detail.perdidos.revenue, base_currency),
            ]
        ),
        PDFTableRow(
            cells=[
                "Mantenidos",
                format_integer(detail.mantenidos.schools),
                format_integer(detail.mantenidos.exams),
                format_currency(detail.mantenidos.revenue, base_currency),
            ]
        ),
    ]
    return AsesorDetailPDFPayload(
        header=build_pdf_header(
            detail.seller_name,
            "Detalle del asesor por geografía, categorías y estado de colegios",
            _normalized_asesor_filters(filters),
        ),
        kpis=[
            PDFKpiItem(label="Total Colegios", value=format_integer(detail.total_schools)),
            PDFKpiItem(label="Total Exámenes", value=format_integer(detail.total_exams)),
            PDFKpiItem(
                label="Sin Categorizar",
                value=format_currency(detail.uncategorized_revenue, base_currency),
            ),
            PDFKpiItem(
                label="Valor Total", value=format_currency(detail.total_revenue, base_currency)
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
