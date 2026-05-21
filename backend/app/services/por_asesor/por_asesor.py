import asyncio
from collections import defaultdict
from sqlalchemy import text

from fastapi import HTTPException

from app.reporting.database import ReportingSessionLocal
from app.enums import PaymentStatus
from app.schemas.pdf import AsesorDetailPDFPayload, PDFKpiItem, PDFTable, PDFTableRow, PorAsesorPDFPayload
from app.schemas.reports import (
    AsesorDetail,
    AsesorFilters,
    AsesorReportResponse,
    AsesorRow,
    BusinessStatusDetail,
    ExamBrandDetail,
)
from app.services.exports.pdf_helpers import build_pdf_header, format_currency, format_integer
from app.services.exports.excel import ExcelColumn, ExcelWorksheetSpec
from app.services.por_asesor.product_grouping import EXAM_CATEGORY_ORDER
from app.services.por_asesor.repository import (
    fetch_paginated_summary_rows,
    fetch_school_exam_metric_rows,
    fetch_school_allocated_revenue_metric_rows,
    fetch_summary_exam_breakdown_rows_by_seller_ids,
    fetch_summary_allocated_revenue_rows_by_seller_ids,
    fetch_school_presence_rows,
)

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
    ASESOR_DETAIL_COLUMNS.extend([
        ExcelColumn(f"{_cat}_exams",    f"{_cat} Exams"),
        ExcelColumn(f"{_cat}_schools",  f"{_cat} Schools"),
        ExcelColumn(f"{_cat}_revenue",  f"{_cat} Revenue"),
    ])
ASESOR_DETAIL_COLUMNS.extend([
    ExcelColumn("ganados_schools",   "Ganados Schools"),
    ExcelColumn("ganados_exams",     "Ganados Exams"),
    ExcelColumn("ganados_revenue",   "Ganados Revenue"),
    ExcelColumn("perdidos_schools",  "Perdidos Schools"),
    ExcelColumn("perdidos_exams",    "Perdidos Exams"),
    ExcelColumn("perdidos_revenue",  "Perdidos Revenue"),
    ExcelColumn("mantenidos_schools","Mantenidos Schools"),
    ExcelColumn("mantenidos_exams",  "Mantenidos Exams"),
    ExcelColumn("mantenidos_revenue","Mantenidos Revenue"),
])


# ─────────────────────────────────────────────────────────────
# DB helpers — reporting DB only
# ─────────────────────────────────────────────────────────────

async def fetch_seller_name(seller_id: int) -> str | None:
    async with ReportingSessionLocal() as session:
        row = (await session.execute(
            text("SELECT seller_name FROM report_payments WHERE seller_id = :id LIMIT 1"),
            {"id": seller_id},
        )).fetchone()
        return row.seller_name if row else None


async def fetch_detail_aggregate_row(seller_id: int, filters: AsesorFilters):
    from app.services.por_asesor.repository import _line_where, _payment_where

    payment_where, payment_params = _payment_where(filters, seller_id=seller_id)
    line_where, line_params = _line_where(filters, seller_id=seller_id, require_product_breakdown=True)

    async def fetch_payment_row():
        async with ReportingSessionLocal() as session:
            return (await session.execute(text(f"""
                SELECT
                    COUNT(DISTINCT lead_id) AS total_schools,
                    COALESCE(SUM(amount_mxn), 0) AS total_revenue
                FROM report_payments
                WHERE {payment_where}
            """), payment_params)).fetchone()

    async def fetch_line_row():
        async with ReportingSessionLocal() as session:
            return (await session.execute(text(f"""
                SELECT
                    COALESCE(SUM(CASE WHEN product_type = 'exam' THEN quantity ELSE 0 END), 0) AS total_exams,
                    COALESCE(SUM(paid_total_mxn), 0) AS allocated_revenue
                FROM report_line_items
                WHERE {line_where}
            """), line_params)).fetchone()

    payment_row, line_row = await asyncio.gather(fetch_payment_row(), fetch_line_row())

    from types import SimpleNamespace
    return SimpleNamespace(
        total_schools=int((payment_row.total_schools or 0) if payment_row else 0),
        total_revenue=float((payment_row.total_revenue or 0) if payment_row else 0),
        total_exams=int((line_row.total_exams or 0) if line_row else 0),
        uncategorized_revenue=float((payment_row.total_revenue or 0) if payment_row else 0) - float((line_row.allocated_revenue or 0) if line_row else 0),
    )


