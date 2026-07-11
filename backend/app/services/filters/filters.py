from app.reporting.database import ReportingSessionLocal
from sqlalchemy import text
from app.enums import PaymentStatus
from app.schemas.reports import FilterOptionsResponse, SellerOptionsResponse


# obtener los filtros geograficos disponibles en los datos, es decir todas las ciudades/zonas... donde
# hay operaciones
async def get_filters() -> FilterOptionsResponse:
    async with ReportingSessionLocal() as session:
        t = text("""
            SELECT DISTINCT 'country' AS filter_type, site AS value
            FROM report_payments
            WHERE site IS NOT NULL AND is_active = TRUE AND payment_status = :payment_status
            UNION ALL
            SELECT DISTINCT 'zone' AS filter_type, zone_name AS value
            FROM report_payments
            WHERE zone_name IS NOT NULL AND is_active = TRUE AND payment_status = :payment_status
            UNION ALL
            SELECT DISTINCT 'state' AS filter_type, unnest(all_states) AS value
            FROM report_payments
            WHERE is_active = TRUE AND payment_status = :payment_status
            UNION ALL
            SELECT DISTINCT 'city' AS filter_type, unnest(all_cities) AS value
            FROM report_payments
            WHERE is_active = TRUE AND payment_status = :payment_status
        """)
        result = await session.execute(t, {"payment_status": PaymentStatus.APROBADO.value})
        rows = result.fetchall()
        options = {"country": [], "zone": [], "state": [], "city": []}
        for row in rows:
            options[row.filter_type].append(row.value)

        return FilterOptionsResponse(
            countries=options["country"],
            zones=options["zone"],
            states=options["state"],
            cities=options["city"],
        )


async def get_seller_options() -> SellerOptionsResponse:
    async with ReportingSessionLocal() as session:
        t = text("""
            SELECT DISTINCT seller_name
            FROM report_payments
            WHERE is_active = TRUE AND payment_status = :payment_status
            ORDER BY seller_name ASC
        """)
        result = await session.execute(t, {"payment_status": PaymentStatus.APROBADO.value})
        rows = result.fetchall()
        return SellerOptionsResponse(sellers=[row.seller_name for row in rows])
