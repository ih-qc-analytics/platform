import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.schemas.reports import (
    AsesorDetail,
    AsesorReportResponse,
    AsesorRow,
    BusinessStatusDetail,
    ExamBrandDetail,
)


SUMMARY_RESPONSE = AsesorReportResponse(
    rows=[
        AsesorRow(
            seller_id=1,
            seller_name="Ana Garcia",
            exam_breakdown={
                "Cambridge English (Main Suite)": 18,
                "Cambridge Teaching & Skills": 0,
                "IELTS": 0,
                "Michigan (MET)": 0,
                "TEA (Test of English for Aviation)": 0,
                "Placement & Otros": 0,
            },
            ganados=2,
            perdidos=0,
            mantenidos=1,
            total_revenue=19200.0,
            uncategorized_revenue=1200.0,
        )
    ],
    year=2025,
    next_cursor="cursor-1",
    has_more=True,
)


DETAIL_RESPONSE = AsesorDetail(
    seller_name="Ana Garcia",
    countries=["mexico"],
    zones=["IH Mexico"],
    states=["CDMX"],
    cities=["Mexico City"],
    total_schools=3,
    total_exams=22,
    total_revenue=19200.0,
    uncategorized_revenue=1200.0,
    exam_breakdown={
        "Cambridge English (Main Suite)": ExamBrandDetail(exams=18, schools=3, revenue=18000.0),
        "Cambridge Teaching & Skills": ExamBrandDetail(exams=0, schools=0, revenue=0.0),
        "IELTS": ExamBrandDetail(exams=0, schools=0, revenue=0.0),
        "Michigan (MET)": ExamBrandDetail(exams=0, schools=0, revenue=0.0),
        "TEA (Test of English for Aviation)": ExamBrandDetail(exams=0, schools=0, revenue=0.0),
        "Placement & Otros": ExamBrandDetail(exams=0, schools=0, revenue=0.0),
    },
    ganados=BusinessStatusDetail(schools=2, exams=16, revenue=14600.0),
    perdidos=BusinessStatusDetail(schools=0, exams=0, revenue=0.0),
    mantenidos=BusinessStatusDetail(schools=1, exams=6, revenue=4600.0),
)


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_post_returns_200():
    with patch(
        "app.routers.por_asesor.getAsesorReport",
        new=AsyncMock(return_value=SUMMARY_RESPONSE),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            response = await client.post("/reports/por-asesor", json={"year": 2025})

    assert response.status_code == 200
    assert response.json()["rows"][0]["seller_name"] == "Ana Garcia"
    assert response.json()["next_cursor"] == "cursor-1"


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_post_parses_filters():
    mock = AsyncMock(return_value=SUMMARY_RESPONSE)
    with patch("app.routers.por_asesor.getAsesorReport", new=mock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            await client.post(
                "/reports/por-asesor",
                json={
                    "year": 2025,
                    "countries": ["mexico"],
                    "sellers": ["Ana Garcia"],
                    "limit": 10,
                    "cursor": "cursor-1",
                },
            )

    filters = mock.call_args[0][0]
    assert filters.year == 2025
    assert filters.countries == ["mexico"]
    assert filters.sellers == ["Ana Garcia"]
    assert filters.limit == 10
    assert filters.cursor == "cursor-1"


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_returns_200():
    with patch(
        "app.routers.por_asesor.getAsesorDetail",
        new=AsyncMock(return_value=DETAIL_RESPONSE),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            response = await client.post("/reports/por-asesor/1", json={"year": 2025})

    assert response.status_code == 200
    assert response.json()["seller_name"] == "Ana Garcia"


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_parses_body():
    mock = AsyncMock(return_value=DETAIL_RESPONSE)
    with patch("app.routers.por_asesor.getAsesorDetail", new=mock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:  # type: ignore[arg-type]
            await client.post(
                "/reports/por-asesor/2",
                json={
                    "year": 2025,
                    "countries": ["colombia"],
                    "states": ["Antioquia"],
                    "cities": ["Medellin"],
                    "sellers": ["Ana Garcia"],
                },
            )

    seller_id, filters = mock.call_args[0]
    assert seller_id == 2
    assert filters.year == 2025
    assert filters.countries == ["colombia"]
    assert filters.states == ["Antioquia"]
    assert filters.cities == ["Medellin"]
    assert filters.sellers == ["Ana Garcia"]
