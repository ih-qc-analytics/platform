import pytest

from app.schemas.reports import AsesorFilters
from app.services.por_asesor.por_asesor import getAsesorDetail, getAsesorReport


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_2025_summary_orders_sellers_by_payment_revenue(ui_dev_reporting_db):
    result = await getAsesorReport(AsesorFilters(year=2025))

    assert [row.seller_name for row in result.rows] == [
        "Carlos Rodriguez",
        "Ana Garcia",
        "Lucia Rios",
        "Miguel Torres",
    ]
    assert [row.total_revenue for row in result.rows] == [7100.0, 4400.0, 1700.0, 1000.0]


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_2025_summary_uses_allocated_exam_breakdowns_and_payment_status_sets(ui_dev_reporting_db):
    result = await getAsesorReport(AsesorFilters(year=2025))
    by_name = {row.seller_name: row for row in result.rows}

    assert by_name["Carlos Rodriguez"].model_dump() == {
        "seller_id": 2,
        "seller_name": "Carlos Rodriguez",
        "exam_breakdown": {
            "Cambridge English (Main Suite)": 2,
            "Cambridge Teaching & Skills": 0,
            "IELTS": 0,
            "Michigan (MET)": 1,
            "TEA (Test of English for Aviation)": 2,
            "Placement & Otros": 0,
        },
        "ganados": 1,
        "perdidos": 0,
        "mantenidos": 1,
        "total_revenue": 7100.0,
    }
    assert by_name["Ana Garcia"].model_dump() == {
        "seller_id": 1,
        "seller_name": "Ana Garcia",
        "exam_breakdown": {
            "Cambridge English (Main Suite)": 3,
            "Cambridge Teaching & Skills": 1,
            "IELTS": 0,
            "Michigan (MET)": 0,
            "TEA (Test of English for Aviation)": 0,
            "Placement & Otros": 0,
        },
        "ganados": 1,
        "perdidos": 0,
        "mantenidos": 1,
        "total_revenue": 4400.0,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_2024_summary_uses_prior_year_payment_presence(ui_dev_reporting_db):
    result = await getAsesorReport(AsesorFilters(year=2024))

    assert [row.seller_name for row in result.rows] == [
        "Lucia Rios",
        "Carlos Rodriguez",
        "Ana Garcia",
    ]
    assert [row.total_revenue for row in result.rows] == [1700.0, 1300.0, 1000.0]


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_supports_pagination(ui_dev_reporting_db):
    first_page = await getAsesorReport(AsesorFilters(year=2025, limit=2))
    second_page = await getAsesorReport(
        AsesorFilters(year=2025, limit=2, cursor=first_page.next_cursor)
    )

    assert [row.seller_name for row in first_page.rows] == [
        "Carlos Rodriguez",
        "Ana Garcia",
    ]
    assert first_page.has_more is True
    assert first_page.next_cursor is not None

    assert [row.seller_name for row in second_page.rows] == [
        "Lucia Rios",
        "Miguel Torres",
    ]
    assert second_page.has_more is False
    assert second_page.next_cursor is None


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_supports_seller_country_and_zone_filters(ui_dev_reporting_db):
    result = await getAsesorReport(
        AsesorFilters(
            year=2025,
            sellers=["Carlos Rodriguez"],
            countries=["colombia"],
            zones=["IH Colombia"],
        )
    )

    assert len(result.rows) == 1
    assert result.rows[0].seller_name == "Carlos Rodriguez"
    assert result.rows[0].total_revenue == 7100.0


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_ana_matches_expected_paid_geo_breakdown_and_statuses(ui_dev_reporting_db):
    result = await getAsesorDetail(1, AsesorFilters(year=2025))

    assert result.model_dump() == {
        "seller_name": "Ana Garcia",
        "countries": ["mexico"],
        "zones": ["IH Mexico"],
        "states": ["CDMX", "Jalisco"],
        "cities": ["Guadalajara", "Mexico City"],
        "total_schools": 2,
        "total_exams": 4,
        "total_revenue": 4400.0,
        "exam_breakdown": {
            "Cambridge English (Main Suite)": {"exams": 3, "schools": 2, "revenue": 3200.0},
            "Cambridge Teaching & Skills": {"exams": 1, "schools": 1, "revenue": 900.0},
            "IELTS": {"exams": 0, "schools": 0, "revenue": 0.0},
            "Michigan (MET)": {"exams": 0, "schools": 0, "revenue": 0.0},
            "TEA (Test of English for Aviation)": {"exams": 0, "schools": 0, "revenue": 0.0},
            "Placement & Otros": {"exams": 0, "schools": 0, "revenue": 0.0},
        },
        "ganados": {"schools": 1, "exams": 1, "revenue": 1500.0},
        "perdidos": {"schools": 0, "exams": 0, "revenue": 0.0},
        "mantenidos": {"schools": 1, "exams": 3, "revenue": 2900.0},
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_carlos_matches_expected_paid_geo_breakdown_and_statuses(ui_dev_reporting_db):
    result = await getAsesorDetail(2, AsesorFilters(year=2025))

    assert result.model_dump() == {
        "seller_name": "Carlos Rodriguez",
        "countries": ["colombia"],
        "zones": ["IH Colombia"],
        "states": ["Antioquia", "Bogota"],
        "cities": ["Bogota", "Medellin"],
        "total_schools": 2,
        "total_exams": 5,
        "total_revenue": 7100.0,
        "exam_breakdown": {
            "Cambridge English (Main Suite)": {"exams": 2, "schools": 1, "revenue": 3000.0},
            "Cambridge Teaching & Skills": {"exams": 0, "schools": 0, "revenue": 0.0},
            "IELTS": {"exams": 0, "schools": 0, "revenue": 0.0},
            "Michigan (MET)": {"exams": 1, "schools": 1, "revenue": 1300.0},
            "TEA (Test of English for Aviation)": {"exams": 2, "schools": 1, "revenue": 2200.0},
            "Placement & Otros": {"exams": 0, "schools": 0, "revenue": 0.0},
        },
        "ganados": {"schools": 1, "exams": 3, "revenue": 3500.0},
        "perdidos": {"schools": 0, "exams": 0, "revenue": 0.0},
        "mantenidos": {"schools": 1, "exams": 2, "revenue": 3600.0},
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_fully_allocated_sellers_reconciles_total_to_ganados_plus_mantenidos(ui_dev_reporting_db):
    for seller_id in (1, 2, 3):
        result = await getAsesorDetail(seller_id, AsesorFilters(year=2025))
        assert result.total_revenue == result.ganados.revenue + result.mantenidos.revenue


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_miguel_keeps_unallocated_payment_gap_visible(ui_dev_reporting_db):
    result = await getAsesorDetail(4, AsesorFilters(year=2025))

    assert result.total_revenue == 1000.0
    assert result.ganados.revenue == 500.0
    assert result.total_revenue - result.ganados.revenue == 500.0
    assert result.exam_breakdown["Placement & Otros"].model_dump() == {
        "exams": 1,
        "schools": 1,
        "revenue": 500.0,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_year_with_no_rows_returns_zero_breakdowns(ui_dev_reporting_db):
    result = await getAsesorDetail(4, AsesorFilters(year=2024))

    assert result.seller_name == "Miguel Torres"
    assert result.countries == []
    assert result.zones == []
    assert result.states == []
    assert result.cities == []
    assert result.total_schools == 0
    assert result.total_exams == 0
    assert result.total_revenue == 0.0
    assert result.ganados.model_dump() == {"schools": 0, "exams": 0, "revenue": 0.0}
    assert result.perdidos.model_dump() == {"schools": 0, "exams": 0, "revenue": 0.0}
    assert result.mantenidos.model_dump() == {"schools": 0, "exams": 0, "revenue": 0.0}