async def fetch_detail_geo_rows(seller_id: int, filters: AsesorFilters) -> list:
    from app.services.por_asesor.repository import _payment_where
    where, params = _payment_where(filters, seller_id=seller_id)
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(f"""
            SELECT DISTINCT
                site        AS country,
                zone_name   AS zone,
                state_name  AS state,
                city        AS city
            FROM report_payments
            WHERE {where}
        """), params)).fetchall()


async def fetch_detail_exam_breakdown_rows(seller_id: int, filters: AsesorFilters) -> list:
    from app.services.por_asesor.repository import _line_where
    where, params = _line_where(filters, seller_id=seller_id, require_product_breakdown=True)
    async with ReportingSessionLocal() as session:
        return (await session.execute(text(f"""
            SELECT
                exam_category,
                SUM(quantity)           AS exams,
                COUNT(DISTINCT lead_id) AS schools,
                SUM(paid_total_mxn)     AS revenue
            FROM report_line_items
            WHERE {where} AND product_type = 'exam'
            GROUP BY exam_category
        """), params)).fetchall()


# ─────────────────────────────────────────────────────────────
# Mapping helpers
# ─────────────────────────────────────────────────────────────

def fill_summary_exam_categories(breakdown: dict) -> dict:
    return {cat: int(breakdown.get(cat, 0) or 0) for cat in EXAM_CATEGORY_ORDER}


def map_summary_exam_breakdowns(rows) -> dict[int, dict[str, int]]:
    """Rows already have exam_category — no canonical mapping needed."""
    exam_breakdowns: dict[int, dict[str, int]] = {}
    for row in rows:
        seller_breakdown = exam_breakdowns.setdefault(int(row.seller_id), {cat: 0 for cat in EXAM_CATEGORY_ORDER})
        cat = row.exam_category
        if cat in seller_breakdown:
            seller_breakdown[cat] += int(row.exam_count or 0)
    return {sid: fill_summary_exam_categories(bd) for sid, bd in exam_breakdowns.items()}


def map_detail_exam_breakdown(rows) -> dict[str, ExamBrandDetail]:
    """Rows already grouped by exam_category — build ExamBrandDetail per category."""
    breakdown = {cat: ExamBrandDetail(exams=0, schools=0, revenue=0.0) for cat in EXAM_CATEGORY_ORDER}
    for row in rows:
        cat = row.exam_category
        if cat in breakdown:
            breakdown[cat] = ExamBrandDetail(
                exams=breakdown[cat].exams     + int(row.exams or 0),
                schools=breakdown[cat].schools + int(row.schools or 0),
                revenue=breakdown[cat].revenue + float(row.revenue or 0),
            )
    return breakdown


def unique_sorted_values(rows, field: str) -> list[str]:
    return sorted({getattr(row, field) for row in rows if getattr(row, field)})


def empty_status() -> BusinessStatusDetail:
    return BusinessStatusDetail(schools=0, exams=0, revenue=0.0)


# ─────────────────────────────────────────────────────────────
# Status calculation
# ─────────────────────────────────────────────────────────────

