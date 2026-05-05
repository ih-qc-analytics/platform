import pytest

from app.schemas.reports import AsesorFilters
from app.services.por_asesor.por_asesor import (
    getAsesorDetail,
    getAsesorReport,
    canonical_exam_category,
    normalize_detail_exam_breakdown,
    normalize_summary_exam_breakdowns,
)
from app.schemas.reports import ExamBrandDetail


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_returns_expected_rows(ui_dev_db):
    result = await getAsesorReport(AsesorFilters(year=2025))

    assert result.year == 2025
    assert [row.seller_name for row in result.rows] == [
        "Ana Garcia",
        "Carlos Rodriguez",
        "Lucia Rios",
        "Miguel Torres",
    ]

    ana = result.rows[0]
    assert ana.exam_breakdown == {
        "Cambridge English (Main Suite)": 18,
        "Cambridge Teaching & Skills": 0,
        "IELTS": 0,
        "Michigan (MET)": 0,
        "TEA (Test of English for Aviation)": 0,
        "Placement & Otros": 0,
    }
    assert ana.ganados == 2
    assert ana.perdidos == 0
    assert ana.mantenidos == 1
    assert ana.total_revenue == 19200.0


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_supports_geo_and_seller_filters(ui_dev_db):
    result = await getAsesorReport(
        AsesorFilters(
            year=2025,
            countries=["colombia"],
            zones=["IH Colombia"],
            sellers=["Carlos Rodriguez"],
        )
    )

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.seller_name == "Carlos Rodriguez"
    assert row.exam_breakdown == {
        "Cambridge English (Main Suite)": 8,
        "Cambridge Teaching & Skills": 0,
        "IELTS": 0,
        "Michigan (MET)": 0,
        "TEA (Test of English for Aviation)": 0,
        "Placement & Otros": 0,
    }
    assert row.ganados == 2
    assert row.perdidos == 1
    assert row.total_revenue == 16000.0


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_returns_expected_breakdowns(ui_dev_db):
    result = await getAsesorDetail(1, AsesorFilters(year=2025))

    assert result.seller_name == "Ana Garcia"
    assert result.countries == ["mexico"]
    assert result.zones == ["IH Mexico"]
    assert result.states == ["CDMX", "Estado de Mexico", "Jalisco"]
    assert result.cities == ["Guadalajara", "Mexico City", "Toluca"]
    assert result.total_schools == 3
    assert result.total_exams == 22
    assert result.total_revenue == 19200.0
    assert result.exam_breakdown["Cambridge English (Main Suite)"].model_dump() == {
        "exams": 18,
        "schools": 3,
        "revenue": 18000.0,
    }
    assert result.ganados.model_dump() == {"schools": 2, "exams": 16, "revenue": 14600.0}
    assert result.perdidos.model_dump() == {"schools": 0, "exams": 0, "revenue": 0.0}
    assert result.mantenidos.model_dump() == {"schools": 1, "exams": 6, "revenue": 4600.0}


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_respects_filters(ui_dev_db):
    result = await getAsesorDetail(
        2,
        AsesorFilters(year=2025, states=["Antioquia"], cities=["Medellin"]),
    )

    assert result.seller_name == "Carlos Rodriguez"
    assert result.countries == ["colombia"]
    assert result.states == ["Antioquia"]
    assert result.cities == ["Medellin"]
    assert result.total_schools == 1
    assert result.total_exams == 8
    assert result.total_revenue == 8000.0
    assert result.exam_breakdown["Cambridge English (Main Suite)"].model_dump() == {
        "exams": 4,
        "schools": 1,
        "revenue": 4800.0,
    }


def test_canonical_exam_category_maps_similar_labels_to_the_same_bucket():
    assert canonical_exam_category("A1 starters") == "Cambridge English (Main Suite)"
    assert canonical_exam_category("IELTS on computer") == "IELTS"
    assert canonical_exam_category("MET Go!") == "Michigan (MET)"
    assert canonical_exam_category("TKT Module 1") == "Cambridge Teaching & Skills"
    assert canonical_exam_category("TEA") == "TEA (Test of English for Aviation)"
    assert canonical_exam_category("Placement Tests") == "Placement & Otros"


def test_normalize_summary_exam_breakdowns_groups_by_category():
    normalized = normalize_summary_exam_breakdowns(
        {
            1: {
                "A1": 10,
                "Starters": 8,
                "a1   starters": 5,
                "PET": 7,
                "IELTS Academic": 4,
                "MET Go!": 3,
                "TKT": 2,
                "TEA": 1,
                "Placement Tests": 9,
            }
        }
    )

    assert normalized == {
        1: {
            "Cambridge English (Main Suite)": 30,
            "Cambridge Teaching & Skills": 2,
            "IELTS": 4,
            "Michigan (MET)": 3,
            "TEA (Test of English for Aviation)": 1,
            "Placement & Otros": 9,
        }
    }


def test_normalize_detail_exam_breakdown_groups_related_labels_into_categories():
    normalized = normalize_detail_exam_breakdown(
        {
            "A1": ExamBrandDetail(exams=10, schools=2, revenue=1000.0),
            "Starters": ExamBrandDetail(exams=8, schools=1, revenue=800.0),
            "a1 starters": ExamBrandDetail(exams=5, schools=1, revenue=500.0),
            "PET": ExamBrandDetail(exams=7, schools=2, revenue=700.0),
            "IELTS Academic": ExamBrandDetail(exams=4, schools=1, revenue=900.0),
            "MET Go!": ExamBrandDetail(exams=3, schools=1, revenue=300.0),
            "TKT": ExamBrandDetail(exams=2, schools=1, revenue=200.0),
            "TEA": ExamBrandDetail(exams=1, schools=1, revenue=100.0),
            "Placement Tests": ExamBrandDetail(exams=9, schools=2, revenue=450.0),
        }
    )

    assert normalized["Cambridge English (Main Suite)"].model_dump() == {
        "exams": 30,
        "schools": 6,
        "revenue": 3000.0,
    }
    assert normalized["Cambridge Teaching & Skills"].model_dump() == {
        "exams": 2,
        "schools": 1,
        "revenue": 200.0,
    }
    assert normalized["IELTS"].model_dump() == {"exams": 4, "schools": 1, "revenue": 900.0}
    assert normalized["Michigan (MET)"].model_dump() == {"exams": 3, "schools": 1, "revenue": 300.0}
    assert normalized["TEA (Test of English for Aviation)"].model_dump() == {
        "exams": 1,
        "schools": 1,
        "revenue": 100.0,
    }
    assert normalized["Placement & Otros"].model_dump() == {
        "exams": 9,
        "schools": 2,
        "revenue": 450.0,
    }
