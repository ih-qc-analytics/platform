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
from app.services.utils.report_filters import (
    build_payment_fact_where_clause,
    build_student_payment_fact_where_clause,
)
from app.services.por_asesor.product_grouping import (
    EXAM_NAME_ORDER,
    canonical_exam_name,
)
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
    *[ExcelColumn(exam_name, exam_name) for exam_name in DETALLE_EXAM_NAME_ORDER],
]


def summary_bucket_for_exam(label: str) -> str:
    exam_name = canonical_exam_name(label)
    if exam_name == "IELTS":
        return "ielts"
    if exam_name == "MET":
        return "michigan"
    if exam_name == "TEA":
        return "tea"
    if exam_name == "Other":
        return "other"
    return "cambridge"


def build_por_pais_where_clause(
    filters: PorPaisFilters,
) -> tuple[str, dict[str, object], list[str]]:
    return build_payment_fact_where_clause(filters)


def build_por_pais_student_payment_where_clause(
    filters: PorPaisFilters,
) -> tuple[str, dict[str, object], list[str]]:
    return build_student_payment_fact_where_clause(filters, include_exam_product=True)


def rewound_date_range(filters: PorPaisFilters) -> tuple[str, str]:
    date_from_obj = datetime.strptime(filters.date_from, "%Y-%m-%d")
    date_to_obj = datetime.strptime(filters.date_to, "%Y-%m-%d")
    return (
        date_from_obj.replace(year=date_from_obj.year - 1).strftime("%Y-%m-%d"),
        date_to_obj.replace(year=date_to_obj.year - 1).strftime("%Y-%m-%d"),
    )


def build_summary_rows(school_rows, exam_rows) -> list[PorPaisSummaryRow]:
    schools_by_country = {row.country: int(row.total_schools or 0) for row in school_rows}
    counts_by_country: dict[str, dict[str, int]] = {
        country: {
            "cambridge": 0,
            "ielts": 0,
            "michigan": 0,
            "tea": 0,
            "other": 0,
        }
        for country in schools_by_country
    }

    for row in exam_rows:
        country_counts = counts_by_country.setdefault(
            row.country,
            {"cambridge": 0, "ielts": 0, "michigan": 0, "tea": 0, "other": 0},
        )
        count = int(row.exam_count or 0)
        bucket = summary_bucket_for_exam(row.exam_name)
        country_counts[bucket] += count

    return [
        PorPaisSummaryRow(
            country=country,
            total_schools=schools_by_country.get(country, 0),
            cambridge=counts_by_country.get(country, {}).get("cambridge", 0),
            ielts=counts_by_country.get(country, {}).get("ielts", 0),
            michigan=counts_by_country.get(country, {}).get("michigan", 0),
            tea=counts_by_country.get(country, {}).get("tea", 0),
            other=counts_by_country.get(country, {}).get("other", 0),
        )
        for country in sorted(schools_by_country)
    ]


def build_status_rows(current_presence_rows, prior_presence_rows, current_metric_rows, prior_metric_rows) -> list[PorPaisStatusRow]:
    current_by_country: dict[str, set[int]] = defaultdict(set)
    prior_by_country: dict[str, set[int]] = defaultdict(set)
    current_metrics: dict[tuple[str, int], int] = {}
    prior_metrics: dict[tuple[str, int], int] = {}

    for row in current_presence_rows:
        current_by_country[row.country].add(int(row.lead_id))
    for row in prior_presence_rows:
        prior_by_country[row.country].add(int(row.lead_id))
    for row in current_metric_rows:
        current_metrics[(row.country, int(row.lead_id))] = int(row.exams or 0)
    for row in prior_metric_rows:
        prior_metrics[(row.country, int(row.lead_id))] = int(row.exams or 0)

    countries = sorted(set(current_by_country) | set(prior_by_country))
    rows: list[PorPaisStatusRow] = []
    for country in countries:
        current = current_by_country.get(country, set())
        prior = prior_by_country.get(country, set())
        ganados = current - prior
        perdidos = prior - current
        mantenidos = current & prior
        rows.append(
            PorPaisStatusRow(
                country=country,
                schools_ganados=len(ganados),
                schools_perdidos=len(perdidos),
                schools_mantenidos=len(mantenidos),
                exams_ganados=sum(current_metrics.get((country, lead_id), 0) for lead_id in ganados),
                exams_perdidos=sum(prior_metrics.get((country, lead_id), 0) for lead_id in perdidos),
                exams_mantenidos=sum(current_metrics.get((country, lead_id), 0) for lead_id in mantenidos),
            )
        )
    return rows


