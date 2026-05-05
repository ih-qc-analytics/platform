from fastapi import APIRouter

from app.schemas.reports import DetalleFilters, DetalleReportResponse
from app.services.detalle_asesor.detalle_asesor import getDetalleData

router = APIRouter()


@router.post("/detalle-asesor", response_model=DetalleReportResponse)
async def get_detalle_asesor(filters: DetalleFilters):
    return await getDetalleData(filters)
