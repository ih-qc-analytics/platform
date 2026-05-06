import pytest

from app.schemas.reports import PorPaisFilters
from app.services.por_pais.por_pais import getPorPaisDetail, getPorPaisReport


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_report_returns_expected_summary_and_status_rows(ui_dev_db):
    result = await getPorPaisReport(
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31")
    )

    assert [row.country for row in result.summary_rows] == ["colombia", "mexico", "peru"]
    assert [row.country for row in result.status_rows] == ["colombia", "mexico", "peru"]

    summary_by_country = {row.country: row for row in result.summary_rows}
    assert summary_by_country["mexico"].model_dump() == {
        "country": "mexico",
        "total_schools": 3,
        "cambridge": 19,
        "ielts": 1,
        "michigan": 0,
        "tea": 0,
        "other": 2,
    }
    assert summary_by_country["colombia"].model_dump() == {
        "country": "colombia",
        "total_schools": 2,
        "cambridge": 8,
        "ielts": 0,
        "michigan": 0,
        "tea": 1,
        "other": 0,
    }
    assert summary_by_country["peru"].model_dump() == {
        "country": "peru",
        "total_schools": 3,
        "cambridge": 10,
        "ielts": 0,
        "michigan": 1,
        "tea": 0,
        "other": 0,
    }

    status_by_country = {row.country: row for row in result.status_rows}
    assert status_by_country["mexico"].model_dump() == {
        "country": "mexico",
        "schools_ganados": 2,
        "schools_perdidos": 0,
        "schools_mantenidos": 1,
        "exams_ganados": 16,
        "exams_perdidos": 0,
        "exams_mantenidos": 6,
    }
    assert status_by_country["colombia"].model_dump() == {
        "country": "colombia",
        "schools_ganados": 2,
        "schools_perdidos": 1,
        "schools_mantenidos": 0,
        "exams_ganados": 9,
        "exams_perdidos": 2,
        "exams_mantenidos": 0,
    }
    assert status_by_country["peru"].model_dump() == {
        "country": "peru",
        "schools_ganados": 2,
        "schools_perdidos": 0,
        "schools_mantenidos": 1,
        "exams_ganados": 8,
        "exams_perdidos": 0,
        "exams_mantenidos": 3,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_detail_returns_expected_canonical_exam_counts(ui_dev_db):
    result = await getPorPaisDetail(
        "mexico",
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31"),
    )

    assert result.country == "mexico"
    assert result.exam_counts["A2 Key"] == 18
    assert result.exam_counts["TKT"] == 1
    assert result.exam_counts["IELTS"] == 1
    assert result.exam_counts["Other"] == 2
    assert result.exam_counts["B1 Preliminary"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_report_uses_rewound_prior_period_for_statuses(ui_dev_db):
    result = await getPorPaisReport(
        PorPaisFilters(date_from="2025-07-01", date_to="2025-12-31")
    )

    status_by_country = {row.country: row for row in result.status_rows}
    assert status_by_country["mexico"].schools_ganados == 1
    assert status_by_country["mexico"].schools_mantenidos == 1
    assert status_by_country["colombia"].schools_perdidos == 1
    assert status_by_country["peru"].schools_mantenidos == 1