def build_detail_counts(exam_rows, country: str) -> dict[str, int]:
    counts = {exam_name: 0 for exam_name in DETALLE_EXAM_NAME_ORDER}
    for row in exam_rows:
        if row.country != country:
            continue
        exam_name = canonical_exam_name(row.exam_name)
        counts[exam_name] = counts.get(exam_name, 0) + int(row.exam_count or 0)
    return counts


async def getPorPaisReport(filters: PorPaisFilters) -> PorPaisReportResponse:
    where_clause, params, expanding_keys = build_por_pais_where_clause(filters)
    breakdown_where_clause, breakdown_params, breakdown_expanding_keys = build_por_pais_student_payment_where_clause(filters)
    summary_school_rows, summary_exam_rows = await asyncio.gather(
        fetch_country_school_rows(where_clause, params, expanding_keys),
        fetch_country_exam_rows(breakdown_where_clause, breakdown_params, breakdown_expanding_keys),
    )

    prior_date_from, prior_date_to = rewound_date_range(filters)

    prior_filters = filters.model_copy(update={"date_from": prior_date_from, "date_to": prior_date_to})
    prior_where_clause, prior_params, prior_expanding_keys = build_por_pais_where_clause(prior_filters)
    prior_breakdown_where_clause, prior_breakdown_params, prior_breakdown_expanding_keys = build_por_pais_student_payment_where_clause(
        prior_filters,
    )

    current_presence_rows, prior_presence_rows, current_metric_rows, prior_metric_rows = await asyncio.gather(
        fetch_country_presence_rows(where_clause, params, expanding_keys),
        fetch_country_presence_rows(prior_where_clause, prior_params, prior_expanding_keys),
        fetch_country_metric_rows(breakdown_where_clause, breakdown_params, breakdown_expanding_keys),
        fetch_country_metric_rows(prior_breakdown_where_clause, prior_breakdown_params, prior_breakdown_expanding_keys),
    )

    return PorPaisReportResponse(
        summary_rows=build_summary_rows(summary_school_rows, summary_exam_rows),
        status_rows=build_status_rows(current_presence_rows, prior_presence_rows, current_metric_rows, prior_metric_rows),
    )


async def getPorPaisDetail(country: str, filters: PorPaisFilters) -> PorPaisDetailResponse:
    where_clause, params, expanding_keys = build_por_pais_student_payment_where_clause(filters)
    exam_rows = await fetch_country_exam_rows(where_clause, params, expanding_keys)
    return PorPaisDetailResponse(country=country, exam_counts=build_detail_counts(exam_rows, country))


def build_por_pais_export_filters_for_all(filters: PorPaisFilters) -> PorPaisFilters:
    return filters.model_copy()


async def getPorPaisDetailsForReport(
    report: PorPaisReportResponse,
    filters: PorPaisFilters,
) -> list[PorPaisDetailResponse]:
    if not report.summary_rows:
        return []
    return list(
        await asyncio.gather(
            *(getPorPaisDetail(row.country, filters) for row in report.summary_rows)
        )
    )


def build_por_pais_export_worksheets(
    report: PorPaisReportResponse,
    details: list[PorPaisDetailResponse],
) -> list[ExcelWorksheetSpec]:
    summary_rows = [row.model_dump() for row in report.summary_rows]
    status_rows = [row.model_dump() for row in report.status_rows]
    detail_rows = []
    for detail in details:
        detail_row = {"country": detail.country}
        for exam_name in DETALLE_EXAM_NAME_ORDER:
            detail_row[exam_name] = int(detail.exam_counts.get(exam_name, 0) or 0)
        detail_rows.append(detail_row)

    return [
        ExcelWorksheetSpec(
            name="Por Pais Summary",
            columns=POR_PAIS_SUMMARY_COLUMNS,
            rows=summary_rows,
        ),
        ExcelWorksheetSpec(
            name="Por Pais Status",
            columns=POR_PAIS_STATUS_COLUMNS,
            rows=status_rows,
        ),
        ExcelWorksheetSpec(
            name="Por Pais Detail",
            columns=POR_PAIS_DETAIL_COLUMNS,
            rows=detail_rows,
        ),
    ]


