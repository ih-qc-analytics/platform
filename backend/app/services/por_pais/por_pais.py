import asyncio
from collections import defaultdict

from app.enums import BaseCurrency, ComparisonMode, ProductType
from app.schemas.pdf import (
    PDFKpiItem,
    PDFTable,
    PDFTableRow,
    PorPaisDetailPDFPayload,
    PorPaisPDFPayload,
)
from app.schemas.reports import (
    PorPaisDetailResponse,
    PorPaisFilters,
    PorPaisReportBase,
    PorPaisReportComparison,
    PorPaisReportResponse,
    PorPaisStatusRow,
    PorPaisSummaryRow,
)
from app.services.exports.pdf_helpers import build_pdf_header, format_currency, format_integer
from app.services.exports.excel import ExcelColumn, ExcelWorksheetSpec
from app.services.por_asesor.product_grouping import EXAM_NAME_ORDER, canonical_exam_name
from app.services.utils.date_utils import resolve_comparison_range
from app.services.por_pais.repository import (
    fetch_country_allocated_revenue_rows,
    fetch_country_exam_rows,
    fetch_country_metric_rows,
    fetch_country_payment_rows,
    fetch_country_presence_rows,
)

DETALLE_EXAM_NAME_ORDER = [*EXAM_NAME_ORDER, "Other"]

POR_PAIS_SUMMARY_COLUMNS = [
    ExcelColumn("country", "Country"),
    ExcelColumn("total_schools", "Total Schools"),
    ExcelColumn("total_revenue", "Total Revenue"),
    ExcelColumn("uncategorized_revenue", "Uncategorized Revenue"),
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


def summary_bucket_for_exam(exam_name: str) -> str:
    name = canonical_exam_name(exam_name)
    if name == "IELTS":
        return "ielts"
    if name == "MET":
        return "michigan"
    if name == "TEA":
        return "tea"
    if name == "Other":
        return "other"
    return "cambridge"


def build_summary_rows(payment_rows, allocated_rows, exam_rows) -> list[PorPaisSummaryRow]:
    schools_by_country = {row.country: int(row.total_schools or 0) for row in payment_rows}
    payment_revenue_by_country = {
        row.country: float(row.total_revenue or 0) for row in payment_rows
    }
    allocated_revenue_by_country = {
        row.country: float(row.allocated_revenue or 0) for row in allocated_rows
    }
    counts: dict[str, dict[str, int]] = {
        country: {"cambridge": 0, "ielts": 0, "michigan": 0, "tea": 0, "other": 0}
        for country in schools_by_country
    }
    for row in exam_rows:
        bucket = summary_bucket_for_exam(row.exam_name)
        counts.setdefault(
            row.country, {"cambridge": 0, "ielts": 0, "michigan": 0, "tea": 0, "other": 0}
        )[bucket] += int(row.exam_count or 0)

    return [
        PorPaisSummaryRow(
            country=country,
            total_schools=schools_by_country.get(country, 0),
            total_revenue=payment_revenue_by_country.get(country, 0.0),
            uncategorized_revenue=payment_revenue_by_country.get(country, 0.0)
            - allocated_revenue_by_country.get(country, 0.0),
            cambridge=counts.get(country, {}).get("cambridge", 0),
            ielts=counts.get(country, {}).get("ielts", 0),
            michigan=counts.get(country, {}).get("michigan", 0),
            tea=counts.get(country, {}).get("tea", 0),
            other=counts.get(country, {}).get("other", 0),
        )
        for country in sorted(schools_by_country)
    ]


def build_status_rows(
    current_presence, prior_presence, current_metrics, prior_metrics
) -> list[PorPaisStatusRow]:
    current_by_country: dict[str, set[int]] = defaultdict(set)
    prior_by_country: dict[str, set[int]] = defaultdict(set)
    current_metric_map: dict[tuple, int] = {}
    prior_metric_map: dict[tuple, int] = {}

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
                exams_ganados=sum(current_metric_map.get((country, lid), 0) for lid in ganados),
                exams_perdidos=sum(prior_metric_map.get((country, lid), 0) for lid in perdidos),
                exams_mantenidos=sum(
                    current_metric_map.get((country, lid), 0) for lid in mantenidos
                ),
            )
        )
    return rows


