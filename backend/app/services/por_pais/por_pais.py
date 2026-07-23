import asyncio
from collections import defaultdict

from app.enums import BaseCurrency, ComparisonMode, ProductType
from app.schemas.pdf import (
    PDFKpiItem,
    PDFTable,
    PDFTableCellDelta,
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
from app.services.exports.pdf_helpers import (
    build_pdf_header,
    format_currency,
    format_delta,
    format_growth,
    format_integer,
)
from app.services.exports.excel import ExcelColumn, ExcelWorksheetSpec
from app.services.por_asesor.product_grouping import EXAM_NAME_ORDER, canonical_exam_name
from app.services.utils.date_utils import (
    percent_change,
    resolve_comparison_range,
)
from app.services.por_pais.repository import (
    fetch_country_allocated_revenue_rows,
    fetch_country_books_courses_presence_rows,
    fetch_country_exam_rows,
    fetch_country_product_metric_rows,
    fetch_country_payment_rows,
    fetch_country_presence_rows,
)

DETALLE_EXAM_NAME_ORDER = [*EXAM_NAME_ORDER, "Other"]

POR_PAIS_SUMMARY_COLUMNS = [
    ExcelColumn("country", "País"),
    ExcelColumn("total_schools", "Total Colegios"),
    ExcelColumn("total_revenue", "Ingreso Total"),
    ExcelColumn("exam_revenue", "Ingreso Exámenes"),
    ExcelColumn("book_revenue", "Ingreso Libros"),
    ExcelColumn("course_revenue", "Ingreso Cursos"),
    ExcelColumn("uncategorized_revenue", "Ingreso Sin Categorizar"),
    ExcelColumn("cambridge", "Cambridge"),
    ExcelColumn("ielts", "IELTS"),
    ExcelColumn("michigan", "Michigan"),
    ExcelColumn("tea", "TEA"),
    ExcelColumn("other", "Otros"),
    ExcelColumn("total_books", "Libros"),
    ExcelColumn("total_courses", "Cursos"),
]
POR_PAIS_STATUS_COLUMNS = [
    ExcelColumn("country", "País"),
    ExcelColumn("schools_ganados", "Colegios Ganados"),
    ExcelColumn("schools_perdidos", "Colegios Perdidos"),
    ExcelColumn("schools_mantenidos", "Colegios Mantenidos"),
    ExcelColumn("exams_ganados", "Exámenes Ganados"),
    ExcelColumn("exams_perdidos", "Exámenes Perdidos"),
    ExcelColumn("exams_mantenidos", "Exámenes Mantenidos"),
    ExcelColumn("books_courses_ganados", "L+C Ganados"),
    ExcelColumn("books_courses_perdidos", "L+C Perdidos"),
    ExcelColumn("books_courses_mantenidos", "L+C Mantenidos"),
]
POR_PAIS_DETAIL_COLUMNS = [
    ExcelColumn("country", "País"),
    *[ExcelColumn(name, name) for name in DETALLE_EXAM_NAME_ORDER],
    ExcelColumn("total_books", "Libros"),
    ExcelColumn("total_courses", "Cursos"),
    ExcelColumn("book_revenue", "Ingreso Libros"),
    ExcelColumn("course_revenue", "Ingreso Cursos"),
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
    allocated_rev_by_country: dict[str, float] = {}
    exam_rev_by_country: dict[str, float] = {}
    book_rev_by_country: dict[str, float] = {}
    course_rev_by_country: dict[str, float] = {}
    books_by_country: dict[str, int] = {}
    courses_by_country: dict[str, int] = {}
    for row in allocated_rows:
        allocated_rev_by_country[row.country] = float(getattr(row, "allocated_revenue", 0) or 0)
        exam_rev_by_country[row.country] = float(getattr(row, "exam_revenue", 0) or 0)
        book_rev_by_country[row.country] = float(getattr(row, "book_revenue", 0) or 0)
        course_rev_by_country[row.country] = float(getattr(row, "course_revenue", 0) or 0)
        books_by_country[row.country] = int(getattr(row, "total_books", 0) or 0)
        courses_by_country[row.country] = int(getattr(row, "total_courses", 0) or 0)

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
            - allocated_rev_by_country.get(country, 0.0),
            cambridge=counts.get(country, {}).get("cambridge", 0),
            ielts=counts.get(country, {}).get("ielts", 0),
            michigan=counts.get(country, {}).get("michigan", 0),
            tea=counts.get(country, {}).get("tea", 0),
            other=counts.get(country, {}).get("other", 0),
            total_books=books_by_country.get(country, 0),
            total_courses=courses_by_country.get(country, 0),
            exam_revenue=exam_rev_by_country.get(country, 0.0),
            book_revenue=book_rev_by_country.get(country, 0.0),
            course_revenue=course_rev_by_country.get(country, 0.0),
        )
        for country in sorted(schools_by_country)
    ]


