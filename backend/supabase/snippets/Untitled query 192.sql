 SELECT seller_name, total_revenue, uncategorized_revenue
  FROM (
    SELECT
      rp.seller_name,
      SUM(rp.amount_mxn) AS total_revenue,
      SUM(rp.amount_mxn) - COALESCE(li.allocated_revenue, 0) AS uncategorized_revenue
    FROM report_payments rp
    LEFT JOIN (
      SELECT seller_id, SUM(paid_total_mxn) AS allocated_revenue
      FROM report_line_items
      WHERE is_active = TRUE
        AND payment_status = 'Aprobado'
        AND include_in_product_breakdown = TRUE
      GROUP BY seller_id
    ) li ON li.seller_id = rp.seller_id
    WHERE rp.is_active = TRUE
      AND rp.payment_status = 'Aprobado'
      AND rp.seller_name = 'Lucia Rios'
    GROUP BY rp.seller_name, li.allocated_revenue
  ) t;