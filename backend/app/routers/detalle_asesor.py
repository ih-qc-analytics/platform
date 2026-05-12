from fastapi import APIRouter

from app.schemas.pdf import DetalleAsesorPDFPayload
from app.schemas.reports import DetalleFilters, DetalleReportResponse
from app.services.detalle_asesor.detalle_asesor import (
    build_detalle_asesor_pdf_payload,
    build_detalle_export_filters_for_all,
    build_detalle_export_worksheets,
    getAllDetalleRows,
    getDetalleData,
)
from app.services.exports.excel import generate_excel_response

router = APIRouter()


@router.post("/detalle-asesor", response_model=DetalleReportResponse)
async def get_detalle_asesor(filters: DetalleFilters):
    return await getDetalleData(filters)


@router.post("/detalle-asesor/export/pdf", response_model=DetalleAsesorPDFPayload)
async def export_detalle_asesor_pdf(filters: DetalleFilters):
    return await build_detalle_asesor_pdf_payload(filters)


@router.post("/detalle-asesor/export/excel")
async def export_detalle_asesor_excel(filters: DetalleFilters):
    report = await getDetalleData(filters)
    return generate_excel_response(
        "detalle-asesor",
        build_detalle_export_worksheets(report),
    )


@router.post("/detalle-asesor/export/excel/all")
async def export_detalle_asesor_excel_all(filters: DetalleFilters):
    report = await getAllDetalleRows(build_detalle_export_filters_for_all(filters))
    return generate_excel_response(
        "detalle-asesor-all",
        build_detalle_export_worksheets(report),
    )
