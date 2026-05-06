import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.schemas.reports import (
    PorPaisDetailResponse,
    PorPaisReportResponse,
    PorPaisStatusRow,
    PorPaisSummaryRow,
)


REPORT_RESPONSE = PorPaisReportResponse(
    summary_rows=[
        PorPaisSummaryRow(
            country="mexico",
            total_schools=3,
            cambridge=19,
            ielts=1,
            michigan=0,
            tea=0,
            other=2,
        )
    ],
    status_rows=[
        PorPaisStatusRow(
            country="mexico",
            schools_ganados=2,
            schools_perdidos=0,
            schools_mantenidos=1,
            exams_ganados=16,
            exams_perdidos=0,
            exams_mantenidos=6,
        )
    ],
)


DETAIL_RESPONSE = PorPaisDetailResponse(
    country="mexico",
    exam_counts={
        "A2 Key": 18,
        "TKT": 1,
        "IELTS": 1,
        "Other": 2,
    },
)


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_post_returns_200():
    with patch(
        "app.routers.por_pais.getPorPaisReport",
        new=AsyncMock(return_value=REPORT_RESPONSE),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            response = await client.post(
                "/reports/por-pais",
                json={"date_from": "2025-01-01", "date_to": "2025-12-31"},
            )

    assert response.status_code == 200
    assert response.json()["summary_rows"][0]["country"] == "mexico"
    assert response.json()["status_rows"][0]["schools_ganados"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_post_parses_filters():
    mock = AsyncMock(return_value=REPORT_RESPONSE)
    with patch("app.routers.por_pais.getPorPaisReport", new=mock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            await client.post(
                "/reports/por-pais",
                json={"date_from": "2025-01-01", "date_to": "2025-12-31"},
            )

    filters = mock.call_args[0][0]
    assert filters.date_from == "2025-01-01"
    assert filters.date_to == "2025-12-31"


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_detail_returns_200():
    with patch(
        "app.routers.por_pais.getPorPaisDetail",
        new=AsyncMock(return_value=DETAIL_RESPONSE),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            response = await client.post(
                "/reports/por-pais/mexico",
                json={"date_from": "2025-01-01", "date_to": "2025-12-31"},
            )

    assert response.status_code == 200
    assert response.json()["country"] == "mexico"
    assert response.json()["exam_counts"]["A2 Key"] == 18


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_detail_parses_body_and_country():
    mock = AsyncMock(return_value=DETAIL_RESPONSE)
    with patch("app.routers.por_pais.getPorPaisDetail", new=mock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            await client.post(
                "/reports/por-pais/colombia",
                json={"date_from": "2025-07-01", "date_to": "2025-12-31"},
            )

    country, filters = mock.call_args[0]
    assert country == "colombia"
    assert filters.date_from == "2025-07-01"
    assert filters.date_to == "2025-12-31"