def build_status_rows(
    current_presence,
    prior_presence,
    current_metrics,
    prior_metrics,
    current_bc_presence=None,
    prior_bc_presence=None,
) -> list[PorPaisStatusRow]:
    current_by_country: dict[str, set[int]] = defaultdict(set)
    prior_by_country: dict[str, set[int]] = defaultdict(set)
    current_metric_map: dict[tuple, int] = {}
    prior_metric_map: dict[tuple, int] = {}
    current_bc_by_country: dict[str, set[int]] = defaultdict(set)
    prior_bc_by_country: dict[str, set[int]] = defaultdict(set)

    for row in current_presence:
        current_by_country[row.country].add(int(row.lead_id))
    for row in prior_presence:
        prior_by_country[row.country].add(int(row.lead_id))
    for row in current_metrics:
        current_metric_map[(row.country, int(row.lead_id))] = int(row.exams or 0)
    for row in prior_metrics:
        prior_metric_map[(row.country, int(row.lead_id))] = int(row.exams or 0)
    for row in current_bc_presence or []:
        current_bc_by_country[row.country].add(int(row.lead_id))
    for row in prior_bc_presence or []:
        prior_bc_by_country[row.country].add(int(row.lead_id))

    countries = sorted(set(current_by_country) | set(prior_by_country))
    rows: list[PorPaisStatusRow] = []
    for country in countries:
        current = current_by_country.get(country, set())
        prior = prior_by_country.get(country, set())
        ganados = current - prior
        perdidos = prior - current
        mantenidos = current & prior
        bc_current = current_bc_by_country.get(country, set())
        bc_prior = prior_bc_by_country.get(country, set())
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
                books_courses_ganados=len(bc_current - bc_prior),
                books_courses_perdidos=len(bc_prior - bc_current),
                books_courses_mantenidos=len(bc_current & bc_prior),
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
        current_metrics,
    ) = await asyncio.gather(
        fetch_country_payment_rows(filters, base_currency=base_currency),
        fetch_country_allocated_revenue_rows(filters, base_currency=base_currency),
        fetch_country_exam_rows(filters),
        fetch_country_presence_rows(filters),
        fetch_country_product_metric_rows(filters),
    )

    return PorPaisReportBase(
        summary_rows=build_summary_rows(payment_rows, allocated_rows, exam_rows),
        status_rows=build_status_rows(
            current_presence, current_presence, current_metrics, current_metrics
        ),
    )


