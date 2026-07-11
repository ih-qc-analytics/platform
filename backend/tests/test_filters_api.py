import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.auth import verify_token
from app.schemas.reports import FilterOptionsResponse, SellerOptionsResponse


FILTER_OPTIONS_RESPONSE = FilterOptionsResponse(
    countries=["mexico", "colombia"],
    zones=["IH Mexico", "IH Colombia"],
    states=["CDMX", "Bogota"],
    cities=["Mexico City", "Bogota"],
)

SELLER_OPTIONS_RESPONSE = SellerOptionsResponse(
    sellers=["Ana Garcia", "Carlos Rodriguez"],
)


@pytest.mark.asyncio(loop_scope="session")
async def test_filter_options_endpoint_returns_200():
    app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}
    try:
        with patch(
            "app.routers.filters.get_filters",
            new=AsyncMock(return_value=FILTER_OPTIONS_RESPONSE),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:  # type: ignore[arg-type]
                response = await client.get("/filters/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["countries"] == ["mexico", "colombia"]


@pytest.mark.asyncio(loop_scope="session")
async def test_seller_options_endpoint_returns_200():
    app.dependency_overrides[verify_token] = lambda: {"sub": "test-user"}
    try:
        with patch(
            "app.routers.filters.get_seller_options",
            new=AsyncMock(return_value=SELLER_OPTIONS_RESPONSE),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:  # type: ignore[arg-type]
                response = await client.get("/filters/sellers")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["sellers"] == ["Ana Garcia", "Carlos Rodriguez"]
