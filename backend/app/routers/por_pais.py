from fastapi import APIRouter

from app.schemas.pdf import PorPaisDetailPDFPayload, PorPaisPDFPayload
from app.schemas.reports import PorPaisDetailResponse, PorPaisFilters, PorPaisReportResponse
from app.services.exports.excel import generate_excel_response
from app.services.por_pais.por_pais import (
    build_por_pais_detail_pdf_payload,
    build_por_pais_pdf_payload,
    build_por_pais_export_filters_for_all,
    build_por_pais_export_worksheets,
    getPorPaisDetail,
    getPorPaisDetailsForReport,
    getPorPaisReport,
)

router = APIRouter()


@router.post("/por-pais", response_model=PorPaisReportResponse)
async def get_por_pais_data(filters: PorPaisFilters):
    return await getPorPaisReport(filters)


@router.post("/por-pais/{country}", response_model=PorPaisDetailResponse)
async def get_por_pais_detail(country: str, filters: PorPaisFilters):
    return await getPorPaisDetail(country, filters)


@router.post("/por-pais/export/pdf", response_model=PorPaisPDFPayload)
async def export_por_pais_pdf(filters: PorPaisFilters):
    return await build_por_pais_pdf_payload(filters)


@router.post("/por-pais/{country}/export/pdf", response_model=PorPaisDetailPDFPayload)
async def export_por_pais_detail_pdf(country: str, filters: PorPaisFilters):
    return await build_por_pais_detail_pdf_payload(country, filters)


@router.post("/por-pais/export/excel")
async def export_por_pais_excel(filters: PorPaisFilters):
    report = await getPorPaisReport(filters)
    details = await getPorPaisDetailsForReport(report, filters)
    return generate_excel_response(
        "por-pais",
        build_por_pais_export_worksheets(report, details),
    )


@router.post("/por-pais/export/excel/all")
async def export_por_pais_excel_all(filters: PorPaisFilters):
    export_filters = build_por_pais_export_filters_for_all(filters)
    report = await getPorPaisReport(export_filters)
    details = await getPorPaisDetailsForReport(report, export_filters)
    return generate_excel_response(
        "por-pais-all",
        build_por_pais_export_worksheets(report, details),
    )
