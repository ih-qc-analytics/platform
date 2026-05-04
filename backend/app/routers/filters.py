from fastapi import APIRouter
from app.services.filters.filters import getFilters, getSellerOptions
from app.schemas.reports import FilterOptionsResponse, SellerOptionsResponse

router = APIRouter()

@router.get("/options", response_model=FilterOptionsResponse)
async def get_filter_options():
    return await getFilters()


@router.get("/sellers", response_model=SellerOptionsResponse)
async def get_seller_options():
    return await getSellerOptions()
