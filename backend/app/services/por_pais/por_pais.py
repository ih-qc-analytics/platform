import asyncio
from collections import defaultdict
from datetime import datetime

from app.enums import ProductType
from app.schemas.pdf import PDFKpiItem, PDFTable, PDFTableRow, PorPaisDetailPDFPayload, PorPaisPDFPayload
from app.schemas.reports import (
    PorPaisDetailResponse,
    PorPaisFilters,
    PorPaisReportResponse,
    PorPaisStatusRow,
    PorPaisSummaryRow,
)
from app.services.exports.pdf_helpers import build_pdf_header, format_integer
from app.services.exports.excel import ExcelColumn, ExcelWorksheetSpec
from app.services.por_asesor.product_grouping import EXAM_NAME_ORDER, canonical_exam_name
from app.services.por_pais.repository import (
    fetch_country_exam_rows,
    fetch_country_metric_rows,
    fetch_country_presence_rows,
    fetch_country_school_rows,
)

DETALLE_EXAM_NAME_ORDER = [*EXAM_NAME_ORDER, "Other"]

POR_PAIS_SUMMARY_COLUMNS = [
    ExcelColumn("country", "Country"),
    ExcelColumn("total_schools", "Total Schools"),
    ExcelColumn("cambridge", "Cambridge"),
    ExcelColumn("ielts", "IELTS"),
    ExcelColumn("michigan", "Michigan"),
    ExcelColumn("tea", "TEA"),
    ExcelColumn("other", "Other"),
]
POR_PAIS_STATUS_COLUMNS = [
    ExcelColumn("country", "Country"),
    ExcelColumn("schools_ganados", "Schools Ganados"),
    ExcelColumn("schools_perdidos", "Schools Perdidos"),
    ExcelColumn("schools_mantenidos", "Schools Mantenidos"),
    ExcelColumn("exams_ganados", "Exams Ganados"),
    ExcelColumn("exams_perdidos", "Exams Perdidos"),
    ExcelColumn("exams_mantenidos", "Exams Mantenidos"),
]
POR_PAIS_DETAIL_COLUMNS = [
    ExcelColumn("country", "Country"),
    *[ExcelColumn(name, name) for name in DETALLE_EXAM_NAME_ORDER],
]


def _rewound_dates(filters: PorPaisFilters) -> tuple[str, str]:
    date_from = datetime.strptime(filters.date_from, "%Y-%m-%d").replace(
        year=datetime.strptime(filters.date_from, "%Y-%m-%d").year - 1
    ).strftime("%Y-%m-%d")
    date_to = datetime.strptime(filters.date_to, "%Y-%m-%d").replace(
        year=datetime.strptime(filters.date_to, "%Y-%m-%d").year - 1
    ).strftime("%Y-%m-%d")
    return date_from, date_to


def summary_bucket_for_exam(exam_name: str) -> str:
    name = canonical_exam_name(exam_name)
    if name == "IELTS":   return "ielts"
    if name == "MET":     return "michigan"
    if name == "TEA":     return "tea"
    if name == "Other":   return "other"
    return "cambridge"


def build_summary_rows(school_rows, exam_rows) -> list[PorPaisSummaryRow]:
    schools_by_country = {row.country: int(row.total_schools or 0) for row in school_rows}
    counts: dict[str, dict[str, int]] = {
        country: {"cambridge": 0, "ielts": 0, "michigan": 0, "tea": 0, "other": 0}
        for country in schools_by_country
    }
    for row in exam_rows:
        bucket = summary_bucket_for_exam(row.exam_name)
        counts.setdefault(row.country, {"cambridge": 0, "ielts": 0, "michigan": 0, "tea": 0, "other": 0})[bucket] += int(row.exam_count or 0)

    return [
        PorPaisSummaryRow(
            country=country,
            total_schools=schools_by_country.get(country, 0),
            cambridge=counts.get(country, {}).get("cambridge", 0),
            ielts=counts.get(country, {}).get("ielts", 0),
            michigan=counts.get(country, {}).get("michigan", 0),
            tea=counts.get(country, {}).get("tea", 0),
            other=counts.get(country, {}).get("other", 0),
        )
        for country in sorted(schools_by_country)
    ]


