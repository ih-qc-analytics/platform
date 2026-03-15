from fastapi import APIRouter
from app.services.filters.filters import getFilters
from app.schemas.reports import FilterOptionsResponse

router = APIRouter()

@router.get("/options", response_model=FilterOptionsResponse)
async def get_filter_options():
    return await getFilters()