import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.schemas.reports import (
    TotalSalesResponse, TrendPoint, GeoPoint, ProductMix
)

BASE = "/reports/ventas-totales"

# ─────────────────────────────────────────────
# MOCK RESPONSE
# ─────────────────────────────────────────────

MOCK_RESPONSE = TotalSalesResponse(
    total_clients=3,
    total_exams=6,
    exam_revenue=6000.0,
    total_books=3,
    book_revenue=900.0,
    total_courses=1,
    course_revenue=500.0,
    total_otros=0,
    otros_revenue=0.0,
    total_revenue=7400.0,
    expected_revenue=7200.0,
    expected_cost=3500.0,
    uncategorized_revenue=1000.0,
    unknown_site_revenue=0.0,
    unknown_site_expected_revenue=0.0,
    profit_margin=52.7,
    prior_year_revenue=0.0,
    growth_pct=0.0,
    trend_points=[
        TrendPoint(month="2025-01", revenue=2300.0),
        TrendPoint(month="2025-02", revenue=3500.0),
    ],
    geo_points=[
        GeoPoint(dimension="mexico", revenue=3900.0),
        GeoPoint(dimension="colombia", revenue=3500.0),
    ],
    product_mix=ProductMix(exams_pct=81.1, books_pct=12.2, courses_pct=6.8, unknown_pct=13.5),
)


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

async def post(body: dict = {}):
    with patch(
        "app.routers.total_sales.getTotalSalesData",
        new=AsyncMock(return_value=MOCK_RESPONSE)
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            return await client.post(BASE, json=body)


# ─────────────────────────────────────────────
# STATUS + SHAPE
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_endpoint_returns_200():
    r = await post()
    assert r.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_response_has_required_fields():
    data = (await post()).json()
    required = {
        "total_clients", "total_exams", "exam_revenue",
        "total_books", "book_revenue", "total_courses", "course_revenue",
        "total_otros", "otros_revenue",
        "total_revenue", "expected_revenue", "expected_cost", "uncategorized_revenue",
        "unknown_site_revenue", "unknown_site_expected_revenue", "profit_margin", "prior_year_revenue",
        "trend_points", "geo_points", "product_mix",
    }
    assert required.issubset(data.keys())


@pytest.mark.asyncio(loop_scope="session")
async def test_trend_points_shape():
    data = (await post()).json()
    for pt in data["trend_points"]:
        assert "month" in pt and "revenue" in pt


@pytest.mark.asyncio(loop_scope="session")
async def test_geo_points_shape():
    data = (await post()).json()
    for pt in data["geo_points"]:
        assert "dimension" in pt and "revenue" in pt


@pytest.mark.asyncio(loop_scope="session")
async def test_product_mix_shape():
    data = (await post()).json()
    mix = data["product_mix"]
    assert mix is not None
    assert {"exams_pct", "books_pct", "courses_pct", "unknown_pct"}.issubset(mix.keys())


# ─────────────────────────────────────────────
# BODY PARSING
# verifies FastAPI correctly deserializes the JSON body into ReportFilters
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_single_country_parsed():
    mock = AsyncMock(return_value=MOCK_RESPONSE)
    with patch("app.routers.total_sales.getTotalSalesData", new=mock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            await client.post(BASE, json={"countries": ["mexico"]})
    filters = mock.call_args[0][0]
    assert filters.countries == ["mexico"]


@pytest.mark.asyncio(loop_scope="session")
async def test_multiple_countries_parsed():
    mock = AsyncMock(return_value=MOCK_RESPONSE)
    with patch("app.routers.total_sales.getTotalSalesData", new=mock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            await client.post(BASE, json={"countries": ["mexico", "colombia"]})
    filters = mock.call_args[0][0]
    assert set(filters.countries) == {"mexico", "colombia"}


@pytest.mark.asyncio(loop_scope="session")
async def test_date_params_parsed():
    mock = AsyncMock(return_value=MOCK_RESPONSE)
    with patch("app.routers.total_sales.getTotalSalesData", new=mock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            await client.post(BASE, json={"date_from": "2025-01-01", "date_to": "2025-01-31"})
    filters = mock.call_args[0][0]
    assert filters.date_from == "2025-01-01"
    assert filters.date_to == "2025-01-31"


@pytest.mark.asyncio(loop_scope="session")
async def test_empty_body_uses_defaults():
    mock = AsyncMock(return_value=MOCK_RESPONSE)
    with patch("app.routers.total_sales.getTotalSalesData", new=mock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            await client.post(BASE, json={})
    filters = mock.call_args[0][0]
    assert filters.countries == []
    assert filters.date_from is None
    assert filters.date_to is None


# ─────────────────────────────────────────────
# SERIALIZATION
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_numeric_fields_are_numbers():
    data = (await post()).json()
    assert isinstance(data["total_revenue"], (int, float))
    assert isinstance(data["profit_margin"], (int, float))
    assert isinstance(data["total_clients"], int)


@pytest.mark.asyncio(loop_scope="session")
async def test_trend_points_are_list():
    data = (await post()).json()
    assert isinstance(data["trend_points"], list)
    assert len(data["trend_points"]) > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_product_mix_null_when_service_returns_none():
    empty_response = MOCK_RESPONSE.model_copy(update={"product_mix": None, "total_revenue": 0.0})
    with patch(
        "app.routers.total_sales.getTotalSalesData",
        new=AsyncMock(return_value=empty_response)
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            data = (await client.post(BASE, json={})).json()
    assert data["product_mix"] is None