def build_status_map_from_year_sets(
    current_rows,
    prior_rows,
    current_allocated_metric_rows,
    prior_allocated_metric_rows,
    current_exam_metric_rows,
    prior_exam_metric_rows,
):
    current_by_seller: dict[int, set[int]] = defaultdict(set)
    prior_by_seller:   dict[int, set[int]] = defaultdict(set)
    current_allocated_metrics: dict[tuple, float] = {}
    prior_allocated_metrics: dict[tuple, float] = {}
    current_exam_metrics: dict[tuple, int] = {}
    prior_exam_metrics: dict[tuple, int] = {}

    for row in current_rows:
        current_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in prior_rows:
        prior_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in current_allocated_metric_rows:
        current_allocated_metrics[(int(row.seller_id), int(row.lead_id))] = float(row.revenue or 0)
    for row in prior_allocated_metric_rows:
        prior_allocated_metrics[(int(row.seller_id), int(row.lead_id))] = float(row.revenue or 0)
    for row in current_exam_metric_rows:
        current_exam_metrics[(int(row.seller_id), int(row.lead_id))] = int(row.exams or 0)
    for row in prior_exam_metric_rows:
        prior_exam_metrics[(int(row.seller_id), int(row.lead_id))] = int(row.exams or 0)

    seller_ids = set(current_by_seller) | set(prior_by_seller)
    status_map: dict[int, dict[str, BusinessStatusDetail]] = {}
    for sid in seller_ids:
        current = current_by_seller.get(sid, set())
        prior   = prior_by_seller.get(sid, set())
        buckets = {"ganado": current - prior, "perdido": prior - current, "mantenido": current & prior}
        seller_statuses: dict[str, BusinessStatusDetail] = {}
        for status, lead_ids in buckets.items():
            exam_src = prior_exam_metrics if status == "perdido" else current_exam_metrics
            revenue_src = prior_allocated_metrics if status == "perdido" else current_allocated_metrics
            exams = sum(exam_src.get((sid, lid), 0) for lid in lead_ids)
            revenue = sum(revenue_src.get((sid, lid), 0.0) for lid in lead_ids)
            seller_statuses[status] = BusinessStatusDetail(schools=len(lead_ids), exams=exams, revenue=revenue)
        status_map[sid] = seller_statuses

    if len(status_map) == 1:
        return next(iter(status_map.values()))
    return status_map


async def fetch_detail_status_rows(seller_id: int, filters: AsesorFilters):
    current_rows, prior_rows, current_allocated_rows, prior_allocated_rows, current_exam_rows, prior_exam_rows = await asyncio.gather(
        fetch_school_presence_rows(filters, filters.year,     seller_id=seller_id),
        fetch_school_presence_rows(filters, filters.year - 1, seller_id=seller_id),
        fetch_school_allocated_revenue_metric_rows(filters, filters.year, seller_id=seller_id),
        fetch_school_allocated_revenue_metric_rows(filters, filters.year - 1, seller_id=seller_id),
        fetch_school_exam_metric_rows(filters, filters.year, seller_id=seller_id),
        fetch_school_exam_metric_rows(filters, filters.year - 1, seller_id=seller_id),
    )
    return build_status_map_from_year_sets(
        current_rows,
        prior_rows,
        current_allocated_rows,
        prior_allocated_rows,
        current_exam_rows,
        prior_exam_rows,
    )


async def fetch_summary_status_counts(filters: AsesorFilters, seller_ids: list[int]) -> dict[int, dict[str, int]]:
    if not seller_ids:
        return {}
    current_rows, prior_rows = await asyncio.gather(
        fetch_school_presence_rows(filters, filters.year),
        fetch_school_presence_rows(filters, filters.year - 1),
    )
    current_by_seller: dict[int, set[int]] = defaultdict(set)
    prior_by_seller:   dict[int, set[int]] = defaultdict(set)
    for row in current_rows:
        current_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in prior_rows:
        prior_by_seller[int(row.seller_id)].add(int(row.lead_id))

    return {
        sid: {
            "ganado":   len(current_by_seller.get(sid, set()) - prior_by_seller.get(sid, set())),
            "perdido":  len(prior_by_seller.get(sid, set())   - current_by_seller.get(sid, set())),
            "mantenido":len(current_by_seller.get(sid, set()) & prior_by_seller.get(sid, set())),
        }
        for sid in seller_ids
    }


# ─────────────────────────────────────────────────────────────
# Response builders
# ─────────────────────────────────────────────────────────────

