from fastapi import APIRouter, Request

from app.schemas.reports import PorPaisDetailResponse, PorPaisFilters, PorPaisReportResponse
from app.services.exports.pdf_renderer import render_por_pais_detail_pdf, render_por_pais_pdf
from app.services.exports.excel import generate_excel_response
from app.services.utils.report_currency import get_request_base_currency
from app.services.por_pais.por_pais import (
    build_por_pais_detail_pdf_payload,
    build_por_pais_pdf_payload,
    build_por_pais_export_filters_for_all,
    build_por_pais_export_worksheets,
    get_por_pais_detail,
    get_por_pais_details_for_report,
    get_por_pais_report,
)

router = APIRouter()


@router.post("/por-pais", response_model=PorPaisReportResponse)
async def get_por_pais_data(filters: PorPaisFilters, request: Request):
    return await get_por_pais_report(filters, base_currency=get_request_base_currency(request))


@router.post("/por-pais/{country}", response_model=PorPaisDetailResponse)
async def get_por_pais_detail_endpoint(country: str, filters: PorPaisFilters):
    return await get_por_pais_detail(country, filters)


@router.post("/por-pais/export/pdf")
async def export_por_pais_pdf(filters: PorPaisFilters, request: Request):
    payload = await build_por_pais_pdf_payload(
        filters, base_currency=get_request_base_currency(request)
    )
    return await render_por_pais_pdf(payload)


@router.post("/por-pais/{country}/export/pdf")
async def export_por_pais_detail_pdf(country: str, filters: PorPaisFilters):
    payload = await build_por_pais_detail_pdf_payload(country, filters)
    return await render_por_pais_detail_pdf(payload)


@router.post("/por-pais/export/excel")
async def export_por_pais_excel(filters: PorPaisFilters, request: Request):
    report = await get_por_pais_report(filters, base_currency=get_request_base_currency(request))
    details = await get_por_pais_details_for_report(report, filters)
    return generate_excel_response(
        "por-pais",
        build_por_pais_export_worksheets(report, details),
    )


@router.post("/por-pais/export/excel/all")
async def export_por_pais_excel_all(filters: PorPaisFilters, request: Request):
    export_filters = build_por_pais_export_filters_for_all(filters)
    report = await get_por_pais_report(
        export_filters, base_currency=get_request_base_currency(request)
    )
    details = await get_por_pais_details_for_report(report, export_filters)
    return generate_excel_response(
        "por-pais-all",
        build_por_pais_export_worksheets(report, details),
    )
