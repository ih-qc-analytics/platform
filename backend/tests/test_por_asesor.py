import pytest

from app.schemas.reports import AsesorFilters
from app.services.por_asesor.por_asesor import get_asesor_detail, get_asesor_report


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_2025_summary_orders_sellers_by_payment_revenue(ui_dev_reporting_db):
    result = await get_asesor_report(AsesorFilters(date_from="2025-01-01", date_to="2025-12-31"))

    assert [row.seller_name for row in result.current.rows] == [
        "Carlos Rodriguez",
        "Ana Garcia",
        "Lucia Rios",
        "Miguel Torres",
    ]
    assert [row.total_revenue for row in result.current.rows] == [7100.0, 4400.0, 1700.0, 1000.0]


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_2025_summary_uses_allocated_exam_breakdowns_and_payment_status_sets(
    ui_dev_reporting_db,
):
    result = await get_asesor_report(
        AsesorFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )
    by_name = {row.seller_name: row for row in result.current.rows}

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
        "uncategorized_revenue": 0.0,
        "total_revenue": 7100.0,
        "total_books": 0,
        "total_courses": 1,
        "exam_revenue": 6500.0,
        "book_revenue": 0.0,
        "course_revenue": 600.0,
        "books_courses_ganados": 1,
        "books_courses_perdidos": 0,
        "books_courses_mantenidos": 0,
        "allocated_revenue": 7100.0,
        "expected_revenue": 7100.0,
        "expected_cost": 3450.0,
        "profit_margin": pytest.approx(51.408, abs=0.01),
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
        "uncategorized_revenue": 0.0,
        "total_revenue": 4400.0,
        "total_books": 1,
        "total_courses": 0,
        "exam_revenue": 4100.0,
        "book_revenue": 300.0,
        "course_revenue": 0.0,
        "books_courses_ganados": 1,
        "books_courses_perdidos": 0,
        "books_courses_mantenidos": 0,
        "allocated_revenue": 4400.0,
        "expected_revenue": 4400.0,
        "expected_cost": 2150.0,
        "profit_margin": pytest.approx(51.136, abs=0.01),
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_2024_summary_uses_prior_year_payment_presence(ui_dev_reporting_db):
    result = await get_asesor_report(AsesorFilters(date_from="2024-01-01", date_to="2024-12-31"))

    assert [row.seller_name for row in result.current.rows] == [
        "Lucia Rios",
        "Carlos Rodriguez",
        "Ana Garcia",
    ]
    assert [row.total_revenue for row in result.current.rows] == [1700.0, 1300.0, 1000.0]


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_supports_pagination(ui_dev_reporting_db):
    first_page = await get_asesor_report(
        AsesorFilters(date_from="2025-01-01", date_to="2025-12-31", limit=2)
    )
    second_page = await get_asesor_report(
        AsesorFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            limit=2,
            cursor=first_page.current.next_cursor,
        )
    )

    assert [row.seller_name for row in first_page.current.rows] == [
        "Carlos Rodriguez",
        "Ana Garcia",
    ]
    assert first_page.current.has_more is True
    assert first_page.current.next_cursor is not None

    assert [row.seller_name for row in second_page.current.rows] == [
        "Lucia Rios",
        "Miguel Torres",
    ]
    assert second_page.current.has_more is False
    assert second_page.current.next_cursor is None


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_supports_seller_country_and_zone_filters(ui_dev_reporting_db):
    result = await get_asesor_report(
        AsesorFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            sellers=["Carlos Rodriguez"],
            countries=["colombia"],
            zones=["IH Colombia"],
        )
    )

    assert len(result.current.rows) == 1
    assert result.current.rows[0].seller_name == "Carlos Rodriguez"
    assert result.current.rows[0].total_revenue == 7100.0


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_ana_matches_expected_paid_geo_breakdown_and_statuses(
    ui_dev_reporting_db,
):
    result = await get_asesor_detail(
        1, AsesorFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )

    assert result.current.model_dump() == {
        "seller_name": "Ana Garcia",
        "countries": ["mexico"],
        "zones": ["IH Mexico"],
        "states": ["CDMX", "Jalisco"],
        "cities": ["Guadalajara", "Mexico City"],
        "total_schools": 2,
        "total_exams": 4,
        "uncategorized_revenue": 0.0,
        "total_revenue": 4400.0,
        "exam_breakdown": {
            "Cambridge English (Main Suite)": {"exams": 3, "schools": 2, "revenue": 3200.0},
            "Cambridge Teaching & Skills": {"exams": 1, "schools": 1, "revenue": 900.0},
            "IELTS": {"exams": 0, "schools": 0, "revenue": 0.0},
            "Michigan (MET)": {"exams": 0, "schools": 0, "revenue": 0.0},
            "TEA (Test of English for Aviation)": {"exams": 0, "schools": 0, "revenue": 0.0},
            "Placement & Otros": {"exams": 0, "schools": 0, "revenue": 0.0},
        },
        "ganados": {"schools": 1, "exams": 1, "books": 1, "courses": 0, "revenue": 1500.0},
        "perdidos": {"schools": 0, "exams": 0, "books": 0, "courses": 0, "revenue": 0.0},
        "mantenidos": {"schools": 1, "exams": 3, "books": 0, "courses": 0, "revenue": 2900.0},
        "total_books": 1,
        "total_courses": 0,
        "book_revenue": 300.0,
        "course_revenue": 0.0,
        "allocated_revenue": 4400.0,
        "expected_revenue": 4400.0,
        "expected_cost": 2150.0,
        "profit_margin": pytest.approx(51.136, abs=0.01),
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_carlos_matches_expected_paid_geo_breakdown_and_statuses(
    ui_dev_reporting_db,
):
    result = await get_asesor_detail(
        2, AsesorFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )

    assert result.current.model_dump() == {
        "seller_name": "Carlos Rodriguez",
        "countries": ["colombia"],
        "zones": ["IH Colombia"],
        "states": ["Antioquia", "Bogota"],
        "cities": ["Bogota", "Medellin"],
        "total_schools": 2,
        "total_exams": 5,
        "uncategorized_revenue": 0.0,
        "total_revenue": 7100.0,
        "exam_breakdown": {
            "Cambridge English (Main Suite)": {"exams": 2, "schools": 1, "revenue": 3000.0},
            "Cambridge Teaching & Skills": {"exams": 0, "schools": 0, "revenue": 0.0},
            "IELTS": {"exams": 0, "schools": 0, "revenue": 0.0},
            "Michigan (MET)": {"exams": 1, "schools": 1, "revenue": 1300.0},
            "TEA (Test of English for Aviation)": {"exams": 2, "schools": 1, "revenue": 2200.0},
            "Placement & Otros": {"exams": 0, "schools": 0, "revenue": 0.0},
        },
        "ganados": {"schools": 1, "exams": 3, "books": 0, "courses": 0, "revenue": 3500.0},
        "perdidos": {"schools": 0, "exams": 0, "books": 0, "courses": 0, "revenue": 0.0},
        "mantenidos": {"schools": 1, "exams": 2, "books": 0, "courses": 1, "revenue": 3600.0},
        "total_books": 0,
        "total_courses": 1,
        "book_revenue": 0.0,
        "course_revenue": 600.0,
        "allocated_revenue": 7100.0,
        "expected_revenue": 7100.0,
        "expected_cost": 3450.0,
        "profit_margin": pytest.approx(51.408, abs=0.01),
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_fully_allocated_sellers_reconciles_total_to_ganados_plus_mantenidos(
    ui_dev_reporting_db,
):
    for seller_id in (1, 2, 3):
        result = await get_asesor_detail(
            seller_id,
            AsesorFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True),
        )
        assert (
            result.current.total_revenue
            == result.current.ganados.revenue + result.current.mantenidos.revenue
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_miguel_keeps_unallocated_payment_gap_visible(
    ui_dev_reporting_db,
):
    result = await get_asesor_detail(
        4, AsesorFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )

    assert result.current.total_revenue == 1000.0
    assert result.current.uncategorized_revenue == 500.0
    assert result.current.ganados.revenue == 500.0
    assert result.current.total_revenue - result.current.ganados.revenue == 500.0
    assert result.current.exam_breakdown["Placement & Otros"].model_dump() == {
        "exams": 1,
        "schools": 1,
        "revenue": 500.0,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_for_year_with_no_rows_returns_zero_breakdowns(ui_dev_reporting_db):
    result = await get_asesor_detail(4, AsesorFilters(date_from="2024-01-01", date_to="2024-12-31"))

    assert result.current.seller_name == "Miguel Torres"
    assert result.current.countries == []
    assert result.current.zones == []
    assert result.current.states == []
    assert result.current.cities == []
    assert result.current.total_schools == 0
    assert result.current.total_exams == 0
    assert result.current.uncategorized_revenue == 0.0
    assert result.current.total_revenue == 0.0
    assert result.current.ganados.model_dump() == {
        "schools": 0,
        "exams": 0,
        "books": 0,
        "courses": 0,
        "revenue": 0.0,
    }
    assert result.current.perdidos.model_dump() == {
        "schools": 0,
        "exams": 0,
        "books": 0,
        "courses": 0,
        "revenue": 0.0,
    }
    assert result.current.mantenidos.model_dump() == {
        "schools": 0,
        "exams": 0,
        "books": 0,
        "courses": 0,
        "revenue": 0.0,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_books_courses_gpm_counts(ui_dev_reporting_db):
    # Full year 2025 vs previous year 2024 (no books/courses in 2024 seed data)
    result = await get_asesor_report(
        AsesorFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )
    by_name = {row.seller_name: row for row in result.current.rows}

    # Carlos has 1 course school in 2025 (cart 7, colombia lead 3 = Prep Course) — not in 2024
    assert by_name["Carlos Rodriguez"].books_courses_ganados == 1
    assert by_name["Carlos Rodriguez"].books_courses_perdidos == 0
    assert by_name["Carlos Rodriguez"].books_courses_mantenidos == 0

    # Ana has 1 book school in 2025 — not in 2024
    assert by_name["Ana Garcia"].books_courses_ganados == 1
    assert by_name["Ana Garcia"].books_courses_perdidos == 0
    assert by_name["Ana Garcia"].books_courses_mantenidos == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_status_tiles_include_books_and_courses_counts(ui_dev_reporting_db):
    # Carlos (seller_id=2) has 1 course in mantenidos schools
    carlos = await get_asesor_detail(
        2, AsesorFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )
    # Sum of books/courses across all statuses must match totals
    total_books = (
        carlos.current.ganados.books
        + carlos.current.perdidos.books
        + carlos.current.mantenidos.books
    )
    total_courses = (
        carlos.current.ganados.courses
        + carlos.current.perdidos.courses
        + carlos.current.mantenidos.courses
    )
    assert total_books == carlos.current.total_books  # 0
    assert total_courses == carlos.current.total_courses  # 1

    # Ana (seller_id=1) has 1 book in ganados schools
    ana = await get_asesor_detail(
        1, AsesorFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )
    total_books_ana = (
        ana.current.ganados.books + ana.current.perdidos.books + ana.current.mantenidos.books
    )
    total_courses_ana = (
        ana.current.ganados.courses + ana.current.perdidos.courses + ana.current.mantenidos.courses
    )
    assert total_books_ana == ana.current.total_books  # 1
    assert total_courses_ana == ana.current.total_courses  # 0


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_profit_margin_matches_formula(ui_dev_reporting_db):
    result = await get_asesor_report(AsesorFilters(date_from="2025-01-01", date_to="2025-12-31"))
    by_name = {row.seller_name: row for row in result.current.rows}

    # Margin = (allocated_revenue - cost) / allocated_revenue * 100
    for row in result.current.rows:
        if row.allocated_revenue > 0:
            expected = (row.allocated_revenue - row.expected_cost) / row.allocated_revenue * 100
            assert row.profit_margin == pytest.approx(expected, abs=0.001)
        else:
            assert row.profit_margin == 0.0

    # Concrete values from seed data
    assert by_name["Carlos Rodriguez"].expected_cost == 3450.0
    assert by_name["Carlos Rodriguez"].profit_margin == pytest.approx(
        (7100.0 - 3450.0) / 7100.0 * 100, abs=0.01
    )
    assert by_name["Ana Garcia"].expected_cost == 2150.0
    assert by_name["Ana Garcia"].profit_margin == pytest.approx(
        (4400.0 - 2150.0) / 4400.0 * 100, abs=0.01
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_profit_margin_matches_formula(ui_dev_reporting_db):
    result = await get_asesor_detail(1, AsesorFilters(date_from="2025-01-01", date_to="2025-12-31"))
    detail = result.current

    assert detail.expected_cost == 2150.0
    assert detail.profit_margin == pytest.approx(
        (detail.allocated_revenue - detail.expected_cost) / detail.allocated_revenue * 100,
        abs=0.001,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_detail_zero_revenue_yields_zero_margin(ui_dev_reporting_db):
    # Miguel Torres has no activity in 2024 — total_revenue is 0
    result = await get_asesor_detail(4, AsesorFilters(date_from="2024-01-01", date_to="2024-12-31"))

    assert result.current.total_revenue == 0.0
    assert result.current.expected_cost == 0.0
    assert result.current.profit_margin == 0.0


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_default_sort_is_total_revenue_desc(ui_dev_reporting_db):
    result = await get_asesor_report(AsesorFilters(date_from="2025-01-01", date_to="2025-12-31"))

    revenues = [row.total_revenue for row in result.current.rows]
    assert revenues == sorted(revenues, reverse=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_sort_by_seller_name_asc(ui_dev_reporting_db):
    result = await get_asesor_report(
        AsesorFilters(
            date_from="2025-01-01", date_to="2025-12-31", sort_by="seller_name", sort_dir="asc"
        )
    )

    names = [row.seller_name for row in result.current.rows]
    assert names == sorted(names)


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_sort_by_profit_margin_desc(ui_dev_reporting_db):
    result = await get_asesor_report(
        AsesorFilters(
            date_from="2025-01-01", date_to="2025-12-31", sort_by="profit_margin", sort_dir="desc"
        )
    )

    margins = [row.profit_margin for row in result.current.rows]
    assert margins == sorted(margins, reverse=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_summary_sort_pagination_stable(ui_dev_reporting_db):
    """Paginating under a non-default sort yields no duplicates and full coverage."""
    all_seller_ids: list[int] = []
    cursor = None
    while True:
        page = await get_asesor_report(
            AsesorFilters(
                date_from="2025-01-01",
                date_to="2025-12-31",
                sort_by="seller_name",
                sort_dir="asc",
                limit=2,
                cursor=cursor,
            )
        )
        all_seller_ids.extend(row.seller_id for row in page.current.rows)
        if not page.current.has_more or page.current.next_cursor is None:
            break
        cursor = page.current.next_cursor

    assert len(all_seller_ids) == len(set(all_seller_ids)), "Duplicate seller_ids across pages"
    assert len(all_seller_ids) == 4, "Expected all 4 sellers in 2025"
