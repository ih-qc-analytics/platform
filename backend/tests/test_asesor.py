import pytest

from app.schemas.reports import AsesorFilters
from app.services.por_asesor.por_asesor import getAsesorDetail, getAsesorReport


# ─────────────────────────────────────────────
# KNOWN VALUES FROM SEED (see por_asesor.sql)
# ─────────────────────────────────────────────
ANA_REVENUE = 5000.0
CARLOS_REVENUE = 5400.0
LUCIA_REVENUE = 1200.0
TOTAL_REVENUE_2025 = 11600.0

ANA_EXAM_BREAKDOWN = {"A1 STARTERS": 5}
CARLOS_EXAM_BREAKDOWN = {"PET": 4}
LUCIA_EXAM_BREAKDOWN = {"PET": 1}


# ─────────────────────────────────────────────
# SECTION 1 — Summary report
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_summary_returns_expected_sellers_and_year(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2025))

    assert result.year == 2025
    assert result.has_more is False
    assert result.next_cursor is None
    assert [row.seller_name for row in result.rows] == [
        "Carlos Rodriguez",
        "Ana Garcia",
        "Lucia Rios",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_summary_returns_expected_revenue_per_seller(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2025))

    by_name = {row.seller_name: row for row in result.rows}
    assert by_name["Ana Garcia"].total_revenue == ANA_REVENUE
    assert by_name["Carlos Rodriguez"].total_revenue == CARLOS_REVENUE
    assert by_name["Lucia Rios"].total_revenue == LUCIA_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_summary_normalizes_exam_labels_per_seller(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2025))

    by_name = {row.seller_name: row for row in result.rows}
    assert by_name["Ana Garcia"].exam_breakdown == ANA_EXAM_BREAKDOWN
    assert by_name["Carlos Rodriguez"].exam_breakdown == CARLOS_EXAM_BREAKDOWN
    assert by_name["Lucia Rios"].exam_breakdown == LUCIA_EXAM_BREAKDOWN


@pytest.mark.asyncio(loop_scope="session")
async def test_summary_returns_expected_business_status_counts(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2025))

    by_name = {row.seller_name: row for row in result.rows}
    assert (by_name["Ana Garcia"].ganados, by_name["Ana Garcia"].perdidos, by_name["Ana Garcia"].mantenidos) == (1, 0, 1)
    assert (by_name["Carlos Rodriguez"].ganados, by_name["Carlos Rodriguez"].perdidos, by_name["Carlos Rodriguez"].mantenidos) == (1, 1, 0)
    assert (by_name["Lucia Rios"].ganados, by_name["Lucia Rios"].perdidos, by_name["Lucia Rios"].mantenidos) == (1, 0, 0)


# ─────────────────────────────────────────────
# SECTION 2 — Filters
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_country_filter_mexico_returns_only_ana(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2025, countries=["mexico"]))

    assert len(result.rows) == 1
    assert result.rows[0].seller_name == "Ana Garcia"
    assert result.rows[0].total_revenue == ANA_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_country_filter_colombia_returns_only_carlos(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2025, countries=["colombia"]))

    assert len(result.rows) == 1
    assert result.rows[0].seller_name == "Carlos Rodriguez"
    assert result.rows[0].total_revenue == CARLOS_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_seller_filter_returns_only_selected_seller(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2025, sellers=["Lucia Rios"]))

    assert len(result.rows) == 1
    assert result.rows[0].seller_name == "Lucia Rios"
    assert result.rows[0].exam_breakdown == LUCIA_EXAM_BREAKDOWN


@pytest.mark.asyncio(loop_scope="session")
async def test_nonexistent_country_returns_empty_rows(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2025, countries=["argentina"]))
    assert result.rows == []
    assert result.has_more is False
    assert result.next_cursor is None


