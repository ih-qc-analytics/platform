from app.services.utils.fact_subqueries import (
    build_deduped_paid_cart_product_fact_subquery,
    build_paid_payment_fact_subquery,
    build_paid_student_allocation_fact_subquery,
)
from app.services.por_asesor.repository import execute_repo_query


async def fetch_country_school_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    paid_payment_fact = build_paid_payment_fact_subquery(where_clause)
    query = f"""
        SELECT
            qpay.country,
            COUNT(DISTINCT qpay.lead_id) AS total_schools
        FROM ({paid_payment_fact}) qpay
        GROUP BY qpay.country
        ORDER BY qpay.country ASC
    """
    return await execute_repo_query(query, params, expanding_keys)


async def fetch_country_exam_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    paid_allocation_fact = build_paid_student_allocation_fact_subquery(where_clause)
    paid_cart_product_fact = build_deduped_paid_cart_product_fact_subquery(paid_allocation_fact)
    query = f"""
        SELECT
            paid_cart_products.country,
            paid_cart_products.exam_name,
            COALESCE(SUM(paid_cart_products.exam_count), 0) AS exam_count
        FROM (
            SELECT DISTINCT
                pcp.cart_product_id,
                pcp.country,
                pcp.exam_name,
                pcp.cart_product_quantity AS exam_count
            FROM ({paid_cart_product_fact}) pcp
        ) paid_cart_products
        GROUP BY paid_cart_products.country, paid_cart_products.exam_name
        ORDER BY paid_cart_products.country ASC, paid_cart_products.exam_name ASC
    """
    return await execute_repo_query(query, params, expanding_keys)


async def fetch_country_presence_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    paid_payment_fact = build_paid_payment_fact_subquery(where_clause)
    query = f"""
        SELECT DISTINCT
            qpay.country,
            qpay.lead_id
        FROM ({paid_payment_fact}) qpay
        ORDER BY qpay.country ASC, qpay.lead_id ASC
    """
    return await execute_repo_query(query, dict(params), expanding_keys)


async def fetch_country_metric_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    paid_allocation_fact = build_paid_student_allocation_fact_subquery(where_clause)
    paid_cart_product_fact = build_deduped_paid_cart_product_fact_subquery(paid_allocation_fact)
    query = f"""
        SELECT
            paid_cart_products.country,
            paid_cart_products.lead_id,
            COALESCE(SUM(paid_cart_products.exam_count), 0) AS exams
        FROM (
            SELECT DISTINCT
                pcp.cart_product_id,
                pcp.country,
                pcp.lead_id,
                pcp.cart_product_quantity AS exam_count
            FROM ({paid_cart_product_fact}) pcp
        ) paid_cart_products
        GROUP BY paid_cart_products.country, paid_cart_products.lead_id
        ORDER BY paid_cart_products.country ASC, paid_cart_products.lead_id ASC
    """
    return await execute_repo_query(query, dict(params), expanding_keys)