def build_asesor_report_response(
    summary_rows,
    exam_breakdowns: dict,
    status_counts: dict,
    year: int,
    next_cursor: str | None,
    has_more: bool,
) -> AsesorReportResponse:
    rows = [
        AsesorRow(
            seller_id=int(row.seller_id),
            seller_name=row.seller_name,
            exam_breakdown=exam_breakdowns.get(int(row.seller_id), {}),
            ganados=int(status_counts.get(int(row.seller_id), {}).get("ganado", 0)),
            perdidos=int(status_counts.get(int(row.seller_id), {}).get("perdido", 0)),
            mantenidos=int(status_counts.get(int(row.seller_id), {}).get("mantenido", 0)),
            total_revenue=float(row.total_revenue or 0),
            uncategorized_revenue=float(getattr(row, "uncategorized_revenue", 0) or 0),
        )
        for row in summary_rows
    ]
    return AsesorReportResponse(rows=rows, year=year, next_cursor=next_cursor, has_more=has_more)


def build_asesor_detail_response(
    seller_name: str,
    aggregate_row,
    geo_rows,
    exam_breakdown: dict,
    status_map: dict,
) -> AsesorDetail:
    has_data = bool(
        aggregate_row and any([
            aggregate_row.total_schools,
            aggregate_row.total_exams,
            aggregate_row.total_revenue,
        ])
    )
    return AsesorDetail(
        seller_name=seller_name,
        countries=unique_sorted_values(geo_rows, "country"),
        zones=unique_sorted_values(geo_rows, "zone"),
        states=unique_sorted_values(geo_rows, "state"),
        cities=unique_sorted_values(geo_rows, "city"),
        total_schools=int((aggregate_row.total_schools or 0) if aggregate_row else 0),
        total_exams=int((aggregate_row.total_exams or 0) if aggregate_row else 0),
        total_revenue=float((aggregate_row.total_revenue or 0) if aggregate_row else 0),
        uncategorized_revenue=float((aggregate_row.uncategorized_revenue or 0) if aggregate_row else 0),
        exam_breakdown=exam_breakdown if has_data else {cat: ExamBrandDetail(exams=0, schools=0, revenue=0.0) for cat in EXAM_CATEGORY_ORDER},
        ganados=status_map.get("ganado", empty_status()),
        perdidos=status_map.get("perdido", empty_status()),
        mantenidos=status_map.get("mantenido", empty_status()),
    )


# ─────────────────────────────────────────────────────────────
# Public service functions
# ─────────────────────────────────────────────────────────────

async def getAsesorReport(
    filters: AsesorFilters,
    country_rates: dict | None = None,
) -> AsesorReportResponse:
    summary_rows, has_more, next_cursor = await fetch_paginated_summary_rows(
        filters, limit=filters.limit, cursor=filters.cursor
    )
    seller_ids = [int(row.seller_id) for row in summary_rows]
    breakdown_rows, allocated_rows, status_counts = await asyncio.gather(
        fetch_summary_exam_breakdown_rows_by_seller_ids(seller_ids, filters),
        fetch_summary_allocated_revenue_rows_by_seller_ids(seller_ids, filters),
        fetch_summary_status_counts(filters, seller_ids),
    )
    exam_breakdowns = map_summary_exam_breakdowns(breakdown_rows)
    allocated_by_seller = {
        int(row.seller_id): float(row.allocated_revenue or 0)
        for row in allocated_rows
    }
    from types import SimpleNamespace
    summary_rows = [
        SimpleNamespace(
            seller_id=row.seller_id,
            seller_name=row.seller_name,
            total_revenue=row.total_revenue,
            uncategorized_revenue=float(row.total_revenue or 0) - allocated_by_seller.get(int(row.seller_id), 0.0),
        )
        for row in summary_rows
    ]
    return build_asesor_report_response(summary_rows, exam_breakdowns, status_counts, filters.year, next_cursor, has_more)


