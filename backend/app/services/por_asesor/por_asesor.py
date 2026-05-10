import asyncio
from collections import defaultdict
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import text

from app.enums import PaymentStatus
from app.schemas.reports import (
    AsesorDetail,
    AsesorFilters,
    AsesorReportResponse,
    AsesorRow,
    BusinessStatusDetail,
    ExamBrandDetail,
)
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
from app.services.utils.fact_subqueries import build_paid_student_allocation_fact_subquery
from app.services.utils.fact_subqueries import build_deduped_paid_cart_product_fact_subquery
from app.services.utils.report_filters import build_payment_fact_where_clause
from app.database import SessionLocal


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
):
    payment_query = f"""
        SELECT
            COUNT(DISTINCT l.id) AS total_schools,
            COALESCE(SUM(pay.quantity), 0) AS total_revenue
        FROM seller_lead sl
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN payment pay ON pay.cartId = c.id
        WHERE sl.sellerId = :seller_id AND {payment_where_clause}
    """
    paid_allocation_fact = build_paid_student_allocation_fact_subquery(breakdown_where_clause)
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
    payment_rows = await execute_query(payment_query, payment_params, payment_expanding_keys)
    exam_rows = await execute_query(exams_query, breakdown_params, breakdown_expanding_keys)
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
):
    paid_allocation_fact = build_paid_student_allocation_fact_subquery(where_clause)
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
                COALESCE(SUM(qsp.allocated_amount), 0) AS revenue
            FROM ({paid_allocation_fact}) qsp
            WHERE qsp.seller_id = :seller_id
            GROUP BY qsp.exam_name
        ) ar ON ar.exam_name = pcp.exam_name
        GROUP BY pcp.exam_name
    """
    return await execute_query(query, params, expanding_keys)


async def fetch_detail_status_rows(
    seller_id: int,
    filters: AsesorFilters,
):
    presence_where_clause, presence_params, expanding_keys = build_presence_filters(filters, seller_id=seller_id)
    current_rows, prior_rows, current_metric_rows, prior_metric_rows = await asyncio.gather(
        fetch_school_presence_rows(presence_where_clause, presence_params, expanding_keys, filters.year),
        fetch_school_presence_rows(presence_where_clause, presence_params, expanding_keys, filters.year - 1),
        fetch_school_metric_rows(presence_where_clause, presence_params, expanding_keys, filters.year),
        fetch_school_metric_rows(presence_where_clause, presence_params, expanding_keys, filters.year - 1),
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


async def getAsesorReport(filters: AsesorFilters) -> AsesorReportResponse:
    payment_where_clause, payment_params, payment_expanding_keys = build_payment_where_clause(
        filters, include_sellers=True
    )
    summary_rows, has_more, next_cursor = await fetch_paginated_summary_rows(
        payment_where_clause,
        payment_params,
        payment_expanding_keys,
        limit=filters.limit,
        cursor=filters.cursor,
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


async def getAsesorDetail(seller_id: int, filters: AsesorFilters) -> AsesorDetail:
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
        ),
        fetch_detail_geo_rows(payment_where_clause, detail_payment_params, payment_expanding_keys),
        fetch_detail_exam_breakdown_rows(
            breakdown_where_clause,
            detail_breakdown_params,
            breakdown_expanding_keys,
        ),
        fetch_detail_status_rows(seller_id, filters),
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
