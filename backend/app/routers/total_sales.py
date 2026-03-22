from fastapi import APIRouter
from app.services.total_sales.total_sales import getTotalSalesData
from app.schemas.reports import TotalSalesResponse, ReportFilters

router = APIRouter()

@router.post("/ventas-totales", response_model=TotalSalesResponse)
async def get_total_sales_data(filters: ReportFilters):
    return await getTotalSalesData(filters)