def build_detail_counts(exam_rows, country: str) -> dict[str, int]:
    counts = {name: 0 for name in DETALLE_EXAM_NAME_ORDER}
    for row in exam_rows:
        if row.country != country:
            continue
        name = canonical_exam_name(row.exam_name)
        counts[name] = counts.get(name, 0) + int(row.exam_count or 0)
    return counts


async def _get_por_pais_base(
    filters: PorPaisFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> PorPaisReportBase:
    (
        payment_rows,
        allocated_rows,
        exam_rows,
        current_presence,
        comparison_presence,
        current_metrics,
        comparison_metrics,
    ) = await asyncio.gather(
        fetch_country_payment_rows(filters, base_currency=base_currency),
        fetch_country_allocated_revenue_rows(filters, base_currency=base_currency),
        fetch_country_exam_rows(filters),
        fetch_country_presence_rows(filters),
        fetch_country_presence_rows(filters),
        fetch_country_metric_rows(filters),
        fetch_country_metric_rows(filters),
    )

    return PorPaisReportBase(
        summary_rows=build_summary_rows(payment_rows, allocated_rows, exam_rows),
        status_rows=build_status_rows(
            current_presence, comparison_presence, current_metrics, comparison_metrics
        ),
    )


async def getPorPaisReport(
    filters: PorPaisFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> PorPaisReportResponse:
    comparison_meta = resolve_comparison_range(filters)
    current_filters = filters.model_copy(
        update={
            "show_comparison": False,
            "comparison_date_from": None,
            "comparison_date_to": None,
        }
    )

    if comparison_meta is None:
        current = await _get_por_pais_base(current_filters, base_currency=base_currency)
        return PorPaisReportResponse(current=current, comparison_mode=None, comparison=None)

    current_status_filters = current_filters.model_copy()
    comparison_status_filters = current_filters.model_copy(
        update={
            "date_from": comparison_meta.date_from,
            "date_to": comparison_meta.date_to,
        }
    )

    (
        current_summary,
        current_presence,
        current_metrics,
        comparison_summary,
        comparison_presence,
        comparison_metrics,
    ) = await asyncio.gather(
        asyncio.gather(
            fetch_country_payment_rows(current_status_filters, base_currency=base_currency),
            fetch_country_allocated_revenue_rows(
                current_status_filters, base_currency=base_currency
            ),
            fetch_country_exam_rows(current_status_filters),
        ),
        fetch_country_presence_rows(current_status_filters),
        fetch_country_metric_rows(current_status_filters),
        asyncio.gather(
            fetch_country_payment_rows(comparison_status_filters, base_currency=base_currency),
            fetch_country_allocated_revenue_rows(
                comparison_status_filters, base_currency=base_currency
            ),
            fetch_country_exam_rows(comparison_status_filters),
        ),
        fetch_country_presence_rows(comparison_status_filters),
        fetch_country_metric_rows(comparison_status_filters),
    )

    current = PorPaisReportBase(
        summary_rows=build_summary_rows(*current_summary),
        status_rows=build_status_rows(
            current_presence, comparison_presence, current_metrics, comparison_metrics
        ),
    )
    comparison = PorPaisReportBase(
        summary_rows=build_summary_rows(*comparison_summary),
        status_rows=build_status_rows(
            comparison_presence, current_presence, comparison_metrics, current_metrics
        ),
    )

    return PorPaisReportResponse(
        current=current,
        comparison_mode=comparison_meta.mode,
        comparison=PorPaisReportComparison(
            meta=comparison_meta,
            data=comparison,
            deltas={},
        ),
    )


async def getPorPaisDetail(country: str, filters: PorPaisFilters) -> PorPaisDetailResponse:
    exam_rows = await fetch_country_exam_rows(filters)
    return PorPaisDetailResponse(
        country=country, exam_counts=build_detail_counts(exam_rows, country)
    )


async def getPorPaisDetailsForReport(
    report: PorPaisReportResponse,
    filters: PorPaisFilters,
) -> list[PorPaisDetailResponse]:
    if not report.current.summary_rows:
        return []
    return list(
        await asyncio.gather(
            *(getPorPaisDetail(row.country, filters) for row in report.current.summary_rows)
        )
    )


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
        ExcelWorksheetSpec(
            name="Por Pais Summary",
            columns=POR_PAIS_SUMMARY_COLUMNS,
            rows=[r.model_dump() for r in report.current.summary_rows],
        ),
        ExcelWorksheetSpec(
            name="Por Pais Status",
            columns=POR_PAIS_STATUS_COLUMNS,
            rows=[r.model_dump() for r in report.current.status_rows],
        ),
        ExcelWorksheetSpec(
            name="Por Pais Detail", columns=POR_PAIS_DETAIL_COLUMNS, rows=detail_rows
        ),
    ]


async def build_por_pais_pdf_payload(
    filters: PorPaisFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> PorPaisPDFPayload:
    report = await getPorPaisReport(filters, base_currency=base_currency)
    current = report.current

    total_schools = sum(r.total_schools for r in current.summary_rows)
    total_revenue = sum(r.total_revenue for r in current.summary_rows)
    total_uncategorized = sum(r.uncategorized_revenue for r in current.summary_rows)
    total_cambridge = sum(r.cambridge for r in current.summary_rows)
    total_ielts = sum(r.ielts for r in current.summary_rows)
    total_met = sum(r.michigan for r in current.summary_rows)
    total_otros = sum(r.tea + r.other for r in current.summary_rows)

    return PorPaisPDFPayload(
        header=build_pdf_header(
            "Resultado por País", "Resumen por país y estado de colegios/exámenes", filters
        ),
        kpis=[
            PDFKpiItem(label="Países", value=format_integer(len(current.summary_rows))),
            PDFKpiItem(label="Colegios", value=format_integer(total_schools)),
            PDFKpiItem(label="Ingreso Total", value=format_currency(total_revenue, base_currency)),
            PDFKpiItem(
                label="Sin Categorizar", value=format_currency(total_uncategorized, base_currency)
            ),
            PDFKpiItem(label="Cambridge", value=format_integer(total_cambridge)),
            PDFKpiItem(label="IELTS", value=format_integer(total_ielts)),
            PDFKpiItem(label="MET", value=format_integer(total_met)),
            PDFKpiItem(label="Otros", value=format_integer(total_otros)),
        ],
        summary_table=PDFTable(
            headers=[
                "País",
                "Colegios",
                "Ingreso",
                "Sin Categorizar",
                "Cambridge",
                "IELTS",
                "MET",
                "TEA",
                "Otros",
            ],
            rows=[
                PDFTableRow(
                    cells=[
                        r.country,
                        format_integer(r.total_schools),
                        format_currency(r.total_revenue, base_currency),
                        format_currency(r.uncategorized_revenue, base_currency),
                        format_integer(r.cambridge),
                        format_integer(r.ielts),
                        format_integer(r.michigan),
                        format_integer(r.tea),
                        format_integer(r.other),
                    ]
                )
                for r in current.summary_rows
            ],
            column_widths=[3, 2, 2, 2, 2, 2, 2, 2, 2],
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
            rows=[
                PDFTableRow(
                    cells=[
                        r.country,
                        format_integer(r.schools_ganados),
                        format_integer(r.schools_perdidos),
                        format_integer(r.schools_mantenidos),
                        format_integer(r.exams_ganados),
                        format_integer(r.exams_perdidos),
                        format_integer(r.exams_mantenidos),
                    ]
                )
                for r in current.status_rows
            ],
            column_widths=[3, 2, 2, 2, 2, 2, 2],
        ),
    )


async def build_por_pais_detail_pdf_payload(
    country: str, filters: PorPaisFilters
) -> PorPaisDetailPDFPayload:
    detail = await getPorPaisDetail(country, filters)

    total_exams = sum(detail.exam_counts.values())
    active_exam_types = sum(1 for c in detail.exam_counts.values() if c > 0)
    cambridge_total = sum(
        count
        for name, count in detail.exam_counts.items()
        if name not in {"IELTS", "MET", "MET Go!", "TEA", "Other"}
    )
    other_total = sum(detail.exam_counts.get(n, 0) for n in ("MET", "MET Go!", "TEA", "Other"))

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
            rows=[
                PDFTableRow(cells=[name, format_integer(count)])
                for name in DETALLE_EXAM_NAME_ORDER
                if (count := int(detail.exam_counts.get(name, 0) or 0)) > 0
            ],
            column_widths=[4, 2],
        ),
    )
