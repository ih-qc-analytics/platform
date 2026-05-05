from sqlalchemy import bindparam, text

from app.database import SessionLocal
from app.schemas.reports import DetalleFilters, DetalleReportResponse, DetalleRow
from app.services.por_asesor.product_grouping import EXAM_NAME_ORDER, canonical_exam_name


DETALLE_EXAM_NAME_ORDER = [*EXAM_NAME_ORDER, "Other"]


def create_empty_exam_counts() -> dict[str, int]:
    return {exam_name: 0 for exam_name in DETALLE_EXAM_NAME_ORDER}


def build_detalle_where(filters: DetalleFilters) -> tuple[str, dict, list[str]]:
    conditions = [
        "c.deletedAt IS NULL",
        "p.productType = 'exam'",
        "cp.deletedAt IS NULL",
    ]
    params: dict = {}
    expanding_keys: list[str] = []

    if filters.cursor is not None:
        conditions.append("cp.id > :cursor")
        params["cursor"] = filters.cursor

    if filters.search:
        conditions.append(
            "(CONCAT(s.name, ' ', s.lastName) LIKE :search OR l.name LIKE :search)"
        )
        params["search"] = f"%{filters.search}%"

    def add_in(field: str, values: list[str], sql: str) -> None:
        if values:
            conditions.append(sql)
            params[field] = values
            expanding_keys.append(field)

    add_in("countries", filters.countries, "l.site IN :countries")
    add_in("zones", filters.zones, "z.name IN :zones")
    add_in("states", filters.states, "la.stateName IN :states")
    add_in("cities", filters.cities, "la.city IN :cities")

    if filters.date_from:
        conditions.append("c.createdAt >= :date_from")
        params["date_from"] = filters.date_from

    if filters.date_to:
        conditions.append("c.createdAt <= :date_to")
        params["date_to"] = filters.date_to

    return " AND ".join(conditions), params, expanding_keys


async def getDetalleData(filters: DetalleFilters) -> DetalleReportResponse:
    where_clause, params, expanding_keys = build_detalle_where(filters)
    params["page_size"] = filters.page_size + 1

    query = f"""
        SELECT
            cp.id,
            CONCAT(s.name, ' ', s.lastName) AS seller_name,
            l.name AS school_name,
            cp.testDate AS exam_date,
            ec.name AS exam_name,
            cp.quantity
        FROM cart c
        JOIN seller_lead sl ON c.sellerLeadId = sl.id
        JOIN seller s ON sl.sellerId = s.id
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        LEFT JOIN (SELECT DISTINCT leadId, stateName, city FROM lead_address) la ON la.leadId = l.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        LEFT JOIN exam_cat ec ON p.examId = ec.id
        WHERE {where_clause}
        ORDER BY cp.id ASC
        LIMIT :page_size
    """

    stmt = text(query)
    if expanding_keys:
        stmt = stmt.bindparams(*(bindparam(key, expanding=True) for key in expanding_keys))

    async with SessionLocal() as session:
        result = await session.execute(stmt, params)
        raw_rows = result.fetchall()

    # Pivot: one DetalleRow per cp.id, aggregating exam counts
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
