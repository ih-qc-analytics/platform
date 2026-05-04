import base64
import json

from sqlalchemy import bindparam, text

from app.database import SessionLocal


def encode_cursor(total_revenue: float, seller_name: str, seller_id: int) -> str:
    payload = {
        "total_revenue": total_revenue,
        "seller_name": seller_name,
        "seller_id": seller_id,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> dict[str, object]:
    padding = "=" * (-len(cursor) % 4)
    decoded = base64.urlsafe_b64decode((cursor + padding).encode("utf-8")).decode("utf-8")
    payload = json.loads(decoded)
    return {
        "cursor_total_revenue": float(payload["total_revenue"]),
        "cursor_seller_name": str(payload["seller_name"]),
        "cursor_seller_id": int(payload["seller_id"]),
    }


async def execute_repo_query(query: str, params: dict, expanding_keys: list[str]):
    stmt = text(query)
    if expanding_keys:
        stmt = stmt.bindparams(*(bindparam(key, expanding=True) for key in expanding_keys))
    async with SessionLocal() as session:
        result = await session.execute(stmt, params)
        return result.fetchall()


def build_summary_base_query(where_clause: str) -> str:
    return f"""
        SELECT
            s.id AS seller_id,
            CONCAT(s.name, ' ', s.lastName) AS seller_name,
            COUNT(DISTINCT CASE WHEN sl.businessStatus = 'ganado' THEN l.id END) AS ganados,
            COUNT(DISTINCT CASE WHEN sl.businessStatus = 'perdido' THEN l.id END) AS perdidos,
            COUNT(DISTINCT CASE WHEN sl.businessStatus = 'mantenido' THEN l.id END) AS mantenidos,
            COALESCE(SUM(cp.total), 0) AS total_revenue
        FROM seller s
        JOIN seller_lead sl ON sl.sellerId = s.id
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        WHERE {where_clause}
        GROUP BY s.id, s.name, s.lastName
    """


def build_cursor_clause(cursor: str | None) -> tuple[str, dict[str, object]]:
    if not cursor:
        return "", {}

    cursor_params = decode_cursor(cursor)
    clause = """
        WHERE
            summary.total_revenue < :cursor_total_revenue
            OR (
                summary.total_revenue = :cursor_total_revenue
                AND summary.seller_name > :cursor_seller_name
            )
            OR (
                summary.total_revenue = :cursor_total_revenue
                AND summary.seller_name = :cursor_seller_name
                AND summary.seller_id > :cursor_seller_id
            )
    """
    return clause, cursor_params


async def fetch_paginated_summary_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
    limit: int,
    cursor: str | None,
):
    cursor_clause, cursor_params = build_cursor_clause(cursor)
    query = f"""
        SELECT *
        FROM (
            {build_summary_base_query(where_clause)}
        ) summary
        {cursor_clause}
        ORDER BY summary.total_revenue DESC, summary.seller_name ASC, summary.seller_id ASC
        LIMIT :page_size
    """
    page_params = {
        **params,
        **cursor_params,
        "page_size": limit + 1,
    }
    rows = await execute_repo_query(query, page_params, expanding_keys)
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = None
    if has_more and page_rows:
        last_row = page_rows[-1]
        next_cursor = encode_cursor(
            total_revenue=float(last_row.total_revenue or 0),
            seller_name=last_row.seller_name,
            seller_id=int(last_row.seller_id),
        )
    return page_rows, has_more, next_cursor


async def fetch_summary_exam_breakdown_rows_by_seller_ids(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
    seller_ids: list[int],
):
    if not seller_ids:
        return []

    query = f"""
        SELECT
            s.id AS seller_id,
            ec.name AS exam_name,
            COALESCE(SUM(cp.quantity), 0) AS exam_count
        FROM seller s
        JOIN seller_lead sl ON sl.sellerId = s.id
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        JOIN exam_cat ec ON p.examId = ec.id
        WHERE {where_clause}
          AND s.id IN :seller_ids
        GROUP BY s.id, ec.name
    """
    breakdown_params = {
        **params,
        "seller_ids": seller_ids,
    }
    return await execute_repo_query(query, breakdown_params, [*expanding_keys, "seller_ids"])
