import pytest

from app.schemas.reports import PorPaisFilters
from app.services.por_pais.por_pais import getPorPaisDetail, getPorPaisReport


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_full_year_summary_and_status_rows_match_payment_based_model(
    ui_dev_reporting_db,
):
    result = await getPorPaisReport(PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31"))

    assert [row.model_dump() for row in result.current.summary_rows] == [
        {
            "country": "colombia",
            "total_schools": 2,
            "total_revenue": 7100.0,
            "uncategorized_revenue": 0.0,
            "cambridge": 2,
            "ielts": 0,
            "michigan": 1,
            "tea": 2,
            "other": 0,
        },
        {
            "country": "mexico",
            "total_schools": 3,
            "total_revenue": 5400.0,
            "uncategorized_revenue": 500.0,
            "cambridge": 4,
            "ielts": 0,
            "michigan": 0,
            "tea": 0,
            "other": 1,
        },
        {
            "country": "peru",
            "total_schools": 1,
            "total_revenue": 1700.0,
            "uncategorized_revenue": 0.0,
            "cambridge": 0,
            "ielts": 1,
            "michigan": 0,
            "tea": 0,
            "other": 0,
        },
    ]
    assert [row.model_dump() for row in result.current.status_rows] == [
        {
            "country": "colombia",
            "schools_ganados": 1,
            "schools_perdidos": 0,
            "schools_mantenidos": 1,
            "exams_ganados": 3,
            "exams_perdidos": 0,
            "exams_mantenidos": 2,
        },
        {
            "country": "mexico",
            "schools_ganados": 2,
            "schools_perdidos": 0,
            "schools_mantenidos": 1,
            "exams_ganados": 2,
            "exams_perdidos": 0,
            "exams_mantenidos": 3,
        },
        {
            "country": "peru",
            "schools_ganados": 0,
            "schools_perdidos": 0,
            "schools_mantenidos": 1,
            "exams_ganados": 0,
            "exams_perdidos": 0,
            "exams_mantenidos": 1,
        },
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_detail_returns_canonical_exam_counts_per_country(ui_dev_reporting_db):
    mexico = await getPorPaisDetail(
        "mexico",
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31"),
    )
    colombia = await getPorPaisDetail(
        "colombia",
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31"),
    )

    assert mexico.exam_counts["A2 Key"] == 2
    assert mexico.exam_counts["B1 Preliminary"] == 1
    assert mexico.exam_counts["TKT"] == 1
    assert mexico.exam_counts["Other"] == 1

    assert colombia.exam_counts["B2 First"] == 2
    assert colombia.exam_counts["MET"] == 1
    assert colombia.exam_counts["TEA"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_midyear_range_rewinds_exact_prior_period_for_statuses(ui_dev_reporting_db):
    result = await getPorPaisReport(PorPaisFilters(date_from="2025-05-01", date_to="2025-08-31"))

    assert [row.model_dump() for row in result.current.summary_rows] == [
        {
            "country": "colombia",
            "total_schools": 1,
            "total_revenue": 3500.0,
            "uncategorized_revenue": 0.0,
            "cambridge": 0,
            "ielts": 0,
            "michigan": 1,
            "tea": 2,
            "other": 0,
        },
        {
            "country": "mexico",
            "total_schools": 1,
            "total_revenue": 1000.0,
            "uncategorized_revenue": 500.0,
            "cambridge": 0,
            "ielts": 0,
            "michigan": 0,
            "tea": 0,
            "other": 1,
        },
        {
            "country": "peru",
            "total_schools": 1,
            "total_revenue": 1700.0,
            "uncategorized_revenue": 0.0,
            "cambridge": 0,
            "ielts": 1,
            "michigan": 0,
            "tea": 0,
            "other": 0,
        },
    ]
    assert [row.model_dump() for row in result.current.status_rows] == [
        {
            "country": "colombia",
            "schools_ganados": 1,
            "schools_perdidos": 1,
            "schools_mantenidos": 0,
            "exams_ganados": 3,
            "exams_perdidos": 1,
            "exams_mantenidos": 0,
        },
        {
            "country": "mexico",
            "schools_ganados": 1,
            "schools_perdidos": 1,
            "schools_mantenidos": 0,
            "exams_ganados": 1,
            "exams_perdidos": 1,
            "exams_mantenidos": 0,
        },
        {
            "country": "peru",
            "schools_ganados": 1,
            "schools_perdidos": 0,
            "schools_mantenidos": 0,
            "exams_ganados": 1,
            "exams_perdidos": 0,
            "exams_mantenidos": 0,
        },
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_empty_range_returns_empty_sections(ui_dev_reporting_db):
    result = await getPorPaisReport(PorPaisFilters(date_from="2030-01-01", date_to="2030-12-31"))

    assert result.current.summary_rows == []
    assert result.current.status_rows == []