async def getAsesorDetail(
    seller_id: int,
    filters: AsesorFilters,
    country_rates: dict | None = None,
) -> AsesorDetail:
    seller_name = await fetch_seller_name(seller_id)
    if seller_name is None:
        raise HTTPException(status_code=404, detail="Seller not found")

    aggregate_row, geo_rows, breakdown_rows, status_rows = await asyncio.gather(
        fetch_detail_aggregate_row(seller_id, filters),
        fetch_detail_geo_rows(seller_id, filters),
        fetch_detail_exam_breakdown_rows(seller_id, filters),
        fetch_detail_status_rows(seller_id, filters),
    )
    exam_breakdown = map_detail_exam_breakdown(breakdown_rows)
    return build_asesor_detail_response(seller_name, aggregate_row, geo_rows, exam_breakdown, status_rows)


async def getAllAsesorReportRows(
    filters: AsesorFilters,
    country_rates: dict | None = None,
) -> AsesorReportResponse:
    all_rows: list[AsesorRow] = []
    cursor = filters.cursor

    while True:
        page = await getAsesorReport(filters.model_copy(update={"cursor": cursor}), country_rates=country_rates)
        all_rows.extend(page.rows)
        if not page.has_more or page.next_cursor is None:
            break
        cursor = page.next_cursor

    return AsesorReportResponse(rows=all_rows, year=filters.year, next_cursor=None, has_more=False)


async def getAsesorDetailsForRows(
    rows: list[AsesorRow],
    filters: AsesorFilters,
    country_rates: dict | None = None,
) -> list[AsesorDetail]:
    if not rows:
        return []
    return list(await asyncio.gather(*(getAsesorDetail(row.seller_id, filters) for row in rows)))


def build_asesor_export_filters_for_all(filters: AsesorFilters) -> AsesorFilters:
    return filters.model_copy(update={"countries": [], "zones": [], "states": [], "cities": [], "sellers": [], "cursor": None, "limit": 100})


def build_asesor_export_worksheets(report: AsesorReportResponse, details: list[AsesorDetail]) -> list[ExcelWorksheetSpec]:
    summary_rows = []
    for row in report.rows:
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
            cat_detail = detail.exam_breakdown.get(cat)
            if isinstance(cat_detail, ExamBrandDetail):
                detail_row[f"{cat}_exams"]   = cat_detail.exams
                detail_row[f"{cat}_schools"] = cat_detail.schools
                detail_row[f"{cat}_revenue"] = cat_detail.revenue
            else:
                detail_row[f"{cat}_exams"]   = int(cat_detail or 0)
                detail_row[f"{cat}_schools"] = 0
                detail_row[f"{cat}_revenue"] = 0.0
        detail_rows.append(detail_row)

    return [
        ExcelWorksheetSpec(name="Por Asesor",        columns=ASESOR_SUMMARY_COLUMNS, rows=summary_rows),
        ExcelWorksheetSpec(name="Por Asesor Detail", columns=ASESOR_DETAIL_COLUMNS,  rows=detail_rows),
    ]


