from app.database import SessionLocal
from app.schemas.reports import GeoPoint, ProductMix, ReportFilters, TotalSalesResponse, TrendPoint
from sqlalchemy import text
from datetime import datetime


async def getTotalSalesData(filters: ReportFilters) -> TotalSalesResponse: 
    where_clause, params = build_where_clause(filters)
    async with SessionLocal() as session: 
        response = await run_main_query(session, filters, where_clause, params)
        if response.total_revenue:
            response.product_mix = ProductMix(
                exams_pct=round(response.exam_revenue / response.total_revenue * 100, 1),
                books_pct=round(response.book_revenue / response.total_revenue * 100, 1),
                courses_pct=round(response.course_revenue / response.total_revenue * 100, 1),
            )
        trend = await run_trend_query(session,filters, where_clause, params)
        geo = await run_geo_query(session,filters, where_clause, params)
        response.trend_points = trend
        response.geo_points = geo
        if filters.date_from and filters.date_to:
            prev_year_revenue = await run_prior_year_query(session, filters)
            response.prior_year_revenue = prev_year_revenue
            if prev_year_revenue > 0:
                response.growth_pct = (response.total_revenue - prev_year_revenue) / prev_year_revenue * 100
            
        return response



async def run_main_query(session, filters: ReportFilters, where_clause, params) -> TotalSalesResponse: 
    query = f"""
        SELECT
            COUNT(DISTINCT l.id) as total_clients,
            SUM(CASE WHEN p.productType = 'exam' THEN cp.quantity ELSE 0 END) as total_exams,      
            SUM(CASE WHEN p.productType = 'exam' THEN cp.total ELSE 0 END) as exam_revenue, 
            SUM(CASE WHEN p.productType = 'book' THEN cp.quantity ELSE 0 END) as total_books,     
            SUM(CASE WHEN p.productType = 'book' THEN cp.total ELSE 0 END) as book_revenue,        
            SUM(CASE WHEN p.productType = 'course' THEN cp.quantity ELSE 0 END) as total_courses,
            SUM(CASE WHEN p.productType = 'course' THEN cp.total ELSE 0 END) as course_revenue,
            SUM(cp.total) as total_revenue,                                   
            SUM(cp.cost) as total_cost                                                       
        FROM cart c
        JOIN seller_lead sl ON c.sellerLeadId = sl.id
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        WHERE {where_clause}
    """ 
    result = await session.execute(text(query), params)
    agg = result.fetchone()
    total_revenue = float(agg.total_revenue or 0)
    total_cost = float(agg.total_cost or 0)
    profit_margin = ((total_revenue - total_cost) / total_revenue * 100) if total_revenue > 0 else 0
    return TotalSalesResponse(
        total_clients=agg.total_clients or 0,
        total_exams=agg.total_exams or 0,
        exam_revenue=float(agg.exam_revenue or 0),
        total_books=agg.total_books or 0,
        book_revenue=float(agg.book_revenue or 0),
        total_courses=agg.total_courses or 0,
        course_revenue=float(agg.course_revenue or 0),
        total_revenue=total_revenue,
        profit_margin=profit_margin,
        prior_year_revenue=0,
        growth_pct=0,
        trend_points=[],
        geo_points=[],
        product_mix=None
    )

    
async def run_trend_query(session, filters: ReportFilters, where_clause, params) -> list[TrendPoint]:
    query = f"""
        SELECT
            DATE_FORMAT(c.createdAt, '%Y-%m') as month,
            SUM(cp.total) as revenue
        FROM cart c
        JOIN seller_lead sl ON c.sellerLeadId = sl.id
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        WHERE {where_clause}
        GROUP BY month
        ORDER BY month ASC
    """
    result = await session.execute(text(query), params)
    return [TrendPoint(month=row.month, revenue=float(row.revenue)) for row in result.fetchall()]


async def run_geo_query(session, filters: ReportFilters, where_clause, params) -> list[GeoPoint]:
    query = f"""
        SELECT
            l.site as dimension,
            SUM(cp.total) as revenue
        FROM cart c
        JOIN seller_lead sl ON c.sellerLeadId = sl.id
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        WHERE {where_clause}
        GROUP BY dimension
    """
    result = await session.execute(text(query), params)
    return [GeoPoint(dimension=row.dimension, revenue=float(row.revenue)) for row in result.fetchall()]


def rewind_dates_one_year(filters: ReportFilters) -> None:
    if filters.date_from is None or filters.date_to is None:
        raise Exception("Cannot rewind non-existent dates")
    date_from_obj = datetime.strptime(filters.date_from, "%Y-%m-%d")
    prior_date_from = date_from_obj.replace(year=date_from_obj.year - 1)
    date_to_obj = datetime.strptime(filters.date_to, "%Y-%m-%d")
    prior_date_to = date_to_obj.replace(year=date_to_obj.year - 1)
    filters.date_from = prior_date_from.strftime("%Y-%m-%d")
    filters.date_to = prior_date_to.strftime("%Y-%m-%d")

async def run_prior_year_query(session, filters: ReportFilters) -> float:
    prior_filters = filters.model_copy()
    rewind_dates_one_year(prior_filters)
    where_clause, params = build_where_clause(prior_filters)
    
    query = f"""
        SELECT SUM(cp.total) as prior_revenue
        FROM cart c
        JOIN seller_lead sl ON c.sellerLeadId = sl.id
        JOIN `lead` l ON sl.leadId = l.id
        LEFT JOIN zone z ON l.zoneId = z.id
        JOIN cart_product cp ON cp.cartId = c.id
        JOIN product p ON cp.productId = p.id
        WHERE {where_clause}
    """
    
    result = await session.execute(text(query), params)
    row = result.fetchone()
    return float(row.prior_revenue or 0)



def build_where_clause(filters: ReportFilters) -> tuple[str, dict]:
    conditions = ["c.deletedAt IS NULL"]
    params = {}

    if filters.countries:
        conditions.append("l.site IN :countries")
        params["countries"] = tuple(filters.countries)

    if filters.zones:
        conditions.append("z.name IN :zones")
        params["zones"] = tuple(filters.zones)

    if filters.states:
        conditions.append("la.stateName IN :states")
        params["states"] = tuple(filters.states)

    if filters.cities:
        conditions.append("la.city IN :cities")
        params["cities"] = tuple(filters.cities)

    if filters.date_from:
        conditions.append("c.createdAt >= :date_from")
        params["date_from"] = filters.date_from

    if filters.date_to:
        conditions.append("c.createdAt <= :date_to")
        params["date_to"] = filters.date_to

    return " AND ".join(conditions), params