@pytest.mark.asyncio(loop_scope="session")
async def test_summary_cursor_pagination_returns_next_cursor(por_asesor_db):
    first_page = await getAsesorReport(AsesorFilters(year=2025, limit=2))

    assert [row.seller_name for row in first_page.rows] == [
        "Carlos Rodriguez",
        "Ana Garcia",
    ]
    assert first_page.has_more is True
    assert first_page.next_cursor is not None

    second_page = await getAsesorReport(
        AsesorFilters(year=2025, limit=2, cursor=first_page.next_cursor)
    )

    assert [row.seller_name for row in second_page.rows] == ["Lucia Rios"]
    assert second_page.has_more is False
    assert second_page.next_cursor is None


# ─────────────────────────────────────────────
# SECTION 3 — Exclusions
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_deleted_cart_and_deleted_cart_product_are_excluded(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2025))
    total_revenue = sum(row.total_revenue for row in result.rows)

    assert total_revenue == TOTAL_REVENUE_2025
    assert total_revenue != TOTAL_REVENUE_2025 + 1300.0
    assert result.rows[0].total_revenue == CARLOS_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_prior_year_cart_is_excluded_by_year_filter(por_asesor_db):
    result = await getAsesorReport(AsesorFilters(year=2024))

    assert len(result.rows) == 1
    assert result.rows[0].seller_name == "Ana Garcia"
    assert result.rows[0].total_revenue == 1000.0


# ─────────────────────────────────────────────
# SECTION 4 — Detail report
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_detail_returns_expected_aggregates_for_ana(por_asesor_db):
    result = await getAsesorDetail(1, AsesorFilters(year=2025))

    assert result.seller_name == "Ana Garcia"
    assert result.countries == ["mexico"]
    assert result.zones == ["IH Mexico"]
    assert result.states == ["CDMX", "Jalisco"]
    assert result.cities == ["Guadalajara", "Mexico City"]
    assert result.total_schools == 2
    assert result.total_exams == 6
    assert result.total_revenue == ANA_REVENUE
    assert result.exam_breakdown["A1 STARTERS"].model_dump() == {
        "exams": 5,
        "schools": 2,
        "revenue": 4700.0,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_returns_expected_status_breakdown_for_carlos(por_asesor_db):
    result = await getAsesorDetail(2, AsesorFilters(year=2025))

    assert result.seller_name == "Carlos Rodriguez"
    assert result.total_schools == 2
    assert result.total_exams == 5
    assert result.total_revenue == CARLOS_REVENUE
    assert {name: detail.model_dump() for name, detail in result.exam_breakdown.items()} == {
        "PET": {
            "exams": 4,
            "schools": 2,
            "revenue": 4800.0,
        }
    }
    assert result.ganados.model_dump() == {"schools": 1, "exams": 1, "revenue": 1200.0}
    assert result.perdidos.model_dump() == {"schools": 1, "exams": 4, "revenue": 4200.0}
    assert result.mantenidos.model_dump() == {"schools": 0, "exams": 0, "revenue": 0.0}


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_geo_filters_reduce_results(por_asesor_db):
    result = await getAsesorDetail(
        2,
        AsesorFilters(year=2025, states=["Antioquia"], cities=["Medellin"]),
    )

    assert result.seller_name == "Carlos Rodriguez"
    assert result.countries == ["colombia"]
    assert result.states == ["Antioquia"]
    assert result.cities == ["Medellin"]
    assert result.total_schools == 1
    assert result.total_exams == 1
    assert result.total_revenue == 1200.0
    assert result.exam_breakdown["PET"].model_dump() == {
        "exams": 1,
        "schools": 1,
        "revenue": 1200.0,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_for_year_with_no_matching_rows_returns_zeros(por_asesor_db):
    result = await getAsesorDetail(3, AsesorFilters(year=2024))

    assert result.seller_name == "Lucia Rios"
    assert result.countries == []
    assert result.zones == []
    assert result.states == []
    assert result.cities == []
    assert result.total_schools == 0
    assert result.total_exams == 0
    assert result.total_revenue == 0.0
    assert result.exam_breakdown == {}
    assert result.ganados.model_dump() == {"schools": 0, "exams": 0, "revenue": 0.0}