async def build_por_asesor_pdf_payload(
    filters: AsesorFilters,
    country_rates: dict | None = None,
) -> PorAsesorPDFPayload:
    report = await getAllAsesorReportRows(build_asesor_export_filters_for_all(filters), country_rates=country_rates)

    total_revenue  = sum(row.total_revenue for row in report.rows)
    total_uncategorized = sum(row.uncategorized_revenue for row in report.rows)
    total_exams    = sum(sum(row.exam_breakdown.values()) for row in report.rows)
    total_ganados  = sum(row.ganados  for row in report.rows)
    total_perdidos = sum(row.perdidos for row in report.rows)
    total_mantenidos = sum(row.mantenidos for row in report.rows)

    table_rows = []
    for row in report.rows:
        cambridge = (
            int(row.exam_breakdown.get("Cambridge English (Main Suite)", 0) or 0)
            + int(row.exam_breakdown.get("Cambridge Teaching & Skills", 0) or 0)
        )
        ielts  = int(row.exam_breakdown.get("IELTS", 0) or 0)
        met    = int(row.exam_breakdown.get("Michigan (MET)", 0) or 0)
        otros  = (
            int(row.exam_breakdown.get("TEA (Test of English for Aviation)", 0) or 0)
            + int(row.exam_breakdown.get("Placement & Otros", 0) or 0)
        )
        table_rows.append(PDFTableRow(cells=[
            row.seller_name,
            format_integer(cambridge),
            format_integer(ielts),
            format_integer(met),
            format_integer(otros),
            format_integer(row.ganados),
            format_integer(row.perdidos),
            format_integer(row.mantenidos),
            format_currency(row.uncategorized_revenue),
            format_currency(row.total_revenue),
        ]))

    return PorAsesorPDFPayload(
        header=build_pdf_header(f"Resultados por Asesor - {filters.year}", "Resumen por asesor con familias de exámenes y valor total", filters),
        kpis=[
            PDFKpiItem(label="Asesores",    value=format_integer(len(report.rows))),
            PDFKpiItem(label="Exámenes",    value=format_integer(total_exams)),
            PDFKpiItem(label="Ganados",     value=format_integer(total_ganados)),
            PDFKpiItem(label="Perdidos",    value=format_integer(total_perdidos)),
            PDFKpiItem(label="Mantenidos",  value=format_integer(total_mantenidos)),
            PDFKpiItem(label="Sin Categorizar", value=format_currency(total_uncategorized)),
            PDFKpiItem(label="Valor Total", value=format_currency(total_revenue)),
        ],
        table=PDFTable(
            headers=["Asesor", "Cambridge", "IELTS", "MET", "Otros", "Ganados", "Perdidos", "Mantenidos", "Sin Categorizar", "Valor Total"],
            rows=table_rows,
            column_widths=[4, 2, 2, 2, 2, 2, 2, 2, 3, 3],
        ),
    )


async def build_asesor_detail_pdf_payload(
    seller_id: int,
    filters: AsesorFilters,
    country_rates: dict | None = None,
) -> AsesorDetailPDFPayload:
    detail = await getAsesorDetail(seller_id, filters, country_rates=country_rates)

    category_rows = []
    for cat in EXAM_CATEGORY_ORDER:
        cat_detail = detail.exam_breakdown.get(cat)
        if isinstance(cat_detail, ExamBrandDetail):
            exams, schools, revenue = cat_detail.exams, cat_detail.schools, cat_detail.revenue
        else:
            exams, schools, revenue = int(cat_detail or 0), 0, 0.0
        category_rows.append(PDFTableRow(cells=[cat, format_integer(exams), format_integer(schools), format_currency(revenue)]))

    status_rows = [
        PDFTableRow(cells=["Ganados",   format_integer(detail.ganados.schools),   format_integer(detail.ganados.exams),   format_currency(detail.ganados.revenue)]),
        PDFTableRow(cells=["Perdidos",  format_integer(detail.perdidos.schools),  format_integer(detail.perdidos.exams),  format_currency(detail.perdidos.revenue)]),
        PDFTableRow(cells=["Mantenidos",format_integer(detail.mantenidos.schools),format_integer(detail.mantenidos.exams),format_currency(detail.mantenidos.revenue)]),
    ]

    return AsesorDetailPDFPayload(
        header=build_pdf_header(detail.seller_name, "Detalle del asesor por geografía, categorías y estado de colegios", filters),
        kpis=[
            PDFKpiItem(label="Total Colegios", value=format_integer(detail.total_schools)),
            PDFKpiItem(label="Total Exámenes", value=format_integer(detail.total_exams)),
            PDFKpiItem(label="Sin Categorizar", value=format_currency(detail.uncategorized_revenue)),
            PDFKpiItem(label="Valor Total",    value=format_currency(detail.total_revenue)),
        ],
        geo_table=PDFTable(
            headers=["País", "Sede", "Estado", "Ciudad"],
            rows=[PDFTableRow(cells=[
                ", ".join(detail.countries) or "-",
                ", ".join(detail.zones)     or "-",
                ", ".join(detail.states)    or "-",
                ", ".join(detail.cities)    or "-",
            ])],
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
