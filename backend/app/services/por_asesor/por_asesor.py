import asyncio
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import text

from app.schemas.reports import (
    AsesorDetail,
    AsesorFilters,
    AsesorReportResponse,
    AsesorRow,
    BusinessStatusDetail,
    ExamBrandDetail,
)
from app.services.por_asesor.product_grouping import (
    build_exam_label_groups,
    choose_canonical_exam_label,
)
from app.services.por_asesor.repository import (
    execute_repo_query,
    fetch_paginated_summary_rows,
    fetch_summary_exam_breakdown_rows_by_seller_ids,
)
from app.database import SessionLocal


def build_common_filters(filters: AsesorFilters, include_sellers: bool = False) -> tuple[str, dict, list[str]]:
    conditions = [
        "c.deletedAt IS NULL",
        "cp.deletedAt IS NULL",
        "sl.deletedAt IS NULL",
        "l.deletedAt IS NULL",
        "YEAR(c.createdAt) = :year",
    ]
    params: dict[str, object] = {"year": filters.year}
    expanding_keys: list[str] = []

    def add_expanding_condition(field: str, values: Sequence[str], sql: str) -> None:
        if values:
            conditions.append(sql)
            params[field] = list(values)
            expanding_keys.append(field)

    add_expanding_condition("countries", filters.countries, "l.site IN :countries")
    add_expanding_condition("zones", filters.zones, "z.name IN :zones")
    add_expanding_condition(
        "states",
        filters.states,
        """
        EXISTS (
            SELECT 1
            FROM lead_address la_filter
            WHERE la_filter.leadId = l.id
              AND la_filter.deletedAt IS NULL
              AND la_filter.stateName IN :states
        )
        """.strip(),
    )
    add_expanding_condition(
        "cities",
        filters.cities,
        """
        EXISTS (
            SELECT 1
            FROM lead_address la_filter
            WHERE la_filter.leadId = l.id
              AND la_filter.deletedAt IS NULL
              AND la_filter.city IN :cities
        )
        """.strip(),
    )
    if include_sellers:
        add_expanding_condition(
            "sellers",
            filters.sellers,
            "CONCAT(s.name, ' ', s.lastName) IN :sellers",
        )

    return " AND ".join(conditions), params, expanding_keys


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
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    query = f"""
        SELECT
            COUNT(DISTINCT l.id) AS total_schools,
            COALESCE(SUM(cp.quantity), 0) AS total_exams,
            COALESCE(SUM(cp.total), 0) AS total_revenue
        FROM seller_lead sl
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        WHERE sl.sellerId = :seller_id AND {where_clause}
    """
    rows = await execute_query(query, params, expanding_keys)
    return rows[0] if rows else None


