from fastapi import APIRouter

from app.schemas.reports import PorPaisDetailResponse, PorPaisFilters, PorPaisReportResponse
from app.services.por_pais.por_pais import getPorPaisDetail, getPorPaisReport

router = APIRouter()


@router.post("/por-pais", response_model=PorPaisReportResponse)
async def get_por_pais_data(filters: PorPaisFilters):
    return await getPorPaisReport(filters)


@router.post("/por-pais/{country}", response_model=PorPaisDetailResponse)
async def get_por_pais_detail(country: str, filters: PorPaisFilters):
    return await getPorPaisDetail(country, filters)
