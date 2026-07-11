from fastapi import APIRouter
from app.services.filters.filters import get_filters, get_seller_options
from app.schemas.reports import FilterOptionsResponse, SellerOptionsResponse

router = APIRouter()


@router.get("/options", response_model=FilterOptionsResponse)
async def get_filter_options():
    return await get_filters()


@router.get("/sellers", response_model=SellerOptionsResponse)
async def get_seller_options():
    return await get_seller_options()