async def fetch_detail_geo_rows(
    where_clause: str,
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
        LEFT JOIN lead_address la ON la.leadId = l.id AND la.deletedAt IS NULL
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        WHERE sl.sellerId = :seller_id AND {where_clause}
    """
    return await execute_query(query, params, expanding_keys)


async def fetch_detail_exam_breakdown_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    query = f"""
        SELECT
            ec.name AS exam_name,
            COALESCE(SUM(cp.quantity), 0) AS exams,
            COUNT(DISTINCT l.id) AS schools,
            COALESCE(SUM(cp.total), 0) AS revenue,
            GROUP_CONCAT(DISTINCT l.id ORDER BY l.id SEPARATOR ',') AS lead_ids
        FROM seller_lead sl
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        JOIN exam_cat ec ON p.examId = ec.id
        WHERE sl.sellerId = :seller_id AND {where_clause}
        GROUP BY ec.name
    """
    return await execute_query(query, params, expanding_keys)


async def fetch_detail_status_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    query = f"""
        SELECT
            sl.businessStatus AS business_status,
            COUNT(DISTINCT l.id) AS schools,
            COALESCE(SUM(cp.quantity), 0) AS exams,
            COALESCE(SUM(cp.total), 0) AS revenue
        FROM seller_lead sl
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        WHERE sl.sellerId = :seller_id AND {where_clause}
        GROUP BY sl.businessStatus
    """
    return await execute_query(query, params, expanding_keys)


def empty_status() -> BusinessStatusDetail:
    return BusinessStatusDetail(schools=0, exams=0, revenue=0.0)


def normalize_summary_exam_breakdowns(exam_breakdowns: dict[int, dict[str, int]]) -> dict[int, dict[str, int]]:
    normalized: dict[int, dict[str, int]] = {}
    for seller_id, breakdown in exam_breakdowns.items():
        grouped: dict[str, int] = {}
        for labels in build_exam_label_groups(list(breakdown.keys())):
            canonical_label = choose_canonical_exam_label(labels)
            grouped[canonical_label] = sum(breakdown[label] for label in labels)
        normalized[seller_id] = grouped
    return normalized


def normalize_detail_exam_breakdown(
    breakdown: dict[str, ExamBrandDetail],
    school_id_map: dict[str, set[int]] | None = None,
) -> dict[str, ExamBrandDetail]:
    grouped: dict[str, ExamBrandDetail] = {}
    for labels in build_exam_label_groups(list(breakdown.keys())):
        canonical_label = choose_canonical_exam_label(labels)
        schools = (
            len(set().union(*(school_id_map.get(label, set()) for label in labels)))
            if school_id_map is not None
            else sum(breakdown[label].schools for label in labels)
        )
        grouped[canonical_label] = ExamBrandDetail(
            exams=sum(breakdown[label].exams for label in labels),
            schools=schools,
            revenue=sum(breakdown[label].revenue for label in labels),
        )
    return grouped


def map_summary_exam_breakdowns(rows) -> dict[int, dict[str, int]]:
    exam_breakdowns: dict[int, dict[str, int]] = {}
    for row in rows:
        seller_breakdown = exam_breakdowns.setdefault(row.seller_id, {})
        seller_breakdown[row.exam_name] = seller_breakdown.get(row.exam_name, 0) + int(row.exam_count or 0)
    return normalize_summary_exam_breakdowns(exam_breakdowns)


def map_detail_exam_breakdown(rows) -> dict[str, ExamBrandDetail]:
    breakdown = {
        row.exam_name: ExamBrandDetail(
            exams=int(row.exams or 0),
            schools=int(row.schools or 0),
            revenue=float(row.revenue or 0),
        )
        for row in rows
    }
    school_id_map = {
        row.exam_name: parse_grouped_ids(row.lead_ids)
        for row in rows
    }
    return normalize_detail_exam_breakdown(breakdown, school_id_map)


def map_status_rows(rows) -> dict[str, BusinessStatusDetail]:
    return {
        row.business_status: BusinessStatusDetail(
            schools=int(row.schools or 0),
            exams=int(row.exams or 0),
            revenue=float(row.revenue or 0),
        )
        for row in rows
    }


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
    year: int,
    next_cursor: str | None,
    has_more: bool,
) -> AsesorReportResponse:
    rows = [
        AsesorRow(
            seller_id=row.seller_id,
            seller_name=row.seller_name,
            exam_breakdown=exam_breakdowns.get(row.seller_id, {}),
            ganados=int(row.ganados or 0),
            perdidos=int(row.perdidos or 0),
            mantenidos=int(row.mantenidos or 0),
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
    return AsesorDetail(
        seller_name=seller_name,
        countries=unique_sorted_values(geo_rows, "country"),
        zones=unique_sorted_values(geo_rows, "zone"),
        states=unique_sorted_values(geo_rows, "state"),
        cities=unique_sorted_values(geo_rows, "city"),
        total_schools=int((aggregate_row.total_schools if aggregate_row else 0) or 0),
        total_exams=int((aggregate_row.total_exams if aggregate_row else 0) or 0),
        total_revenue=float((aggregate_row.total_revenue if aggregate_row else 0) or 0),
        exam_breakdown=exam_breakdown,
        ganados=status_map.get("ganado", empty_status()),
        perdidos=status_map.get("perdido", empty_status()),
        mantenidos=status_map.get("mantenido", empty_status()),
    )


async def getAsesorReport(filters: AsesorFilters) -> AsesorReportResponse:
    where_clause, params, expanding_keys = build_common_filters(filters, include_sellers=True)
    summary_rows, has_more, next_cursor = await fetch_paginated_summary_rows(
        where_clause,
        params,
        expanding_keys,
        limit=filters.limit,
        cursor=filters.cursor,
    )
    seller_ids = [int(row.seller_id) for row in summary_rows]
    breakdown_rows = await fetch_summary_exam_breakdown_rows_by_seller_ids(
        where_clause,
        params,
        expanding_keys,
        seller_ids,
    )
    exam_breakdowns = map_summary_exam_breakdowns(breakdown_rows)
    return build_asesor_report_response(summary_rows, exam_breakdowns, filters.year, next_cursor, has_more)


async def getAsesorDetail(seller_id: int, filters: AsesorFilters) -> AsesorDetail:
    seller_name = await fetch_seller_name(seller_id)
    if seller_name is None:
        raise HTTPException(status_code=404, detail="Seller not found")

    where_clause, params, expanding_keys = build_common_filters(filters)
    detail_params = {**params, "seller_id": seller_id}
    aggregate_row, geo_rows, breakdown_rows, status_rows = await asyncio.gather(
        fetch_detail_aggregate_row(where_clause, detail_params, expanding_keys),
        fetch_detail_geo_rows(where_clause, detail_params, expanding_keys),
        fetch_detail_exam_breakdown_rows(where_clause, detail_params, expanding_keys),
        fetch_detail_status_rows(where_clause, detail_params, expanding_keys),
    )
    exam_breakdown = map_detail_exam_breakdown(breakdown_rows)
    status_map = map_status_rows(status_rows)
    return build_asesor_detail_response(seller_name, aggregate_row, geo_rows, exam_breakdown, status_map)
