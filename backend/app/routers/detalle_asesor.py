from fastapi import APIRouter

from app.schemas.reports import DetalleFilters, DetalleReportResponse
from app.services.exports.pdf_renderer import render_detalle_asesor_pdf
from app.services.detalle_asesor.detalle_asesor import (
    build_detalle_asesor_pdf_payload,
    build_detalle_export_filters_for_all,
    build_detalle_filtered_export_filters,
    build_detalle_export_worksheets,
    get_all_detalle_rows,
    get_detalle_data,
)
from app.services.exports.excel import generate_excel_response

router = APIRouter()


@router.post("/detalle-asesor", response_model=DetalleReportResponse)
async def get_detalle_asesor(filters: DetalleFilters):
    return await get_detalle_data(filters)


@router.post("/detalle-asesor/export/pdf")
async def export_detalle_asesor_pdf(filters: DetalleFilters):
    payload = await build_detalle_asesor_pdf_payload(filters)
    return await render_detalle_asesor_pdf(payload)


@router.post("/detalle-asesor/export/excel")
async def export_detalle_asesor_excel(filters: DetalleFilters):
    report = await get_all_detalle_rows(build_detalle_filtered_export_filters(filters))
    return generate_excel_response(
        "detalle-asesor",
        build_detalle_export_worksheets(report),
    )


@router.post("/detalle-asesor/export/excel/all")
async def export_detalle_asesor_excel_all(filters: DetalleFilters):
    report = await get_all_detalle_rows(build_detalle_export_filters_for_all(filters))
    return generate_excel_response(
        "detalle-asesor-all",
        build_detalle_export_worksheets(report),
    )
