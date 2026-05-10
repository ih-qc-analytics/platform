from sqlalchemy import bindparam, text

from app.database import SessionLocal
from app.schemas.reports import DetalleFilters, DetalleReportResponse, DetalleRow
from app.services.por_asesor.product_grouping import EXAM_NAME_ORDER, canonical_exam_name
from app.services.utils.fact_subqueries import (
    build_deduped_paid_cart_product_fact_subquery,
    build_paid_student_allocation_fact_subquery,
)
from app.services.utils.report_filters import (
    build_student_payment_fact_where_clause,
)


DETALLE_EXAM_NAME_ORDER = [*EXAM_NAME_ORDER, "Other"]


def create_empty_exam_counts() -> dict[str, int]:
    return {exam_name: 0 for exam_name in DETALLE_EXAM_NAME_ORDER}


def build_detalle_where(filters: DetalleFilters) -> tuple[str, dict, list[str]]:
    where_clause, params, expanding_keys = build_student_payment_fact_where_clause(
        filters,
        include_exam_product=True,
    )
    conditions = [where_clause]

    if filters.cursor is not None:
        conditions.append("cp.id > :cursor")
        params["cursor"] = filters.cursor

    if filters.search:
        conditions.append(
            "(CONCAT(s.name, ' ', s.lastName) LIKE :search OR l.name LIKE :search)"
        )
        params["search"] = f"%{filters.search}%"

    return " AND ".join(conditions), params, expanding_keys


async def getDetalleData(filters: DetalleFilters) -> DetalleReportResponse:
    where_clause, params, expanding_keys = build_detalle_where(filters)
    params["page_size"] = filters.page_size + 1
    paid_allocation_fact = build_paid_student_allocation_fact_subquery(where_clause)
    paid_cart_product_fact = build_deduped_paid_cart_product_fact_subquery(paid_allocation_fact)

    query = f"""
        SELECT DISTINCT
            pcp.cart_product_id AS id,
            pcp.seller_name,
            pcp.school_name,
            pcp.exam_date,
            pcp.exam_name,
            pcp.cart_product_quantity AS quantity
        FROM ({paid_cart_product_fact}) pcp
        ORDER BY pcp.cart_product_id ASC
        LIMIT :page_size
    """

    stmt = text(query)
    if expanding_keys:
        stmt = stmt.bindparams(*(bindparam(key, expanding=True) for key in expanding_keys))

    async with SessionLocal() as session:
        result = await session.execute(stmt, params)
        raw_rows = result.fetchall()

    # One DetalleRow per paid cart-product line.
    grouped: dict[int, dict] = {}
    order: list[int] = []
    for row in raw_rows:
        cp_id = row.id
        if cp_id not in grouped:
            grouped[cp_id] = {
                "id": cp_id,
                "seller_name": row.seller_name,
                "school_name": row.school_name,
                "exam_date": str(row.exam_date) if row.exam_date else "",
                "exam_counts": create_empty_exam_counts(),
            }
            order.append(cp_id)
        if row.exam_name:
            exam_counts = grouped[cp_id]["exam_counts"]
            exam_name = canonical_exam_name(row.exam_name)
            exam_counts[exam_name] = exam_counts.get(exam_name, 0) + row.quantity

    pivoted = [grouped[k] for k in order]
    has_more = len(pivoted) > filters.page_size
    if has_more:
        pivoted = pivoted[: filters.page_size]

    rows = [
        DetalleRow(
            id=r["id"],
            seller_name=r["seller_name"],
            school_name=r["school_name"],
            exam_date=r["exam_date"],
            exam_counts=r["exam_counts"],
            total=sum(r["exam_counts"].values()),
        )
        for r in pivoted
    ]

    next_cursor = rows[-1].id if has_more and rows else None

    return DetalleReportResponse(rows=rows, next_cursor=next_cursor, has_more=has_more)