def build_status_rows(current_presence, prior_presence, current_metrics, prior_metrics) -> list[PorPaisStatusRow]:
    current_by_country: dict[str, set[int]] = defaultdict(set)
    prior_by_country:   dict[str, set[int]] = defaultdict(set)
    current_metric_map: dict[tuple, int]    = {}
    prior_metric_map:   dict[tuple, int]    = {}

    for row in current_presence:
        current_by_country[row.country].add(int(row.lead_id))
    for row in prior_presence:
        prior_by_country[row.country].add(int(row.lead_id))
    for row in current_metrics:
        current_metric_map[(row.country, int(row.lead_id))] = int(row.exams or 0)
    for row in prior_metrics:
        prior_metric_map[(row.country, int(row.lead_id))] = int(row.exams or 0)

    countries = sorted(set(current_by_country) | set(prior_by_country))
    rows: list[PorPaisStatusRow] = []
    for country in countries:
        current  = current_by_country.get(country, set())
        prior    = prior_by_country.get(country, set())
        ganados  = current - prior
        perdidos = prior   - current
        mantenidos = current & prior
        rows.append(PorPaisStatusRow(
            country=country,
            schools_ganados=len(ganados),
            schools_perdidos=len(perdidos),
            schools_mantenidos=len(mantenidos),
            exams_ganados=  sum(current_metric_map.get((country, lid), 0) for lid in ganados),
            exams_perdidos= sum(prior_metric_map.get((country, lid), 0)   for lid in perdidos),
            exams_mantenidos=sum(current_metric_map.get((country, lid), 0) for lid in mantenidos),
        ))
    return rows


def build_detail_counts(exam_rows, country: str) -> dict[str, int]:
    counts = {name: 0 for name in DETALLE_EXAM_NAME_ORDER}
    for row in exam_rows:
        if row.country != country:
            continue
        name = canonical_exam_name(row.exam_name)
        counts[name] = counts.get(name, 0) + int(row.exam_count or 0)
    return counts


async def getPorPaisReport(filters: PorPaisFilters) -> PorPaisReportResponse:
    prior_from, prior_to = _rewound_dates(filters)

    (
        school_rows, exam_rows,
        current_presence, prior_presence,
        current_metrics,  prior_metrics,
    ) = await asyncio.gather(
        fetch_country_school_rows(filters.date_from, filters.date_to),
        fetch_country_exam_rows(filters.date_from, filters.date_to),
        fetch_country_presence_rows(filters.date_from, filters.date_to),
        fetch_country_presence_rows(prior_from, prior_to),
        fetch_country_metric_rows(filters.date_from, filters.date_to),
        fetch_country_metric_rows(prior_from, prior_to),
    )

    return PorPaisReportResponse(
        summary_rows=build_summary_rows(school_rows, exam_rows),
        status_rows=build_status_rows(current_presence, prior_presence, current_metrics, prior_metrics),
    )


async def getPorPaisDetail(country: str, filters: PorPaisFilters) -> PorPaisDetailResponse:
    exam_rows = await fetch_country_exam_rows(filters.date_from, filters.date_to)
    return PorPaisDetailResponse(country=country, exam_counts=build_detail_counts(exam_rows, country))


async def getPorPaisDetailsForReport(
    report: PorPaisReportResponse,
    filters: PorPaisFilters,
) -> list[PorPaisDetailResponse]:
    if not report.summary_rows:
        return []
    return list(await asyncio.gather(*(getPorPaisDetail(row.country, filters) for row in report.summary_rows)))


def build_por_pais_export_filters_for_all(filters: PorPaisFilters) -> PorPaisFilters:
    return filters.model_copy()


def build_por_pais_export_worksheets(
    report: PorPaisReportResponse,
    details: list[PorPaisDetailResponse],
) -> list[ExcelWorksheetSpec]:
    detail_rows = []
    for detail in details:
        row = {"country": detail.country}
        for name in DETALLE_EXAM_NAME_ORDER:
            row[name] = int(detail.exam_counts.get(name, 0) or 0)
        detail_rows.append(row)

    return [
        ExcelWorksheetSpec(name="Por Pais Summary", columns=POR_PAIS_SUMMARY_COLUMNS, rows=[r.model_dump() for r in report.summary_rows]),
        ExcelWorksheetSpec(name="Por Pais Status",  columns=POR_PAIS_STATUS_COLUMNS,  rows=[r.model_dump() for r in report.status_rows]),
        ExcelWorksheetSpec(name="Por Pais Detail",  columns=POR_PAIS_DETAIL_COLUMNS,  rows=detail_rows),
    ]


