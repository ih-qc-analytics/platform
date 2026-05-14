from fastapi import APIRouter, Request
from app.schemas.pdf import VentasTotalesPDFPayload
from app.services.exports.excel import generate_excel_response
from app.schemas.reports import TotalSalesResponse, ReportFilters
from app.services.utils.currency_rates import build_country_rates_for_mxn
from app.services.total_sales.total_sales import (
    build_ventas_totales_pdf_payload,
    build_total_sales_export_filters_for_all,
    build_total_sales_export_worksheets,
    getTotalSalesData,
)

router = APIRouter()


def resolve_total_sales_country_rates(request: Request) -> dict[str, float]:
    return build_country_rates_for_mxn(getattr(request.app.state, "rates", None))

@router.post("/ventas-totales", response_model=TotalSalesResponse)
async def get_total_sales_data(filters: ReportFilters, request: Request):
    return await getTotalSalesData(filters, country_rates=resolve_total_sales_country_rates(request))


@router.post("/ventas-totales/export/pdf", response_model=VentasTotalesPDFPayload)
async def export_total_sales_pdf(filters: ReportFilters, request: Request):
    return await build_ventas_totales_pdf_payload(
        filters,
        country_rates=resolve_total_sales_country_rates(request),
    )


@router.post("/ventas-totales/export/excel")
async def export_total_sales_excel(filters: ReportFilters, request: Request):
    response = await getTotalSalesData(
        filters,
        country_rates=resolve_total_sales_country_rates(request),
    )
    return generate_excel_response(
        "ventas-totales",
        build_total_sales_export_worksheets(response),
    )


@router.post("/ventas-totales/export/excel/all")
async def export_total_sales_excel_all(filters: ReportFilters, request: Request):
    response = await getTotalSalesData(
        build_total_sales_export_filters_for_all(filters),
        country_rates=resolve_total_sales_country_rates(request),
    )
    return generate_excel_response(
        "ventas-totales-all",
        build_total_sales_export_worksheets(response),
    )
