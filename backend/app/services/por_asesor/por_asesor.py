import asyncio
from collections import defaultdict
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import text

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
from app.services.por_asesor.product_grouping import (
    EXAM_CATEGORY_ORDER,
    canonical_exam_category,
)
from app.services.por_asesor.repository import (
    build_payment_where_clause,
    build_student_payment_where_clause,
    execute_repo_query,
    fetch_school_metric_rows,
    fetch_school_presence_rows,
    fetch_paginated_summary_rows,
    fetch_summary_exam_breakdown_rows_by_seller_ids,
)
from app.services.utils.currency_rates import (
    FALLBACK_EXCHANGE_RATE,
    build_country_rates_derived_table,
    build_country_rates_for_mxn,
)
from app.services.utils.fact_subqueries import build_paid_student_allocation_fact_subquery
from app.services.utils.fact_subqueries import build_deduped_paid_cart_product_fact_subquery
from app.services.utils.report_filters import build_payment_fact_where_clause
from app.database import SessionLocal

ASESOR_SUMMARY_COLUMNS = [
    ExcelColumn("seller_name", "Seller"),
    *[ExcelColumn(category, category) for category in EXAM_CATEGORY_ORDER],
    ExcelColumn("ganados", "Ganados"),
    ExcelColumn("perdidos", "Perdidos"),
    ExcelColumn("mantenidos", "Mantenidos"),
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
    ExcelColumn("total_revenue", "Total Revenue"),
]
for category in EXAM_CATEGORY_ORDER:
    ASESOR_DETAIL_COLUMNS.extend(
        [
            ExcelColumn(f"{category}_exams", f"{category} Exams"),
            ExcelColumn(f"{category}_schools", f"{category} Schools"),
            ExcelColumn(f"{category}_revenue", f"{category} Revenue"),
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


async def execute_query(query: str, params: dict, expanding_keys: list[str]):
    return await execute_repo_query(query, params, expanding_keys)


async def fetch_seller_name(seller_id: int) -> str | None:
    async with SessionLocal() as session:
        result = await session.execute(
            text("SELECT CONCAT(name, ' ', lastName) AS seller_name FROM seller WHERE id = :seller_id"),
            {"seller_id": seller_id},
        )
        row = result.fetchone()
        return row.seller_name if row else None


async def fetch_detail_aggregate_row(
    payment_where_clause: str,
    payment_params: dict,
    payment_expanding_keys: list[str],
    breakdown_where_clause: str,
    breakdown_params: dict,
    breakdown_expanding_keys: list[str],
    country_rates: dict[str, float],
):
    fx_table_sql, fx_params = build_country_rates_derived_table(country_rates)
    payment_query = f"""
        SELECT
            COUNT(DISTINCT qp.lead_id) AS total_schools,
            COALESCE(SUM(qp.paid_amount_base), 0) AS total_revenue
        FROM (
            SELECT *
            FROM (
                SELECT
                    pay.id AS payment_id,
                    pay.quantity AS paid_amount,
                    pay.quantity * COALESCE(fx.rate_to_base, :fallback_rate) AS paid_amount_base,
                    CONCAT(s.name, ' ', s.lastName) AS seller_name,
                    s.id AS seller_id,
                    l.id AS lead_id
                FROM payment pay
                JOIN cart c ON c.id = pay.cartId
                JOIN seller_lead sl ON sl.id = c.sellerLeadId
                JOIN seller s ON s.id = sl.sellerId
                JOIN `lead` l ON l.id = sl.leadId
                LEFT JOIN zone z ON z.id = l.zoneId
                LEFT JOIN ({fx_table_sql}) fx ON
                    LOWER(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(l.site, ''), 'á', 'a'), 'é', 'e'), 'í', 'i'), 'ó', 'o'), 'ú', 'u'), 'ñ', 'n'))) = fx.country_key
                WHERE {payment_where_clause}
            ) qp_inner
            WHERE qp_inner.seller_id = :seller_id
        ) qp
    """
    paid_allocation_fact = build_paid_student_allocation_fact_subquery(breakdown_where_clause, fx_table_sql=fx_table_sql)
    paid_cart_product_fact = build_deduped_paid_cart_product_fact_subquery(paid_allocation_fact)
    exams_query = f"""
        SELECT COALESCE(SUM(paid_cart_products.exam_count), 0) AS total_exams
        FROM (
            SELECT DISTINCT
                pcp.cart_product_id,
                pcp.cart_product_quantity AS exam_count
            FROM ({paid_cart_product_fact}) pcp
            WHERE pcp.seller_id = :seller_id
        ) paid_cart_products
    """
    payment_rows = await execute_query(
        payment_query,
        {**payment_params, **fx_params, "fallback_rate": FALLBACK_EXCHANGE_RATE},
        payment_expanding_keys,
    )
    exam_rows = await execute_query(
        exams_query,
        {**breakdown_params, **fx_params, "fallback_rate": FALLBACK_EXCHANGE_RATE},
        breakdown_expanding_keys,
    )
    payment_row = payment_rows[0] if payment_rows else None
    exam_row = exam_rows[0] if exam_rows else None
    return SimpleNamespace(
        total_schools=int((payment_row.total_schools if payment_row else 0) or 0),
        total_revenue=float((payment_row.total_revenue if payment_row else 0) or 0),
        total_exams=int((exam_row.total_exams if exam_row else 0) or 0),
    )


async def fetch_detail_geo_rows(
    payment_where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    query = f"""
        SELECT DISTINCT
            l.site AS country,
            z.name AS zone,
            la.stateName AS state,
            la.city AS city
        FROM seller_lead sl
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        LEFT JOIN (SELECT DISTINCT leadId, stateName, city FROM lead_address) la ON la.leadId = l.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN payment pay ON pay.cartId = c.id
        WHERE sl.sellerId = :seller_id AND {payment_where_clause}
    """
    return await execute_query(query, params, expanding_keys)


async def fetch_detail_exam_breakdown_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
    country_rates: dict[str, float],
):
    fx_table_sql, fx_params = build_country_rates_derived_table(country_rates)
    paid_allocation_fact = build_paid_student_allocation_fact_subquery(where_clause, fx_table_sql=fx_table_sql)
    paid_cart_product_fact = build_deduped_paid_cart_product_fact_subquery(paid_allocation_fact)
    query = f"""
        SELECT
            pcp.exam_name,
            COALESCE(SUM(pcp.exams), 0) AS exams,
            COUNT(DISTINCT pcp.lead_id) AS schools,
            COALESCE(MAX(ar.revenue), 0) AS revenue,
            GROUP_CONCAT(DISTINCT pcp.lead_id ORDER BY pcp.lead_id SEPARATOR ',') AS lead_ids
        FROM (
            SELECT DISTINCT
                pcp.cart_product_id,
                pcp.exam_name,
                pcp.cart_product_quantity AS exams,
                pcp.lead_id
            FROM ({paid_cart_product_fact}) pcp
            WHERE pcp.seller_id = :seller_id
        ) pcp
        LEFT JOIN (
            SELECT
                qsp.exam_name,
                COALESCE(SUM(qsp.allocated_amount_base), 0) AS revenue
            FROM ({paid_allocation_fact}) qsp
            WHERE qsp.seller_id = :seller_id
            GROUP BY qsp.exam_name
        ) ar ON ar.exam_name = pcp.exam_name
        GROUP BY pcp.exam_name
    """
    return await execute_query(
        query,
        {**params, **fx_params, "fallback_rate": FALLBACK_EXCHANGE_RATE},
        expanding_keys,
    )


async def fetch_detail_status_rows(
    seller_id: int,
    filters: AsesorFilters,
    country_rates: dict[str, float],
):
    presence_where_clause, presence_params, expanding_keys = build_presence_filters(filters, seller_id=seller_id)
    current_rows, prior_rows, current_metric_rows, prior_metric_rows = await asyncio.gather(
        fetch_school_presence_rows(presence_where_clause, presence_params, expanding_keys, filters.year),
        fetch_school_presence_rows(presence_where_clause, presence_params, expanding_keys, filters.year - 1),
        fetch_school_metric_rows(presence_where_clause, presence_params, expanding_keys, filters.year, country_rates),
        fetch_school_metric_rows(presence_where_clause, presence_params, expanding_keys, filters.year - 1, country_rates),
    )
    return build_status_map_from_year_sets(current_rows, prior_rows, current_metric_rows, prior_metric_rows)


def empty_status() -> BusinessStatusDetail:
    return BusinessStatusDetail(schools=0, exams=0, revenue=0.0)


def empty_detail_breakdown() -> dict[str, int]:
    return {category: 0 for category in EXAM_CATEGORY_ORDER}


def fill_summary_exam_categories(breakdown: dict[str, int]) -> dict[str, int]:
    return {category: int(breakdown.get(category, 0) or 0) for category in EXAM_CATEGORY_ORDER}


def normalize_summary_exam_breakdowns(exam_breakdowns: dict[int, dict[str, int]]) -> dict[int, dict[str, int]]:
    normalized: dict[int, dict[str, int]] = {}
    for seller_id, breakdown in exam_breakdowns.items():
        grouped: dict[str, int] = {category: 0 for category in EXAM_CATEGORY_ORDER}
        for label, count in breakdown.items():
            category = canonical_exam_category(label)
            grouped[category] = grouped.get(category, 0) + int(count or 0)
        normalized[seller_id] = fill_summary_exam_categories(grouped)
    return normalized


def normalize_detail_exam_breakdown(
    breakdown: dict[str, ExamBrandDetail],
    school_id_map: dict[str, set[int]] | None = None,
) -> dict[str, ExamBrandDetail]:
    grouped: dict[str, ExamBrandDetail] = {
        category: ExamBrandDetail(exams=0, schools=0, revenue=0.0)
        for category in EXAM_CATEGORY_ORDER
    }
    schools_by_category: dict[str, set[int]] = {category: set() for category in EXAM_CATEGORY_ORDER}

    for label, detail in breakdown.items():
        category = canonical_exam_category(label)
        current = grouped[category]
        grouped[category] = ExamBrandDetail(
            exams=current.exams + int(detail.exams or 0),
            schools=current.schools + int(detail.schools or 0),
            revenue=current.revenue + float(detail.revenue or 0),
        )
        if school_id_map is not None:
            schools_by_category[category].update(school_id_map.get(label, set()))

    if school_id_map is not None:
        for category in EXAM_CATEGORY_ORDER:
            current = grouped[category]
            grouped[category] = ExamBrandDetail(
                exams=current.exams,
                schools=len(schools_by_category[category]),
                revenue=current.revenue,
            )

    return grouped


def map_summary_exam_breakdowns(rows) -> dict[int, dict[str, int]]:
    exam_breakdowns: dict[int, dict[str, int]] = {}
    for row in rows:
        seller_breakdown = exam_breakdowns.setdefault(row.seller_id, {})
        seller_breakdown[row.exam_name] = seller_breakdown.get(row.exam_name, 0) + int(row.exam_count or 0)
    return normalize_summary_exam_breakdowns(exam_breakdowns)


def map_detail_exam_breakdown(rows) -> dict[str, ExamBrandDetail]:
    breakdown: dict[str, ExamBrandDetail] = {}
    school_id_map: dict[str, set[int]] = {}
    for row in rows:
        breakdown[row.exam_name] = ExamBrandDetail(
            exams=breakdown.get(row.exam_name, ExamBrandDetail(exams=0, schools=0, revenue=0.0)).exams + int(row.exams or 0),
            schools=breakdown.get(row.exam_name, ExamBrandDetail(exams=0, schools=0, revenue=0.0)).schools + int(row.schools or 0),
            revenue=breakdown.get(row.exam_name, ExamBrandDetail(exams=0, schools=0, revenue=0.0)).revenue + float(row.revenue or 0),
        )
        school_id_map.setdefault(row.exam_name, set()).update(parse_grouped_ids(row.lead_ids))
    return normalize_detail_exam_breakdown(breakdown, school_id_map)


def map_status_rows(rows) -> dict[str, BusinessStatusDetail]:
    return rows


def unique_sorted_values(rows, field: str) -> list[str]:
    values = {getattr(row, field) for row in rows if getattr(row, field)}
    return sorted(values)


def parse_grouped_ids(value: str | None) -> set[int]:
    if not value:
        return set()
    return {int(item) for item in value.split(",") if item}


def build_asesor_report_response(
    summary_rows,
    exam_breakdowns: dict[int, dict[str, int]],
    status_counts: dict[int, dict[str, int]],
    year: int,
    next_cursor: str | None,
    has_more: bool,
) -> AsesorReportResponse:
    rows = [
        AsesorRow(
            seller_id=row.seller_id,
            seller_name=row.seller_name,
            exam_breakdown=exam_breakdowns.get(row.seller_id, {}),
            ganados=int(status_counts.get(row.seller_id, {}).get("ganado", 0)),
            perdidos=int(status_counts.get(row.seller_id, {}).get("perdido", 0)),
            mantenidos=int(status_counts.get(row.seller_id, {}).get("mantenido", 0)),
            total_revenue=float(row.total_revenue or 0),
        )
        for row in summary_rows
    ]
    return AsesorReportResponse(rows=rows, year=year, next_cursor=next_cursor, has_more=has_more)


def build_asesor_detail_response(
    seller_name: str,
    aggregate_row,
    geo_rows,
    exam_breakdown: dict[str, ExamBrandDetail],
    status_map: dict[str, BusinessStatusDetail],
) -> AsesorDetail:
    has_any_detail_rows = bool(aggregate_row and any(
        [
            int((aggregate_row.total_schools if aggregate_row else 0) or 0),
            int((aggregate_row.total_exams if aggregate_row else 0) or 0),
            float((aggregate_row.total_revenue if aggregate_row else 0) or 0),
        ]
    ))
    return AsesorDetail(
        seller_name=seller_name,
        countries=unique_sorted_values(geo_rows, "country"),
        zones=unique_sorted_values(geo_rows, "zone"),
        states=unique_sorted_values(geo_rows, "state"),
        cities=unique_sorted_values(geo_rows, "city"),
        total_schools=int((aggregate_row.total_schools if aggregate_row else 0) or 0),
        total_exams=int((aggregate_row.total_exams if aggregate_row else 0) or 0),
        total_revenue=float((aggregate_row.total_revenue if aggregate_row else 0) or 0),
        exam_breakdown=exam_breakdown if has_any_detail_rows else empty_detail_breakdown(),
        ganados=status_map.get("ganado", empty_status()),
        perdidos=status_map.get("perdido", empty_status()),
        mantenidos=status_map.get("mantenido", empty_status()),
    )


async def getAsesorReport(
    filters: AsesorFilters,
    country_rates: dict[str, float] | None = None,
) -> AsesorReportResponse:
    effective_rates = country_rates or build_country_rates_for_mxn(None, identity_fallback=True)
    payment_where_clause, payment_params, payment_expanding_keys = build_payment_where_clause(
        filters, include_sellers=True
    )
    summary_rows, has_more, next_cursor = await fetch_paginated_summary_rows(
        payment_where_clause,
        payment_params,
        payment_expanding_keys,
        limit=filters.limit,
        cursor=filters.cursor,
        country_rates=effective_rates,
    )
    seller_ids = [int(row.seller_id) for row in summary_rows]
    breakdown_where_clause, breakdown_params, breakdown_expanding_keys = build_student_payment_where_clause(
        filters, include_sellers=True
    )
    breakdown_rows = await fetch_summary_exam_breakdown_rows_by_seller_ids(
        breakdown_where_clause,
        breakdown_params,
        breakdown_expanding_keys,
        seller_ids,
    )
    exam_breakdowns = map_summary_exam_breakdowns(breakdown_rows)
    status_counts = await fetch_summary_status_counts(filters, seller_ids)
    return build_asesor_report_response(summary_rows, exam_breakdowns, status_counts, filters.year, next_cursor, has_more)


async def getAsesorDetail(
    seller_id: int,
    filters: AsesorFilters,
    country_rates: dict[str, float] | None = None,
) -> AsesorDetail:
    effective_rates = country_rates or build_country_rates_for_mxn(None, identity_fallback=True)
    seller_name = await fetch_seller_name(seller_id)
    if seller_name is None:
        raise HTTPException(status_code=404, detail="Seller not found")

    payment_where_clause, payment_params, payment_expanding_keys = build_payment_where_clause(filters)
    breakdown_where_clause, breakdown_params, breakdown_expanding_keys = build_student_payment_where_clause(filters)
    detail_payment_params = {**payment_params, "seller_id": seller_id}
    detail_breakdown_params = {**breakdown_params, "seller_id": seller_id}
    aggregate_row, geo_rows, breakdown_rows, status_rows = await asyncio.gather(
        fetch_detail_aggregate_row(
            payment_where_clause,
            detail_payment_params,
            payment_expanding_keys,
            breakdown_where_clause,
            detail_breakdown_params,
            breakdown_expanding_keys,
            effective_rates,
        ),
        fetch_detail_geo_rows(payment_where_clause, detail_payment_params, payment_expanding_keys),
        fetch_detail_exam_breakdown_rows(
            breakdown_where_clause,
            detail_breakdown_params,
            breakdown_expanding_keys,
            effective_rates,
        ),
        fetch_detail_status_rows(seller_id, filters, effective_rates),
    )
    exam_breakdown = map_detail_exam_breakdown(breakdown_rows)
    status_map = map_status_rows(status_rows)
    return build_asesor_detail_response(seller_name, aggregate_row, geo_rows, exam_breakdown, status_map)


def build_presence_filters(filters: AsesorFilters, seller_id: int | None = None) -> tuple[str, dict[str, object], list[str]]:
    where_clause, params, expanding_keys = build_payment_fact_where_clause(
        filters,
        include_date_range=False,
    )
    conditions = [where_clause]
    if filters.sellers:
        conditions.append("CONCAT(s.name, ' ', s.lastName) IN :sellers")
        params["sellers"] = list(filters.sellers)
        expanding_keys.append("sellers")
    if seller_id is not None:
        conditions.append("s.id = :seller_id")
        params["seller_id"] = seller_id
    return " AND ".join(conditions), params, expanding_keys


def build_status_map_from_year_sets(current_rows, prior_rows, current_metric_rows, prior_metric_rows):
    current_by_seller: dict[int, set[int]] = defaultdict(set)
    prior_by_seller: dict[int, set[int]] = defaultdict(set)
    current_metrics: dict[tuple[int, int], tuple[int, float]] = {}
    prior_metrics: dict[tuple[int, int], tuple[int, float]] = {}

    for row in current_rows:
        current_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in prior_rows:
        prior_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in current_metric_rows:
        current_metrics[(int(row.seller_id), int(row.lead_id))] = (int(row.exams or 0), float(row.revenue or 0))
    for row in prior_metric_rows:
        prior_metrics[(int(row.seller_id), int(row.lead_id))] = (int(row.exams or 0), float(row.revenue or 0))

    seller_ids = set(current_by_seller) | set(prior_by_seller)
    status_map: dict[int, dict[str, BusinessStatusDetail]] = {}
    for seller_id in seller_ids:
        current = current_by_seller.get(seller_id, set())
        prior = prior_by_seller.get(seller_id, set())
        buckets = {
            "ganado": current - prior,
            "perdido": prior - current,
            "mantenido": current & prior,
        }
        seller_statuses: dict[str, BusinessStatusDetail] = {}
        for status, lead_ids in buckets.items():
            metric_source = prior_metrics if status == "perdido" else current_metrics
            exams = sum(metric_source.get((seller_id, lead_id), (0, 0.0))[0] for lead_id in lead_ids)
            revenue = sum(metric_source.get((seller_id, lead_id), (0, 0.0))[1] for lead_id in lead_ids)
            seller_statuses[status] = BusinessStatusDetail(schools=len(lead_ids), exams=exams, revenue=revenue)
        status_map[seller_id] = seller_statuses
    if len(status_map) == 1:
        return next(iter(status_map.values()))
    return status_map


async def fetch_summary_status_counts(filters: AsesorFilters, seller_ids: list[int]) -> dict[int, dict[str, int]]:
    if not seller_ids:
        return {}
    filtered = AsesorFilters(
        year=filters.year,
        countries=filters.countries,
        zones=filters.zones,
        states=filters.states,
        cities=filters.cities,
        sellers=filters.sellers,
    )
    where_clause, params, expanding_keys = build_presence_filters(filtered)
    current_rows, prior_rows = await asyncio.gather(
        fetch_school_presence_rows(where_clause, params, expanding_keys, filters.year),
        fetch_school_presence_rows(where_clause, params, expanding_keys, filters.year - 1),
    )
    current_by_seller: dict[int, set[int]] = defaultdict(set)
    prior_by_seller: dict[int, set[int]] = defaultdict(set)
    for row in current_rows:
        current_by_seller[int(row.seller_id)].add(int(row.lead_id))
    for row in prior_rows:
        prior_by_seller[int(row.seller_id)].add(int(row.lead_id))
    status_counts: dict[int, dict[str, int]] = {}
    for seller_id in seller_ids:
        current = current_by_seller.get(seller_id, set())
        prior = prior_by_seller.get(seller_id, set())
        status_counts[seller_id] = {
            "ganado": len(current - prior),
            "perdido": len(prior - current),
            "mantenido": len(current & prior),
        }
    return status_counts


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


async def getAllAsesorReportRows(
    filters: AsesorFilters,
    country_rates: dict[str, float] | None = None,
) -> AsesorReportResponse:
    all_rows: list[AsesorRow] = []
    cursor = filters.cursor
    has_more = False
    effective_rates = country_rates or build_country_rates_for_mxn(None, identity_fallback=True)

    while True:
        page = await getAsesorReport(filters.model_copy(update={"cursor": cursor}), country_rates=effective_rates)
        all_rows.extend(page.rows)
        if not page.has_more or page.next_cursor is None:
            has_more = False
            break
        cursor = page.next_cursor

    return AsesorReportResponse(
        rows=all_rows,
        year=filters.year,
        next_cursor=None,
        has_more=has_more,
    )


async def getAsesorDetailsForRows(
    rows: list[AsesorRow],
    filters: AsesorFilters,
    country_rates: dict[str, float] | None = None,
) -> list[AsesorDetail]:
    if not rows:
        return []
    effective_rates = country_rates or build_country_rates_for_mxn(None, identity_fallback=True)
    return list(await asyncio.gather(*(getAsesorDetail(row.seller_id, filters, country_rates=effective_rates) for row in rows)))


def build_asesor_export_worksheets(
    report: AsesorReportResponse,
    details: list[AsesorDetail],
) -> list[ExcelWorksheetSpec]:
    summary_rows = []
    for row in report.rows:
        summary_row = {
            "seller_name": row.seller_name,
            "ganados": row.ganados,
            "perdidos": row.perdidos,
            "mantenidos": row.mantenidos,
            "total_revenue": row.total_revenue,
        }
        for category in EXAM_CATEGORY_ORDER:
            summary_row[category] = int(row.exam_breakdown.get(category, 0) or 0)
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
        for category in EXAM_CATEGORY_ORDER:
            category_detail = detail.exam_breakdown.get(category)
            if isinstance(category_detail, ExamBrandDetail):
                detail_row[f"{category}_exams"] = category_detail.exams
                detail_row[f"{category}_schools"] = category_detail.schools
                detail_row[f"{category}_revenue"] = category_detail.revenue
            else:
                detail_row[f"{category}_exams"] = int(category_detail or 0)
                detail_row[f"{category}_schools"] = 0
                detail_row[f"{category}_revenue"] = 0.0
        detail_rows.append(detail_row)

    return [
        ExcelWorksheetSpec(
            name="Por Asesor",
            columns=ASESOR_SUMMARY_COLUMNS,
            rows=summary_rows,
        ),
        ExcelWorksheetSpec(
            name="Por Asesor Detail",
            columns=ASESOR_DETAIL_COLUMNS,
            rows=detail_rows,
        ),
    ]


async def build_por_asesor_pdf_payload(
    filters: AsesorFilters,
    country_rates: dict[str, float] | None = None,
) -> PorAsesorPDFPayload:
    report = await getAllAsesorReportRows(build_asesor_export_filters_for_all(filters), country_rates=country_rates)

    total_revenue = sum(row.total_revenue for row in report.rows)
    total_exams = sum(sum(row.exam_breakdown.values()) for row in report.rows)
    total_ganados = sum(row.ganados for row in report.rows)
    total_perdidos = sum(row.perdidos for row in report.rows)
    total_mantenidos = sum(row.mantenidos for row in report.rows)

    table_rows = []
    for row in report.rows:
        cambridge = (
            int(row.exam_breakdown.get("Cambridge English (Main Suite)", 0) or 0)
            + int(row.exam_breakdown.get("Cambridge Teaching & Skills", 0) or 0)
        )
        ielts = int(row.exam_breakdown.get("IELTS", 0) or 0)
        met = int(row.exam_breakdown.get("Michigan (MET)", 0) or 0)
        otros = (
            int(row.exam_breakdown.get("TEA (Test of English for Aviation)", 0) or 0)
            + int(row.exam_breakdown.get("Placement & Otros", 0) or 0)
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
                    format_currency(row.total_revenue),
                ]
            )
        )

    return PorAsesorPDFPayload(
        header=build_pdf_header(
            f"Resultados por Asesor - {filters.year}",
            "Resumen por asesor con familias de exámenes y valor total",
            filters,
        ),
        kpis=[
            PDFKpiItem(label="Asesores", value=format_integer(len(report.rows))),
            PDFKpiItem(label="Exámenes", value=format_integer(total_exams)),
            PDFKpiItem(label="Ganados", value=format_integer(total_ganados)),
            PDFKpiItem(label="Perdidos", value=format_integer(total_perdidos)),
            PDFKpiItem(label="Mantenidos", value=format_integer(total_mantenidos)),
            PDFKpiItem(label="Valor Total", value=format_currency(total_revenue)),
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
                "Valor Total",
            ],
            rows=table_rows,
            column_widths=[4, 2, 2, 2, 2, 2, 2, 2, 3],
        ),
    )


