from app.database import SessionLocal
from sqlalchemy import text
from app.schemas.reports import FilterOptionsResponse

# obtener los filtros geograficos disponibles en los datos, es decir todas las ciudades/zonas... donde
# hay operaciones
async def getFilters() -> FilterOptionsResponse:
    async with SessionLocal() as session:
        t = text("""SELECT DISTINCT 'country' as filter_type, site as value FROM `lead` WHERE site IS NOT NULL
                    UNION ALL
                    SELECT DISTINCT 'zone', name FROM zone WHERE name IS NOT NULL
                    UNION ALL
                    SELECT DISTINCT 'state', stateName FROM lead_address WHERE stateName IS NOT NULL
                    UNION ALL
                    SELECT DISTINCT 'city', city FROM lead_address WHERE city IS NOT NULL
                 """)
        result = await session.execute(t)
        rows = result.fetchall()
        options = {"country": [], "zone": [], "state": [], "city": []}
        for row in rows: 
            options[row.filter_type].append(row.value)
        
        return FilterOptionsResponse(countries=options["country"],
                                      zones=options["zone"],
                                      states=options["state"], 
                                      cities=options["city"])


