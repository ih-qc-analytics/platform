import pytest

from app.schemas.reports import PorPaisFilters
from app.services.por_pais.por_pais import get_por_pais_detail, get_por_pais_report


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_full_year_summary_and_status_rows_match_payment_based_model(
    ui_dev_reporting_db,
):
    result = await get_por_pais_report(
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )

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
            "total_books": 0,
            "total_courses": 1,
            "exam_revenue": 6500.0,
            "book_revenue": 0.0,
            "course_revenue": 600.0,
        },
        {
            "country": "mexico",
            "total_schools": 3,
            "total_revenue": 6700.0,
            "uncategorized_revenue": 0.0,
            "cambridge": 5,
            "ielts": 0,
            "michigan": 0,
            "tea": 0,
            "other": 1,
            "total_books": 2,
            "total_courses": 0,
            "exam_revenue": 5600.0,
            "book_revenue": 600.0,
            "course_revenue": 0.0,
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
            "total_books": 0,
            "total_courses": 0,
            "exam_revenue": 1700.0,
            "book_revenue": 0.0,
            "course_revenue": 0.0,
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
            "books_courses_ganados": 1,
            "books_courses_perdidos": 0,
            "books_courses_mantenidos": 0,
        },
        {
            "country": "mexico",
            "schools_ganados": 2,
            "schools_perdidos": 0,
            "schools_mantenidos": 1,
            "exams_ganados": 2,
            "exams_perdidos": 0,
            "exams_mantenidos": 4,
            "books_courses_ganados": 2,
            "books_courses_perdidos": 0,
            "books_courses_mantenidos": 0,
        },
        {
            "country": "peru",
            "schools_ganados": 0,
            "schools_perdidos": 0,
            "schools_mantenidos": 1,
            "exams_ganados": 0,
            "exams_perdidos": 0,
            "exams_mantenidos": 1,
            "books_courses_ganados": 0,
            "books_courses_perdidos": 0,
            "books_courses_mantenidos": 0,
        },
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_detail_returns_canonical_exam_counts_per_country(ui_dev_reporting_db):
    mexico = await get_por_pais_detail(
        "mexico",
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31"),
    )
    colombia = await get_por_pais_detail(
        "colombia",
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31"),
    )

    assert mexico.exam_counts["A2 Key"] == 2
    assert mexico.exam_counts["B1 Preliminary"] == 2
    assert mexico.exam_counts["TKT"] == 1
    assert mexico.exam_counts["Other"] == 1

    assert colombia.exam_counts["B2 First"] == 2
    assert colombia.exam_counts["MET"] == 1
    assert colombia.exam_counts["TEA"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_detail_returns_product_revenue_breakdown(ui_dev_reporting_db):
    mexico = await get_por_pais_detail(
        "mexico",
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31"),
    )
    colombia = await get_por_pais_detail(
        "colombia",
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31"),
    )

    # Mexico: exam revenue excludes the books (600) → 5600, and has 2 books
    assert mexico.exam_revenue == 5600.0
    assert mexico.book_revenue == 600.0
    assert mexico.course_revenue == 0.0
    assert mexico.total_books == 2
    assert mexico.total_courses == 0

    # Colombia: has 1 course (600) → exam_revenue = total - course = 6500
    assert colombia.exam_revenue == 6500.0
    assert colombia.book_revenue == 0.0
    assert colombia.course_revenue == 600.0
    assert colombia.total_books == 0
    assert colombia.total_courses == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_detail_comparison_includes_exam_revenue(ui_dev_reporting_db):
    result = await get_por_pais_detail(
        "colombia",
        PorPaisFilters(
            date_from="2025-05-01",
            date_to="2025-12-31",
            show_comparison=True,
            comparison_mode="PREVIOUS_PERIOD",
            comparison_date_from="2025-01-01",
            comparison_date_to="2025-04-30",
        ),
    )

    assert result.exam_revenue > 0
    assert result.comparison_exam_revenue is not None
    assert result.comparison_book_revenue == 0.0
    assert (
        result.comparison_course_revenue == 600.0
    )  # course payment date 2025-04-02 falls in comparison period


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_midyear_range_status_rows_use_comparison_period(ui_dev_reporting_db):
    result = await get_por_pais_report(
        PorPaisFilters(date_from="2025-05-01", date_to="2025-08-31", show_comparison=True)
    )

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
            "total_books": 0,
            "total_courses": 0,
            "exam_revenue": 3500.0,
            "book_revenue": 0.0,
            "course_revenue": 0.0,
        },
        {
            "country": "mexico",
            "total_schools": 1,
            "total_revenue": 1000.0,
            "uncategorized_revenue": 0.0,
            "cambridge": 0,
            "ielts": 0,
            "michigan": 0,
            "tea": 0,
            "other": 1,
            "total_books": 0,
            "total_courses": 0,
            "exam_revenue": 500.0,
            "book_revenue": 0.0,
            "course_revenue": 0.0,
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
            "total_books": 0,
            "total_courses": 0,
            "exam_revenue": 1700.0,
            "book_revenue": 0.0,
            "course_revenue": 0.0,
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
            "books_courses_ganados": 0,
            "books_courses_perdidos": 0,
            "books_courses_mantenidos": 0,
        },
        {
            "country": "mexico",
            "schools_ganados": 1,
            "schools_perdidos": 1,
            "schools_mantenidos": 0,
            "exams_ganados": 1,
            "exams_perdidos": 1,
            "exams_mantenidos": 0,
            "books_courses_ganados": 0,
            "books_courses_perdidos": 0,
            "books_courses_mantenidos": 0,
        },
        {
            "country": "peru",
            "schools_ganados": 1,
            "schools_perdidos": 0,
            "schools_mantenidos": 0,
            "exams_ganados": 1,
            "exams_perdidos": 0,
            "exams_mantenidos": 0,
            "books_courses_ganados": 0,
            "books_courses_perdidos": 0,
            "books_courses_mantenidos": 0,
        },
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_empty_range_returns_empty_sections(ui_dev_reporting_db):
    result = await get_por_pais_report(PorPaisFilters(date_from="2030-01-01", date_to="2030-12-31"))

    assert result.current.summary_rows == []
    assert result.current.status_rows == []


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_full_year_status_rows_include_books_courses_gpm(ui_dev_reporting_db):
    # Full year 2025 vs previous year 2024 (no books/courses in 2024 seed data)
    result = await get_por_pais_report(
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )

    status_by_country = {row.country: row for row in result.current.status_rows}

    # Colombia has 1 course school in 2025 (none in 2024) → bc_ganado=1
    assert status_by_country["colombia"].books_courses_ganados == 1
    assert status_by_country["colombia"].books_courses_perdidos == 0
    assert status_by_country["colombia"].books_courses_mantenidos == 0

    # Mexico has 2 book schools in 2025 (leadId=1 and leadId=2, neither in 2024) → bc_ganado=2
    assert status_by_country["mexico"].books_courses_ganados == 2
    assert status_by_country["mexico"].books_courses_perdidos == 0
    assert status_by_country["mexico"].books_courses_mantenidos == 0

    # Peru has no books/courses in 2025
    assert status_by_country["peru"].books_courses_ganados == 0
    assert status_by_country["peru"].books_courses_perdidos == 0
    assert status_by_country["peru"].books_courses_mantenidos == 0