async def get_por_pais_report(
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
        current_bc_presence,
        comparison_summary,
        comparison_presence,
        comparison_metrics,
        comparison_bc_presence,
    ) = await asyncio.gather(
        asyncio.gather(
            fetch_country_payment_rows(current_status_filters, base_currency=base_currency),
            fetch_country_allocated_revenue_rows(
                current_status_filters, base_currency=base_currency
            ),
            fetch_country_exam_rows(current_status_filters),
        ),
        fetch_country_presence_rows(current_status_filters),
        fetch_country_product_metric_rows(current_status_filters),
        fetch_country_books_courses_presence_rows(current_status_filters),
        asyncio.gather(
            fetch_country_payment_rows(comparison_status_filters, base_currency=base_currency),
            fetch_country_allocated_revenue_rows(
                comparison_status_filters, base_currency=base_currency
            ),
            fetch_country_exam_rows(comparison_status_filters),
        ),
        fetch_country_presence_rows(comparison_status_filters),
        fetch_country_product_metric_rows(comparison_status_filters),
        fetch_country_books_courses_presence_rows(comparison_status_filters),
    )

    current = PorPaisReportBase(
        summary_rows=build_summary_rows(*current_summary),
        status_rows=build_status_rows(
            current_presence,
            comparison_presence,
            current_metrics,
            comparison_metrics,
            current_bc_presence,
            comparison_bc_presence,
        ),
    )
    comparison = PorPaisReportBase(
        summary_rows=build_summary_rows(*comparison_summary),
        status_rows=build_status_rows(
            comparison_presence,
            current_presence,
            comparison_metrics,
            current_metrics,
            comparison_bc_presence,
            current_bc_presence,
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


def _extract_country_product_totals(allocated_rows, country: str) -> dict:
    for row in allocated_rows:
        if row.country == country:
            return {
                "total_books": int(getattr(row, "total_books", 0) or 0),
                "total_courses": int(getattr(row, "total_courses", 0) or 0),
                "book_revenue": float(getattr(row, "book_revenue", 0) or 0),
                "course_revenue": float(getattr(row, "course_revenue", 0) or 0),
                "exam_revenue": float(getattr(row, "exam_revenue", 0) or 0),
            }
    return {
        "total_books": 0,
        "total_courses": 0,
        "book_revenue": 0.0,
        "course_revenue": 0.0,
        "exam_revenue": 0.0,
    }


async def get_por_pais_detail(country: str, filters: PorPaisFilters) -> PorPaisDetailResponse:
    comparison_meta = resolve_comparison_range(filters)
    current_filters = filters.model_copy(
        update={"show_comparison": False, "comparison_date_from": None, "comparison_date_to": None}
    )

    if comparison_meta is None:
        exam_rows, allocated_rows = await asyncio.gather(
            fetch_country_exam_rows(current_filters),
            fetch_country_allocated_revenue_rows(current_filters),
        )
        totals = _extract_country_product_totals(allocated_rows, country)
        return PorPaisDetailResponse(
            country=country,
            exam_counts=build_detail_counts(exam_rows, country),
            **totals,
        )

    comparison_filters = current_filters.model_copy(
        update={"date_from": comparison_meta.date_from, "date_to": comparison_meta.date_to}
    )
    (
        current_exam_rows,
        comparison_exam_rows,
        current_allocated,
        comparison_allocated,
    ) = await asyncio.gather(
        fetch_country_exam_rows(current_filters),
        fetch_country_exam_rows(comparison_filters),
        fetch_country_allocated_revenue_rows(current_filters),
        fetch_country_allocated_revenue_rows(comparison_filters),
    )
    totals = _extract_country_product_totals(current_allocated, country)
    comp_totals = _extract_country_product_totals(comparison_allocated, country)
    return PorPaisDetailResponse(
        country=country,
        exam_counts=build_detail_counts(current_exam_rows, country),
        comparison_exam_counts=build_detail_counts(comparison_exam_rows, country),
        **totals,
        comparison_total_books=comp_totals["total_books"],
        comparison_total_courses=comp_totals["total_courses"],
        comparison_book_revenue=comp_totals["book_revenue"],
        comparison_course_revenue=comp_totals["course_revenue"],
        comparison_exam_revenue=comp_totals["exam_revenue"],
    )


async def get_por_pais_details_for_report(
    report: PorPaisReportResponse,
    filters: PorPaisFilters,
) -> list[PorPaisDetailResponse]:
    if not report.current.summary_rows:
        return []
    return list(
        await asyncio.gather(
            *(get_por_pais_detail(row.country, filters) for row in report.current.summary_rows)
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
        row["total_books"] = detail.total_books
        row["total_courses"] = detail.total_courses
        row["book_revenue"] = detail.book_revenue
        row["course_revenue"] = detail.course_revenue
        detail_rows.append(row)

    specs = [
        ExcelWorksheetSpec(
            name="Por Pais Summary",
            columns=POR_PAIS_SUMMARY_COLUMNS,
            rows=[r.model_dump() for r in report.current.summary_rows],
        ),
        ExcelWorksheetSpec(
            name="Por Pais Detail", columns=POR_PAIS_DETAIL_COLUMNS, rows=detail_rows
        ),
    ]

    if report.comparison:
        specs.append(
            ExcelWorksheetSpec(
                name="Por Pais Status",
                columns=POR_PAIS_STATUS_COLUMNS,
                rows=[r.model_dump() for r in report.current.status_rows],
            )
        )

        comp_by_country = {r.country: r for r in report.comparison.data.summary_rows}

        def _pct(act: float, ant: float) -> float | None:
            return round((act - ant) / ant * 100, 1) if ant else None

        comparison_rows = []
        for r in report.current.summary_rows:
            comp = comp_by_country.get(r.country)
            comparison_rows.append(
                {
                    "country": r.country,
                    "schools_act": r.total_schools,
                    "schools_ant": comp.total_schools if comp else None,
                    "schools_pct": _pct(r.total_schools, comp.total_schools) if comp else None,
                    "revenue_act": r.total_revenue,
                    "revenue_ant": comp.total_revenue if comp else None,
                    "revenue_pct": _pct(r.total_revenue, comp.total_revenue) if comp else None,
                    "uncategorized_act": r.uncategorized_revenue,
                    "uncategorized_ant": comp.uncategorized_revenue if comp else None,
                    "uncategorized_pct": _pct(r.uncategorized_revenue, comp.uncategorized_revenue)
                    if comp
                    else None,
                    "cambridge_act": r.cambridge,
                    "cambridge_ant": comp.cambridge if comp else None,
                    "cambridge_pct": _pct(r.cambridge, comp.cambridge) if comp else None,
                    "ielts_act": r.ielts,
                    "ielts_ant": comp.ielts if comp else None,
                    "ielts_pct": _pct(r.ielts, comp.ielts) if comp else None,
                    "met_act": r.michigan,
                    "met_ant": comp.michigan if comp else None,
                    "met_pct": _pct(r.michigan, comp.michigan) if comp else None,
                    "tea_act": r.tea,
                    "tea_ant": comp.tea if comp else None,
                    "tea_pct": _pct(r.tea, comp.tea) if comp else None,
                    "otros_act": r.other,
                    "otros_ant": comp.other if comp else None,
                    "otros_pct": _pct(r.other, comp.other) if comp else None,
                    "books_act": r.total_books,
                    "books_ant": comp.total_books if comp else None,
                    "books_pct": _pct(r.total_books, comp.total_books) if comp else None,
                    "courses_act": r.total_courses,
                    "courses_ant": comp.total_courses if comp else None,
                    "courses_pct": _pct(r.total_courses, comp.total_courses) if comp else None,
                    "book_rev_act": r.book_revenue,
                    "book_rev_ant": comp.book_revenue if comp else None,
                    "book_rev_pct": _pct(r.book_revenue, comp.book_revenue) if comp else None,
                    "course_rev_act": r.course_revenue,
                    "course_rev_ant": comp.course_revenue if comp else None,
                    "course_rev_pct": _pct(r.course_revenue, comp.course_revenue) if comp else None,
                }
            )
        specs.append(
            ExcelWorksheetSpec(
                name="Comparación",
                columns=[
                    ExcelColumn("country", "País"),
                    ExcelColumn("schools_act", "Colegios (Act.)"),
                    ExcelColumn("schools_ant", "Colegios (Ant.)"),
                    ExcelColumn("schools_pct", "Colegios Δ%"),
                    ExcelColumn("revenue_act", "Ingreso (Act.)"),
                    ExcelColumn("revenue_ant", "Ingreso (Ant.)"),
                    ExcelColumn("revenue_pct", "Ingreso Δ%"),
                    ExcelColumn("uncategorized_act", "Sin Cat. (Act.)"),
                    ExcelColumn("uncategorized_ant", "Sin Cat. (Ant.)"),
                    ExcelColumn("uncategorized_pct", "Sin Cat. Δ%"),
                    ExcelColumn("cambridge_act", "Cambridge (Act.)"),
                    ExcelColumn("cambridge_ant", "Cambridge (Ant.)"),
                    ExcelColumn("cambridge_pct", "Cambridge Δ%"),
                    ExcelColumn("ielts_act", "IELTS (Act.)"),
                    ExcelColumn("ielts_ant", "IELTS (Ant.)"),
                    ExcelColumn("ielts_pct", "IELTS Δ%"),
                    ExcelColumn("met_act", "MET (Act.)"),
                    ExcelColumn("met_ant", "MET (Ant.)"),
                    ExcelColumn("met_pct", "MET Δ%"),
                    ExcelColumn("tea_act", "TEA (Act.)"),
                    ExcelColumn("tea_ant", "TEA (Ant.)"),
                    ExcelColumn("tea_pct", "TEA Δ%"),
                    ExcelColumn("otros_act", "Otros (Act.)"),
                    ExcelColumn("otros_ant", "Otros (Ant.)"),
                    ExcelColumn("otros_pct", "Otros Δ%"),
                    ExcelColumn("books_act", "Libros (Act.)"),
                    ExcelColumn("books_ant", "Libros (Ant.)"),
                    ExcelColumn("books_pct", "Libros Δ%"),
                    ExcelColumn("courses_act", "Cursos (Act.)"),
                    ExcelColumn("courses_ant", "Cursos (Ant.)"),
                    ExcelColumn("courses_pct", "Cursos Δ%"),
                    ExcelColumn("book_rev_act", "Ing. Libros (Act.)"),
                    ExcelColumn("book_rev_ant", "Ing. Libros (Ant.)"),
                    ExcelColumn("book_rev_pct", "Ing. Libros Δ%"),
                    ExcelColumn("course_rev_act", "Ing. Cursos (Act.)"),
                    ExcelColumn("course_rev_ant", "Ing. Cursos (Ant.)"),
                    ExcelColumn("course_rev_pct", "Ing. Cursos Δ%"),
                ],
                rows=comparison_rows,
                note=f"Período comparativo: {report.comparison.meta.date_from} – {report.comparison.meta.date_to}",
            )
        )

    return specs


async def build_por_pais_pdf_payload(
    filters: PorPaisFilters,
    base_currency: BaseCurrency = BaseCurrency.MXN,
) -> PorPaisPDFPayload:
    report = await get_por_pais_report(filters, base_currency=base_currency)
    current = report.current
    has_comparison = report.comparison is not None

    total_schools = sum(r.total_schools for r in current.summary_rows)
    total_revenue = sum(r.total_revenue for r in current.summary_rows)
    total_uncategorized = sum(r.uncategorized_revenue for r in current.summary_rows)
    total_cambridge = sum(r.cambridge for r in current.summary_rows)
    total_ielts = sum(r.ielts for r in current.summary_rows)
    total_met = sum(r.michigan for r in current.summary_rows)
    total_otros = sum(r.tea + r.other for r in current.summary_rows)
    total_books = sum(r.total_books for r in current.summary_rows)
    total_courses = sum(r.total_courses for r in current.summary_rows)

    comp_rows = report.comparison.data.summary_rows if has_comparison else []
    comp_by_country = {r.country: r for r in comp_rows}
    comp_total_schools = sum(r.total_schools for r in comp_rows) if has_comparison else None
    comp_total_revenue = sum(r.total_revenue for r in comp_rows) if has_comparison else None
    comp_total_uncategorized = (
        sum(r.uncategorized_revenue for r in comp_rows) if has_comparison else None
    )
    comp_total_cambridge = sum(r.cambridge for r in comp_rows) if has_comparison else None
    comp_total_ielts = sum(r.ielts for r in comp_rows) if has_comparison else None
    comp_total_met = sum(r.michigan for r in comp_rows) if has_comparison else None
    comp_total_otros = sum(r.tea + r.other for r in comp_rows) if has_comparison else None
    comp_total_books = sum(r.total_books for r in comp_rows) if has_comparison else None
    comp_total_courses = sum(r.total_courses for r in comp_rows) if has_comparison else None

    def _kw(curr: float, prev: float | None, fmt=None) -> dict:
        if prev is None:
            return {}
        g, gp = format_growth(percent_change(curr, prev))
        result: dict = {"growth": g or "N/A", "growth_positive": gp}
        if fmt is not None:
            result["comparison_value"] = fmt(prev)
        return result

    def _fmt_cur(v: float) -> str:
        return format_currency(v, base_currency)

    def _summary_row_deltas(r: PorPaisSummaryRow) -> list:
        comp = comp_by_country.get(r.country)
        if not comp:
            return []

        def fmt_cur(v):
            return format_currency(v, base_currency)

        # Columns: País(0) Colegios(1) Ingreso(2) Sin Cat(3) Cambridge(4) IELTS(5) MET(6) TEA(7) Otros(8) Libros(9) Cursos(10)
        deltas: list = [None] * 11
        deltas[1] = format_delta(r.total_schools, comp.total_schools, format_integer)
        deltas[2] = format_delta(r.total_revenue, comp.total_revenue, fmt_cur)
        deltas[3] = format_delta(r.uncategorized_revenue, comp.uncategorized_revenue, fmt_cur)
        deltas[4] = format_delta(r.cambridge, comp.cambridge, format_integer)
        deltas[5] = format_delta(r.ielts, comp.ielts, format_integer)
        deltas[6] = format_delta(r.michigan, comp.michigan, format_integer)
        deltas[7] = format_delta(r.tea, comp.tea, format_integer)
        deltas[8] = format_delta(r.other, comp.other, format_integer)
        deltas[9] = format_delta(r.total_books, comp.total_books, format_integer)
        deltas[10] = format_delta(r.total_courses, comp.total_courses, format_integer)
        return deltas

    status_table = (
        PDFTable(
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
        )
        if has_comparison
        else None
    )

    return PorPaisPDFPayload(
        header=build_pdf_header(
            "Resultado por País",
            "Resumen por país y estado de colegios/exámenes",
            filters,
            comparison_meta=report.comparison.meta if report.comparison else None,
        ),
        kpis=[
            PDFKpiItem(
                label="Países",
                value=format_integer(len(current.summary_rows)),
                **_kw(
                    len(current.summary_rows),
                    len(comp_rows) if has_comparison else None,
                    format_integer,
                ),
            ),
            PDFKpiItem(
                label="Colegios",
                value=format_integer(total_schools),
                **_kw(total_schools, comp_total_schools, format_integer),
            ),
            PDFKpiItem(
                label="Ingreso Total",
                value=_fmt_cur(total_revenue),
                **_kw(total_revenue, comp_total_revenue, _fmt_cur),
            ),
            PDFKpiItem(
                label="Sin Categorizar",
                value=_fmt_cur(total_uncategorized),
                **_kw(total_uncategorized, comp_total_uncategorized, _fmt_cur),
            ),
            PDFKpiItem(
                label="Cambridge",
                value=format_integer(total_cambridge),
                **_kw(total_cambridge, comp_total_cambridge, format_integer),
            ),
            PDFKpiItem(
                label="IELTS",
                value=format_integer(total_ielts),
                **_kw(total_ielts, comp_total_ielts, format_integer),
            ),
            PDFKpiItem(
                label="MET",
                value=format_integer(total_met),
                **_kw(total_met, comp_total_met, format_integer),
            ),
            PDFKpiItem(
                label="Otros",
                value=format_integer(total_otros),
                **_kw(total_otros, comp_total_otros, format_integer),
            ),
            PDFKpiItem(
                label="Libros",
                value=format_integer(total_books),
                **_kw(total_books, comp_total_books, format_integer),
            ),
            PDFKpiItem(
                label="Cursos",
                value=format_integer(total_courses),
                **_kw(total_courses, comp_total_courses, format_integer),
            ),
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
                "Libros",
                "Cursos",
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
                        format_integer(r.total_books),
                        format_integer(r.total_courses),
                    ],
                    deltas=_summary_row_deltas(r),
                )
                for r in current.summary_rows
            ],
            column_widths=[3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
        ),
        status_table=status_table,
    )


async def build_por_pais_detail_pdf_payload(
    country: str, filters: PorPaisFilters, base_currency: BaseCurrency = BaseCurrency.MXN
) -> PorPaisDetailPDFPayload:
    detail = await get_por_pais_detail(country, filters)
    comp_counts = detail.comparison_exam_counts
    has_comparison = comp_counts is not None

    def _fmt_cur(v: float) -> str:
        return format_currency(v, base_currency)

    def _kw(curr: float, prev: float | None, fmt=None) -> dict:
        if prev is None:
            return {}
        g, gp = format_growth(percent_change(curr, prev))
        result: dict = {"growth": g or "N/A", "growth_positive": gp}
        if fmt is not None:
            result["comparison_value"] = fmt(prev)
        return result

    total_exams = sum(detail.exam_counts.values())
    cambridge_total = sum(
        count
        for name, count in detail.exam_counts.items()
        if name not in {"IELTS", "MET", "MET Go!", "TEA", "Other"}
    )
    other_total = sum(detail.exam_counts.get(n, 0) for n in ("MET", "MET Go!", "TEA", "Other"))

    comp_total_exams = sum(comp_counts.values()) if comp_counts else None
    comp_cambridge = (
        sum(
            v
            for n, v in comp_counts.items()
            if n not in {"IELTS", "MET", "MET Go!", "TEA", "Other"}
        )
        if comp_counts
        else None
    )
    comp_ielts = comp_counts.get("IELTS", 0) if comp_counts else None
    comp_other = (
        sum(comp_counts.get(n, 0) for n in ("MET", "MET Go!", "TEA", "Other"))
        if comp_counts
        else None
    )

    comparison_meta = resolve_comparison_range(filters)

    detail_rows = []
    for name in DETALLE_EXAM_NAME_ORDER:
        count = int(detail.exam_counts.get(name, 0) or 0)
        if count == 0 and (not has_comparison or not comp_counts.get(name)):
            continue
        comp_count = int(comp_counts.get(name, 0) or 0) if comp_counts else None
        delta = format_delta(count, comp_count, format_integer) if comp_count is not None else None
        detail_rows.append(PDFTableRow(cells=[name, format_integer(count)], deltas=[None, delta]))

    # Add Libros and Cursos rows
    for product_label, count, comp_count in [
        ("Libros", detail.total_books, detail.comparison_total_books),
        ("Cursos", detail.total_courses, detail.comparison_total_courses),
    ]:
        if count == 0 and not comp_count:
            continue
        delta = format_delta(count, comp_count, format_integer) if comp_count is not None else None
        detail_rows.append(
            PDFTableRow(cells=[product_label, format_integer(count)], deltas=[None, delta])
        )

    return PorPaisDetailPDFPayload(
        header=build_pdf_header(
            f"Detalle por País - {detail.country}",
            "Desglose por examen para el país seleccionado",
            filters,
            comparison_meta=comparison_meta,
        ),
        kpis=[
            PDFKpiItem(label="País", value=detail.country),
            PDFKpiItem(
                label="Exámenes",
                value=format_integer(total_exams),
                **_kw(total_exams, comp_total_exams),
            ),
            PDFKpiItem(
                label="Cambridge",
                value=format_integer(cambridge_total),
                **_kw(cambridge_total, comp_cambridge),
            ),
            PDFKpiItem(
                label="IELTS",
                value=format_integer(detail.exam_counts.get("IELTS", 0)),
                **_kw(detail.exam_counts.get("IELTS", 0), comp_ielts),
            ),
            PDFKpiItem(
                label="Otros",
                value=format_integer(other_total),
                **_kw(other_total, comp_other),
            ),
            PDFKpiItem(
                label="Libros",
                value=format_integer(detail.total_books),
                **_kw(detail.total_books, detail.comparison_total_books),
            ),
            PDFKpiItem(
                label="Cursos",
                value=format_integer(detail.total_courses),
                **_kw(detail.total_courses, detail.comparison_total_courses),
            ),
            PDFKpiItem(
                label="Ingreso Exámenes",
                value=_fmt_cur(detail.exam_revenue),
                **_kw(detail.exam_revenue, detail.comparison_exam_revenue, _fmt_cur),
            ),
            PDFKpiItem(
                label="Ingreso Libros",
                value=_fmt_cur(detail.book_revenue),
                **_kw(detail.book_revenue, detail.comparison_book_revenue, _fmt_cur),
            ),
            PDFKpiItem(
                label="Ingreso Cursos",
                value=_fmt_cur(detail.course_revenue),
                **_kw(detail.course_revenue, detail.comparison_course_revenue, _fmt_cur),
            ),
        ],
        detail_table=PDFTable(
            headers=["Examen / Producto", "Cantidad"],
            rows=detail_rows,
            column_widths=[4, 2],
        ),
    )
