import base64
import json

from sqlalchemy import bindparam, text

from app.database import SessionLocal
from app.services.utils.currency_rates import FALLBACK_EXCHANGE_RATE, build_country_rates_derived_table
from app.enums import ProductType
from app.services.utils.fact_subqueries import (
    build_deduped_paid_cart_product_fact_subquery,
    build_paid_payment_fact_subquery,
    build_paid_student_allocation_fact_subquery,
)
from app.services.utils.report_filters import (
    build_payment_fact_where_clause,
    build_student_payment_fact_where_clause,
    payment_date_expr,
)


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


def build_payment_where_clause(filters, include_sellers: bool = False) -> tuple[str, dict, list[str]]:
    where_clause, params, expanding_keys = build_payment_fact_where_clause(filters, year=filters.year)
    conditions = [where_clause]
    if include_sellers and filters.sellers:
        conditions.append("CONCAT(s.name, ' ', s.lastName) IN :sellers")
        params["sellers"] = list(filters.sellers)
        expanding_keys.append("sellers")
    return " AND ".join(conditions), params, expanding_keys


def build_student_payment_where_clause(filters, include_sellers: bool = False) -> tuple[str, dict, list[str]]:
    where_clause, params, expanding_keys = build_student_payment_fact_where_clause(
        filters,
        year=filters.year,
        include_exam_product=True,
    )
    conditions = [where_clause]
    if include_sellers and filters.sellers:
        conditions.append("CONCAT(s.name, ' ', s.lastName) IN :sellers")
        params["sellers"] = list(filters.sellers)
        expanding_keys.append("sellers")
    return " AND ".join(conditions), params, expanding_keys


def build_summary_base_query(where_clause: str, fx_table_sql: str) -> str:
    return f"""
        SELECT
            s.id AS seller_id,
            CONCAT(s.name, ' ', s.lastName) AS seller_name,
            COALESCE(SUM(qp.paid_amount_base), 0) AS total_revenue
        FROM ({build_paid_payment_fact_subquery(where_clause, fx_table_sql=fx_table_sql)}) qp
        JOIN seller s ON s.id = qp.seller_id
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
    country_rates: dict[str, float],
):
    cursor_clause, cursor_params = build_cursor_clause(cursor)
    fx_table_sql, fx_params = build_country_rates_derived_table(country_rates)
    query = f"""
        SELECT *
        FROM (
            {build_summary_base_query(where_clause, fx_table_sql)}
        ) summary
        {cursor_clause}
        ORDER BY summary.total_revenue DESC, summary.seller_name ASC, summary.seller_id ASC
        LIMIT :page_size
    """
    page_params = {
        **params,
        **fx_params,
        **cursor_params,
        "fallback_rate": FALLBACK_EXCHANGE_RATE,
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

    paid_allocation_fact = build_paid_student_allocation_fact_subquery(where_clause)
    paid_cart_product_fact = build_deduped_paid_cart_product_fact_subquery(paid_allocation_fact)
    query = f"""
        SELECT
            paid_cart_products.seller_id,
            paid_cart_products.exam_name,
            COALESCE(SUM(paid_cart_products.exam_count), 0) AS exam_count
        FROM (
            SELECT DISTINCT
                pcp.seller_id,
                pcp.cart_product_id,
                pcp.exam_name,
                pcp.cart_product_quantity AS exam_count
            FROM ({paid_cart_product_fact}) pcp
            WHERE pcp.seller_id IN :seller_ids
        ) paid_cart_products
        GROUP BY paid_cart_products.seller_id, paid_cart_products.exam_name
    """
    breakdown_params = {
        **params,
        "seller_ids": seller_ids,
    }
    return await execute_repo_query(query, breakdown_params, [*expanding_keys, "seller_ids"])


async def fetch_school_presence_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
    year: int,
):
    query = f"""
        SELECT DISTINCT
            s.id AS seller_id,
            sl.leadId AS lead_id
        FROM seller s
        JOIN seller_lead sl ON sl.sellerId = s.id
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN payment pay ON pay.cartId = c.id
        WHERE {where_clause}
          AND YEAR({payment_date_expr()}) = :presence_year
    """
    return await execute_repo_query(
        query,
        {
            **params,
            "presence_year": year,
        },
        expanding_keys,
    )


async def fetch_school_metric_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
    year: int,
    country_rates: dict[str, float],
):
    fx_table_sql, fx_params = build_country_rates_derived_table(country_rates)
    paid_allocation_fact = build_paid_student_allocation_fact_subquery(where_clause, fx_table_sql=fx_table_sql)
    paid_cart_product_fact = build_deduped_paid_cart_product_fact_subquery(paid_allocation_fact)
    query = f"""
        SELECT
            paid_cart_products.seller_id,
            paid_cart_products.lead_id,
            COALESCE(SUM(paid_cart_products.exam_count), 0) AS exams,
            COALESCE(MAX(allocated_revenue.revenue), 0) AS revenue
        FROM (
            SELECT DISTINCT
                pcp.seller_id,
                pcp.lead_id,
                pcp.cart_product_id,
                pcp.cart_product_quantity AS exam_count
            FROM ({paid_cart_product_fact}) pcp
            WHERE YEAR(pcp.payment_day) = :metrics_year
        ) paid_cart_products
        LEFT JOIN (
            SELECT
                qsp.seller_id,
                qsp.lead_id,
                COALESCE(SUM(qsp.allocated_amount_base), 0) AS revenue
            FROM ({paid_allocation_fact}) qsp
            WHERE YEAR(qsp.payment_day) = :metrics_year
            GROUP BY qsp.seller_id, qsp.lead_id
        ) allocated_revenue
          ON allocated_revenue.seller_id = paid_cart_products.seller_id
         AND allocated_revenue.lead_id = paid_cart_products.lead_id
        GROUP BY paid_cart_products.seller_id, paid_cart_products.lead_id
    """
    return await execute_repo_query(
        query,
        {
            **params,
            **fx_params,
            "metrics_year": year,
            "fallback_rate": FALLBACK_EXCHANGE_RATE,
        },
        expanding_keys,
    )
