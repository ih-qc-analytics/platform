from fastapi import APIRouter, Request

from app.schemas.pdf import AsesorDetailPDFPayload, PorAsesorPDFPayload
from app.schemas.reports import AsesorDetail, AsesorFilters, AsesorReportResponse
from app.services.exports.excel import generate_excel_response
from app.services.utils.currency_rates import build_country_rates_for_mxn
from app.services.por_asesor.por_asesor import (
    build_asesor_detail_pdf_payload,
    build_por_asesor_pdf_payload,
    build_asesor_export_filters_for_all,
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
    return await getAsesorReport(filters, country_rates=resolve_por_asesor_country_rates(request))


@router.post("/por-asesor/{seller_id}", response_model=AsesorDetail)
async def get_por_asesor_detail(seller_id: int, filters: AsesorFilters, request: Request):
    return await getAsesorDetail(seller_id, filters, country_rates=resolve_por_asesor_country_rates(request))


@router.post("/por-asesor/{seller_id}/export/pdf", response_model=AsesorDetailPDFPayload)
async def export_asesor_detail_pdf(seller_id: int, filters: AsesorFilters, request: Request):
    return await build_asesor_detail_pdf_payload(
        seller_id,
        filters,
        country_rates=resolve_por_asesor_country_rates(request),
    )


@router.post("/por-asesor/export/pdf", response_model=PorAsesorPDFPayload)
async def export_por_asesor_pdf(filters: AsesorFilters, request: Request):
    return await build_por_asesor_pdf_payload(
        filters,
        country_rates=resolve_por_asesor_country_rates(request),
    )


@router.post("/por-asesor/export/excel")
async def export_por_asesor_excel(filters: AsesorFilters, request: Request):
    country_rates = resolve_por_asesor_country_rates(request)
    report = await getAsesorReport(filters, country_rates=country_rates)
    details = await getAsesorDetailsForRows(report.rows, filters, country_rates=country_rates)
    return generate_excel_response(
        "por-asesor",
        build_asesor_export_worksheets(report, details),
    )


@router.post("/por-asesor/export/excel/all")
async def export_por_asesor_excel_all(filters: AsesorFilters, request: Request):
    country_rates = resolve_por_asesor_country_rates(request)
    export_filters = build_asesor_export_filters_for_all(filters)
    report = await getAllAsesorReportRows(export_filters, country_rates=country_rates)
    details = await getAsesorDetailsForRows(report.rows, export_filters, country_rates=country_rates)
    return generate_excel_response(
        "por-asesor-all",
        build_asesor_export_worksheets(report, details),
    )
