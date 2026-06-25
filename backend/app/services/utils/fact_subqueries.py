from app.services.utils.report_filters import payment_date_expr
from app.services.utils.currency_rates import FALLBACK_EXCHANGE_RATE, sql_normalized_country_expr


"""
    One row per approved payment after report filters are applied.

    Used for cash-total style metrics such as:
    - total revenue
    - period trend
    - geo rollups
    - seller/country presence based on paid payments

    Assumptions:
    - `payment.quantity` is the monetary amount to aggregate
    - payment-level metrics must not join `student_payments`, otherwise the
      payment amount would fan out across allocation rows
    - the caller's `where_clause` is written against these aliases:
      `pay`, `c`, `sl`, `l`, `z`
    """


def build_paid_payment_fact_subquery(
    where_clause: str,
    *,
    fx_table_sql: str | None = None,
) -> str:
    payment_rate_expr = (
        "COALESCE(fx.rate_to_base, :fallback_rate)" if fx_table_sql else str(FALLBACK_EXCHANGE_RATE)
    )
    payment_join = (
        f"LEFT JOIN ({fx_table_sql}) fx ON {sql_normalized_country_expr('l.site')} = fx.country_key"
        if fx_table_sql
        else ""
    )
    return f"""
        SELECT
            pay.id AS payment_id,
            pay.quantity AS paid_amount,
            pay.quantity * {payment_rate_expr} AS paid_amount_base,
            {payment_date_expr()} AS payment_day,
            c.id AS cart_id,
            sl.id AS seller_lead_id,
            s.id AS seller_id,
            CONCAT(s.name, ' ', s.lastName) AS seller_name,
            l.id AS lead_id,
            l.name AS school_name,
            l.site AS country,
            z.name AS zone_name
        FROM payment pay
        JOIN cart c ON c.id = pay.cartId
        JOIN seller_lead sl ON sl.id = c.sellerLeadId
        JOIN seller s ON s.id = sl.sellerId
        JOIN `lead` l ON l.id = sl.leadId
        LEFT JOIN zone z ON z.id = l.zoneId
        {payment_join}
        WHERE {where_clause}
    """


"""
    One row per paid student allocation after report filters are applied.

    Used for allocated product revenue and for deriving deduped paid
    cart-product lines in exam/product breakdown reports.

    Assumptions:
    - `student_payments.amount` is the allocated paid revenue for the linked
      student/product slice
    - product unit counts should be derived by deduping `cart_product_id`
      before summing `cart_product_quantity`, because multiple allocations can
      point at the same cart-product line
    - the caller's `where_clause` is written against these aliases:
      `pay`, `cp`, `p`, `c`, `sl`, `l`, `z`
    """


def build_paid_student_allocation_fact_subquery(
    where_clause: str,
    *,
    fx_table_sql: str | None = None,
) -> str:
    allocation_rate_expr = (
        "COALESCE(fx.rate_to_base, :fallback_rate)" if fx_table_sql else str(FALLBACK_EXCHANGE_RATE)
    )
    allocation_join = (
        f"LEFT JOIN ({fx_table_sql}) fx ON {sql_normalized_country_expr('l.site')} = fx.country_key"
        if fx_table_sql
        else ""
    )
    return f"""
        SELECT
            sp.payment_id,
            sp.student_id,
            sp.amount AS allocated_amount,
            sp.amount * {allocation_rate_expr} AS allocated_amount_base,
            {payment_date_expr()} AS payment_day,
            cp.id AS cart_product_id,
            cp.quantity AS cart_product_quantity,
            cp.cost AS cart_product_cost,
            cp.cost * {allocation_rate_expr} AS cart_product_cost_base,
            cp.testDate AS exam_date,
            p.productType AS product_type,
            ec.name AS exam_name,
            c.id AS cart_id,
            sl.id AS seller_lead_id,
            s.id AS seller_id,
            CONCAT(s.name, ' ', s.lastName) AS seller_name,
            l.id AS lead_id,
            l.name AS school_name,
            l.site AS country,
            z.name AS zone_name
        FROM student_payments sp
        JOIN payment pay ON pay.id = sp.payment_id
        JOIN student st ON st.id = sp.student_id
        JOIN cart_product cp ON cp.id = st.cartProductId
        JOIN product p ON p.id = cp.productId
        LEFT JOIN exam_cat ec ON ec.id = p.examId
        JOIN cart c ON c.id = cp.cartId
        JOIN seller_lead sl ON sl.id = c.sellerLeadId
        JOIN seller s ON s.id = sl.sellerId
        JOIN `lead` l ON l.id = sl.leadId
        LEFT JOIN zone z ON z.id = l.zoneId
        {allocation_join}
        WHERE {where_clause}
    """


"""
    One row per paid cart-product line derived from the student-allocation fact.

    Used when reports need unit-style product counts or line-level cost without
    multiplying `cart_product.quantity` or `cart_product.cost` across multiple
    `student_payments` rows that point to the same cart-product line.

    Assumptions:
    - multiple paid student allocations can legitimately reference the same
      `cart_product_id`
    - quantity/cost metrics should count each paid cart-product line once
    - the provided subquery must expose at least:
      `cart_product_id`, `cart_product_quantity`, `cart_product_cost`,
      `product_type`, `exam_name`, `seller_id`, `seller_name`, `lead_id`,
      `school_name`, `country`, `zone_name`, `exam_date`, `payment_day`
    """


def build_deduped_paid_cart_product_fact_subquery(
    paid_student_allocation_fact_subquery: str,
) -> str:
    return f"""
        SELECT DISTINCT
            qsp.cart_product_id,
            qsp.cart_product_quantity,
            qsp.cart_product_cost,
            qsp.cart_product_cost_base,
            qsp.product_type,
            qsp.exam_name,
            qsp.seller_id,
            qsp.seller_name,
            qsp.lead_id,
            qsp.school_name,
            qsp.country,
            qsp.zone_name,
            qsp.exam_date,
            qsp.payment_day
        FROM ({paid_student_allocation_fact_subquery}) qsp
    """
