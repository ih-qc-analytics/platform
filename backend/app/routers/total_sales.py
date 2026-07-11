from fastapi import APIRouter, Request
from app.services.exports.excel import generate_excel_response
from app.services.exports.pdf_renderer import render_ventas_totales_pdf
from app.schemas.reports import TotalSalesResponse, ReportFilters
from app.services.utils.currency_rates import build_country_rates_for_mxn
from app.services.utils.report_currency import get_request_base_currency
from app.services.total_sales.total_sales import (
    build_ventas_totales_pdf_payload,
    build_total_sales_export_filters_for_all,
    build_total_sales_export_worksheets,
    get_total_sales_data,
)

router = APIRouter()


def resolve_total_sales_country_rates(request: Request) -> dict[str, float]:
    return build_country_rates_for_mxn(getattr(request.app.state, "rates", None))


@router.post("/ventas-totales", response_model=TotalSalesResponse)
async def get_total_sales_data_endpoint(filters: ReportFilters, request: Request):
    return await get_total_sales_data(
        filters,
        country_rates=resolve_total_sales_country_rates(request),
        base_currency=get_request_base_currency(request),
    )


@router.post("/ventas-totales/export/pdf")
async def export_total_sales_pdf(filters: ReportFilters, request: Request):
    payload = await build_ventas_totales_pdf_payload(
        filters,
        country_rates=resolve_total_sales_country_rates(request),
        base_currency=get_request_base_currency(request),
    )
    return await render_ventas_totales_pdf(payload)


@router.post("/ventas-totales/export/excel")
async def export_total_sales_excel(filters: ReportFilters, request: Request):
    response = await get_total_sales_data(
        filters,
        country_rates=resolve_total_sales_country_rates(request),
        base_currency=get_request_base_currency(request),
    )
    return generate_excel_response(
        "ventas-totales",
        build_total_sales_export_worksheets(response),
    )


@router.post("/ventas-totales/export/excel/all")
async def export_total_sales_excel_all(filters: ReportFilters, request: Request):
    response = await get_total_sales_data(
        build_total_sales_export_filters_for_all(filters),
        country_rates=resolve_total_sales_country_rates(request),
        base_currency=get_request_base_currency(request),
    )
    return generate_excel_response(
        "ventas-totales-all",
        build_total_sales_export_worksheets(response),
    )
