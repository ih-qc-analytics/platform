from fastapi import APIRouter, Request

from app.schemas.reports import AsesorDetailResponse, AsesorFilters, AsesorReportResponse
from app.services.exports.pdf_renderer import render_asesor_detail_pdf, render_por_asesor_pdf
from app.services.exports.excel import generate_excel_response
from app.services.utils.currency_rates import build_country_rates_for_mxn
from app.services.utils.report_currency import get_request_base_currency
from app.services.por_asesor.por_asesor import (
    build_asesor_detail_pdf_payload,
    build_por_asesor_pdf_payload,
    build_asesor_export_filters_for_all,
    build_asesor_filtered_export_filters,
    build_asesor_export_worksheets,
    getAllAsesorReportRows,
    getAsesorDetail,
    getAsesorDetailsForRows,
    getAsesorReport,
)


router = APIRouter()


def resolve_por_asesor_country_rates(request: Request) -> dict[str, float]:
    return build_country_rates_for_mxn(getattr(request.app.state, "rates", None))


@router.post("/por-asesor", response_model=AsesorReportResponse)
async def get_por_asesor_data(filters: AsesorFilters, request: Request):
    return await getAsesorReport(
        filters,
        country_rates=resolve_por_asesor_country_rates(request),
        base_currency=get_request_base_currency(request),
    )


@router.post("/por-asesor/{seller_id}", response_model=AsesorDetailResponse)
async def get_por_asesor_detail(seller_id: int, filters: AsesorFilters, request: Request):
    return await getAsesorDetail(
        seller_id,
        filters,
        country_rates=resolve_por_asesor_country_rates(request),
        base_currency=get_request_base_currency(request),
    )


@router.post("/por-asesor/{seller_id}/export/pdf")
async def export_asesor_detail_pdf(seller_id: int, filters: AsesorFilters, request: Request):
    payload = await build_asesor_detail_pdf_payload(
        seller_id,
        filters,
        country_rates=resolve_por_asesor_country_rates(request),
        base_currency=get_request_base_currency(request),
    )
    return await render_asesor_detail_pdf(payload)


@router.post("/por-asesor/export/pdf")
async def export_por_asesor_pdf(filters: AsesorFilters, request: Request):
    payload = await build_por_asesor_pdf_payload(
        filters,
        country_rates=resolve_por_asesor_country_rates(request),
        base_currency=get_request_base_currency(request),
    )
    return await render_por_asesor_pdf(payload)


@router.post("/por-asesor/export/excel")
async def export_por_asesor_excel(filters: AsesorFilters, request: Request):
    country_rates = resolve_por_asesor_country_rates(request)
    base_currency = get_request_base_currency(request)
    export_filters = build_asesor_filtered_export_filters(filters)
    report = await getAllAsesorReportRows(
        export_filters, country_rates=country_rates, base_currency=base_currency
    )
    details = await getAsesorDetailsForRows(
        report.current.rows,
        export_filters,
        country_rates=country_rates,
        base_currency=base_currency,
    )
    return generate_excel_response(
        "por-asesor",
        build_asesor_export_worksheets(report, details),
    )


@router.post("/por-asesor/export/excel/all")
async def export_por_asesor_excel_all(filters: AsesorFilters, request: Request):
    country_rates = resolve_por_asesor_country_rates(request)
    base_currency = get_request_base_currency(request)
    export_filters = build_asesor_export_filters_for_all(filters)
    report = await getAllAsesorReportRows(
        export_filters,
        country_rates=country_rates,
        base_currency=base_currency,
    )
    details = await getAsesorDetailsForRows(
        report.current.rows,
        export_filters,
        country_rates=country_rates,
        base_currency=base_currency,
    )
    return generate_excel_response(
        "por-asesor-all",
        build_asesor_export_worksheets(report, details),
    )
