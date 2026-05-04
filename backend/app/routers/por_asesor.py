from fastapi import APIRouter

from app.schemas.reports import AsesorDetail, AsesorFilters, AsesorReportResponse
from app.services.por_asesor.por_asesor import getAsesorDetail, getAsesorReport


router = APIRouter()


@router.post("/por-asesor", response_model=AsesorReportResponse)
async def get_por_asesor_data(filters: AsesorFilters):
    return await getAsesorReport(filters)


@router.post("/por-asesor/{seller_id}", response_model=AsesorDetail)
async def get_por_asesor_detail(seller_id: int, filters: AsesorFilters):
    return await getAsesorDetail(seller_id, filters)