async def build_por_pais_pdf_payload(filters: PorPaisFilters) -> PorPaisPDFPayload:
    report = await getPorPaisReport(filters)

    total_schools  = sum(r.total_schools for r in report.summary_rows)
    total_cambridge = sum(r.cambridge    for r in report.summary_rows)
    total_ielts    = sum(r.ielts         for r in report.summary_rows)
    total_met      = sum(r.michigan      for r in report.summary_rows)
    total_otros    = sum(r.tea + r.other for r in report.summary_rows)

    return PorPaisPDFPayload(
        header=build_pdf_header("Resultado por País", "Resumen por país y estado de colegios/exámenes", filters),
        kpis=[
            PDFKpiItem(label="Países",    value=format_integer(len(report.summary_rows))),
            PDFKpiItem(label="Colegios",  value=format_integer(total_schools)),
            PDFKpiItem(label="Cambridge", value=format_integer(total_cambridge)),
            PDFKpiItem(label="IELTS",     value=format_integer(total_ielts)),
            PDFKpiItem(label="MET",       value=format_integer(total_met)),
            PDFKpiItem(label="Otros",     value=format_integer(total_otros)),
        ],
        summary_table=PDFTable(
            headers=["País", "Colegios", "Cambridge", "IELTS", "MET", "TEA", "Otros"],
            rows=[PDFTableRow(cells=[
                r.country, format_integer(r.total_schools), format_integer(r.cambridge),
                format_integer(r.ielts), format_integer(r.michigan),
                format_integer(r.tea),   format_integer(r.other),
            ]) for r in report.summary_rows],
            column_widths=[3, 2, 2, 2, 2, 2, 2],
        ),
        status_table=PDFTable(
            headers=["País", "Col. Ganados", "Col. Perdidos", "Col. Mantenidos", "Ex. Ganados", "Ex. Perdidos", "Ex. Mantenidos"],
            rows=[PDFTableRow(cells=[
                r.country,
                format_integer(r.schools_ganados),   format_integer(r.schools_perdidos),   format_integer(r.schools_mantenidos),
                format_integer(r.exams_ganados),     format_integer(r.exams_perdidos),     format_integer(r.exams_mantenidos),
            ]) for r in report.status_rows],
            column_widths=[3, 2, 2, 2, 2, 2, 2],
        ),
    )


async def build_por_pais_detail_pdf_payload(country: str, filters: PorPaisFilters) -> PorPaisDetailPDFPayload:
    detail = await getPorPaisDetail(country, filters)

    total_exams      = sum(detail.exam_counts.values())
    active_exam_types = sum(1 for c in detail.exam_counts.values() if c > 0)
    cambridge_total  = sum(
        count for name, count in detail.exam_counts.items()
        if name not in {"IELTS", "MET", "MET Go!", "TEA", "Other"}
    )
    other_total = sum(detail.exam_counts.get(n, 0) for n in ("MET", "MET Go!", "TEA", "Other"))

    return PorPaisDetailPDFPayload(
        header=build_pdf_header(f"Detalle por País - {detail.country}", "Desglose por examen para el país seleccionado", filters),
        kpis=[
            PDFKpiItem(label="País",          value=detail.country),
            PDFKpiItem(label="Exámenes",      value=format_integer(total_exams)),
            PDFKpiItem(label="Tipos Activos", value=format_integer(active_exam_types)),
            PDFKpiItem(label="Cambridge",     value=format_integer(cambridge_total)),
            PDFKpiItem(label="IELTS",         value=format_integer(detail.exam_counts.get("IELTS", 0))),
            PDFKpiItem(label="Otros",         value=format_integer(other_total)),
        ],
        detail_table=PDFTable(
            headers=["Examen", "Cantidad"],
            rows=[
                PDFTableRow(cells=[name, format_integer(count)])
                for name in DETALLE_EXAM_NAME_ORDER
                if (count := int(detail.exam_counts.get(name, 0) or 0)) > 0
            ],
            column_widths=[4, 2],
        ),
    )
