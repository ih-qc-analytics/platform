from app.enums import PaymentStatus, ProductType
from app.services.por_asesor.repository import execute_repo_query


async def fetch_country_school_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    query = f"""
        SELECT
            l.site AS country,
            COUNT(DISTINCT l.id) AS total_schools
        FROM seller_lead sl
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        LEFT JOIN (SELECT DISTINCT leadId, stateName, city FROM lead_address) la ON la.leadId = l.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON p.id = cp.productId
        WHERE {where_clause}
        GROUP BY l.site
        ORDER BY l.site ASC
    """
    return await execute_repo_query(query, params, expanding_keys)


async def fetch_country_exam_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    query = f"""
        SELECT
            l.site AS country,
            ec.name AS exam_name,
            COALESCE(SUM(cp.quantity), 0) AS exam_count
        FROM seller_lead sl
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        LEFT JOIN (SELECT DISTINCT leadId, stateName, city FROM lead_address) la ON la.leadId = l.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON p.id = cp.productId
        JOIN exam_cat ec ON ec.id = p.examId
        WHERE {where_clause}
        GROUP BY l.site, ec.name
        ORDER BY l.site ASC, ec.name ASC
    """
    return await execute_repo_query(query, params, expanding_keys)


async def fetch_country_presence_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    query = f"""
        SELECT DISTINCT
            l.site AS country,
            l.id AS lead_id
        FROM seller_lead sl
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        LEFT JOIN (SELECT DISTINCT leadId, stateName, city FROM lead_address) la ON la.leadId = l.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON p.id = cp.productId
        WHERE {where_clause}
          AND EXISTS (
              SELECT 1
              FROM payment pay
              WHERE pay.cartId = c.id
                AND pay.status = :payment_status_aprobado
          )
        ORDER BY l.site ASC, l.id ASC
    """
    query_params = {
        **params,
        "payment_status_aprobado": PaymentStatus.APROBADO.value,
    }
    return await execute_repo_query(query, query_params, expanding_keys)


async def fetch_country_metric_rows(
    where_clause: str,
    params: dict,
    expanding_keys: list[str],
):
    query = f"""
        SELECT
            l.site AS country,
            l.id AS lead_id,
            COALESCE(SUM(cp.quantity), 0) AS exams
        FROM seller_lead sl
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        LEFT JOIN (SELECT DISTINCT leadId, stateName, city FROM lead_address) la ON la.leadId = l.id
        JOIN cart c ON c.sellerLeadId = sl.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON p.id = cp.productId
        WHERE {where_clause}
          AND cp.deletedAt IS NULL
          AND p.productType = :product_type_exam
          AND EXISTS (
              SELECT 1
              FROM payment pay
              WHERE pay.cartId = c.id
                AND pay.status = :payment_status_aprobado
          )
        GROUP BY l.site, l.id
        ORDER BY l.site ASC, l.id ASC
    """
    query_params = {
        **params,
        "payment_status_aprobado": PaymentStatus.APROBADO.value,
        "product_type_exam": ProductType.EXAM.value,
    }
    return await execute_repo_query(query, query_params, expanding_keys)