async def build_asesor_detail_pdf_payload(
    seller_id: int,
    filters: AsesorFilters,
    country_rates: dict[str, float] | None = None,
) -> AsesorDetailPDFPayload:
    detail = await getAsesorDetail(seller_id, filters, country_rates=country_rates)

    category_rows = []
    for category in EXAM_CATEGORY_ORDER:
        category_detail = detail.exam_breakdown.get(category)
        if isinstance(category_detail, ExamBrandDetail):
            exams = category_detail.exams
            schools = category_detail.schools
            revenue = category_detail.revenue
        else:
            exams = int(category_detail or 0)
            schools = 0
            revenue = 0.0
        category_rows.append(
            PDFTableRow(
                cells=[
                    category,
                    format_integer(exams),
                    format_integer(schools),
                    format_currency(revenue),
                ]
            )
        )

    status_rows = [
        PDFTableRow(
            cells=[
                "Ganados",
                format_integer(detail.ganados.schools),
                format_integer(detail.ganados.exams),
                format_currency(detail.ganados.revenue),
            ]
        ),
        PDFTableRow(
            cells=[
                "Perdidos",
                format_integer(detail.perdidos.schools),
                format_integer(detail.perdidos.exams),
                format_currency(detail.perdidos.revenue),
            ]
        ),
        PDFTableRow(
            cells=[
                "Mantenidos",
                format_integer(detail.mantenidos.schools),
                format_integer(detail.mantenidos.exams),
                format_currency(detail.mantenidos.revenue),
            ]
        ),
    ]

    return AsesorDetailPDFPayload(
        header=build_pdf_header(
            detail.seller_name,
            "Detalle del asesor por geografía, categorías y estado de colegios",
            filters,
        ),
        kpis=[
            PDFKpiItem(label="Total Colegios", value=format_integer(detail.total_schools)),
            PDFKpiItem(label="Total Exámenes", value=format_integer(detail.total_exams)),
            PDFKpiItem(label="Valor Total", value=format_currency(detail.total_revenue)),
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
