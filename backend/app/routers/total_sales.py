from fastapi import APIRouter
from app.schemas.pdf import VentasTotalesPDFPayload
from app.services.exports.excel import generate_excel_response
from app.schemas.reports import TotalSalesResponse, ReportFilters
from app.services.total_sales.total_sales import (
    build_ventas_totales_pdf_payload,
    build_total_sales_export_filters_for_all,
    build_total_sales_export_worksheets,
    getTotalSalesData,
)

router = APIRouter()

@router.post("/ventas-totales", response_model=TotalSalesResponse)
async def get_total_sales_data(filters: ReportFilters):
    return await getTotalSalesData(filters)


@router.post("/ventas-totales/export/pdf", response_model=VentasTotalesPDFPayload)
async def export_total_sales_pdf(filters: ReportFilters):
    return await build_ventas_totales_pdf_payload(filters)


@router.post("/ventas-totales/export/excel")
async def export_total_sales_excel(filters: ReportFilters):
    response = await getTotalSalesData(filters)
    return generate_excel_response(
        "ventas-totales",
        build_total_sales_export_worksheets(response),
    )


@router.post("/ventas-totales/export/excel/all")
async def export_total_sales_excel_all(filters: ReportFilters):
    response = await getTotalSalesData(build_total_sales_export_filters_for_all(filters))
    return generate_excel_response(
        "ventas-totales-all",
        build_total_sales_export_worksheets(response),
    )