async def build_por_pais_pdf_payload(filters: PorPaisFilters) -> PorPaisPDFPayload:
    report = await getPorPaisReport(filters)

    total_schools = sum(row.total_schools for row in report.summary_rows)
    total_cambridge = sum(row.cambridge for row in report.summary_rows)
    total_ielts = sum(row.ielts for row in report.summary_rows)
    total_met = sum(row.michigan for row in report.summary_rows)
    total_otros = sum(row.tea + row.other for row in report.summary_rows)

    summary_rows = [
        PDFTableRow(
            cells=[
                row.country,
                format_integer(row.total_schools),
                format_integer(row.cambridge),
                format_integer(row.ielts),
                format_integer(row.michigan),
                format_integer(row.tea),
                format_integer(row.other),
            ]
        )
        for row in report.summary_rows
    ]
    status_rows = [
        PDFTableRow(
            cells=[
                row.country,
                format_integer(row.schools_ganados),
                format_integer(row.schools_perdidos),
                format_integer(row.schools_mantenidos),
                format_integer(row.exams_ganados),
                format_integer(row.exams_perdidos),
                format_integer(row.exams_mantenidos),
            ]
        )
        for row in report.status_rows
    ]

    return PorPaisPDFPayload(
        header=build_pdf_header(
            "Resultado por País",
            "Resumen por país y estado de colegios/exámenes",
            filters,
        ),
        kpis=[
            PDFKpiItem(label="Países", value=format_integer(len(report.summary_rows))),
            PDFKpiItem(label="Colegios", value=format_integer(total_schools)),
            PDFKpiItem(label="Cambridge", value=format_integer(total_cambridge)),
            PDFKpiItem(label="IELTS", value=format_integer(total_ielts)),
            PDFKpiItem(label="MET", value=format_integer(total_met)),
            PDFKpiItem(label="Otros", value=format_integer(total_otros)),
        ],
        summary_table=PDFTable(
            headers=["País", "Colegios", "Cambridge", "IELTS", "MET", "TEA", "Otros"],
            rows=summary_rows,
            column_widths=[3, 2, 2, 2, 2, 2, 2],
        ),
        status_table=PDFTable(
            headers=[
                "País",
                "Col. Ganados",
                "Col. Perdidos",
                "Col. Mantenidos",
                "Ex. Ganados",
                "Ex. Perdidos",
                "Ex. Mantenidos",
            ],
            rows=status_rows,
            column_widths=[3, 2, 2, 2, 2, 2, 2],
        ),
    )


async def build_por_pais_detail_pdf_payload(
    country: str,
    filters: PorPaisFilters,
) -> PorPaisDetailPDFPayload:
    detail = await getPorPaisDetail(country, filters)

    total_exams = sum(detail.exam_counts.values())
    active_exam_types = sum(1 for count in detail.exam_counts.values() if count > 0)
    cambridge_total = sum(
        count
        for exam_name, count in detail.exam_counts.items()
        if exam_name not in {"IELTS", "MET", "MET Go!", "TEA", "Other"}
    )
    other_total = sum(
        detail.exam_counts.get(exam_name, 0)
        for exam_name in ("MET", "MET Go!", "TEA", "Other")
    )

    detail_rows = [
        PDFTableRow(cells=[exam_name, format_integer(count)])
        for exam_name in DETALLE_EXAM_NAME_ORDER
        if (count := int(detail.exam_counts.get(exam_name, 0) or 0)) > 0
    ]

    return PorPaisDetailPDFPayload(
        header=build_pdf_header(
            f"Detalle por País - {detail.country}",
            "Desglose por examen para el país seleccionado",
            filters,
        ),
        kpis=[
            PDFKpiItem(label="País", value=detail.country),
            PDFKpiItem(label="Exámenes", value=format_integer(total_exams)),
            PDFKpiItem(label="Tipos Activos", value=format_integer(active_exam_types)),
            PDFKpiItem(label="Cambridge", value=format_integer(cambridge_total)),
            PDFKpiItem(label="IELTS", value=format_integer(detail.exam_counts.get("IELTS", 0))),
            PDFKpiItem(label="Otros", value=format_integer(other_total)),
        ],
        detail_table=PDFTable(
            headers=["Examen", "Cantidad"],
            rows=detail_rows,
            column_widths=[4, 2],
        ),
    )
