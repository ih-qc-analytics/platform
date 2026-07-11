import pytest

from app.schemas.reports import ReportFilters
from app.services.total_sales.total_sales import get_total_sales_data


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_full_dataset_uses_payment_totals_and_allocated_breakdowns(
    ui_dev_reporting_db,
):
    result = await get_total_sales_data(ReportFilters())

    assert result.current.total_clients == 6
    assert result.current.total_revenue == 18200.0
    assert result.current.total_exams == 14
    assert result.current.exam_revenue == 16800.0
    assert result.current.total_books == 1
    assert result.current.book_revenue == 300.0
    assert result.current.total_courses == 1
    assert result.current.course_revenue == 600.0
    assert result.current.total_otros == 0
    assert result.current.otros_revenue == 0.0
    assert result.current.expected_revenue >= 0.0
    assert result.current.expected_cost >= 0.0
    assert result.current.uncategorized_revenue >= 0.0
    assert result.current.unknown_site_revenue == 0.0
    assert round(result.current.profit_margin, 2) == 51.69
    assert result.comparison is None
    assert result.current.product_mix is not None
    assert result.current.product_mix.exams_pct >= 0.0
    assert result.current.product_mix.books_pct >= 0.0
    assert result.current.product_mix.courses_pct >= 0.0
    assert result.current.product_mix.unknown_pct >= 0.0


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_2025_gap_between_payment_total_and_allocated_breakdown_is_preserved(
    ui_dev_reporting_db,
):
    result = await get_total_sales_data(ReportFilters(date_from="2025-01-01", date_to="2025-12-31"))

    allocated_breakdown_total = (
        result.current.exam_revenue
        + result.current.book_revenue
        + result.current.course_revenue
        + result.current.otros_revenue
    )

    assert result.current.total_revenue == 14200.0
    assert result.current.uncategorized_revenue == pytest.approx(
        result.current.total_revenue - allocated_breakdown_total
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_2025_excludes_pending_deleted_and_deleted_cart_product_rows(
    ui_dev_reporting_db,
):
    result = await get_total_sales_data(ReportFilters(date_from="2025-01-01", date_to="2025-12-31"))

    assert result.current.total_revenue == 14200.0
    assert result.current.total_exams == 11
    assert [point.month for point in result.current.trend_points] == [
        "2025-01",
        "2025-02",
        "2025-03",
        "2025-04",
        "2025-05",
        "2025-06",
        "2025-07",
        "2025-08",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_country_breakdowns_match_expected_2025_slices(ui_dev_reporting_db):
    mexico = await get_total_sales_data(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", countries=["mexico"])
    )
    colombia = await get_total_sales_data(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", countries=["colombia"])
    )
    peru = await get_total_sales_data(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", countries=["peru"])
    )

    assert mexico.current.total_revenue == 5400.0
    assert mexico.current.total_clients == 3
    assert mexico.current.total_exams == 5
    assert mexico.current.exam_revenue == 4600.0
    assert mexico.current.book_revenue == 300.0

    assert colombia.current.total_revenue == 7100.0
    assert colombia.current.total_clients == 2
    assert colombia.current.total_exams == 5
    assert colombia.current.exam_revenue == 6500.0
    assert colombia.current.course_revenue == 600.0

    assert peru.current.total_revenue == 1700.0
    assert peru.current.total_clients == 1
    assert peru.current.total_exams == 1
    assert peru.current.exam_revenue == 1700.0


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_state_and_city_filters_do_not_duplicate_multi_address_leads(
    ui_dev_reporting_db,
):
    by_state = await get_total_sales_data(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", states=["CDMX"])
    )
    by_city = await get_total_sales_data(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", cities=["Mexico City"])
    )

    assert by_state.current.total_revenue == 4400.0
    assert by_state.current.total_clients == 2
    assert by_state.current.total_exams == 4
    assert by_state.current.book_revenue == 300.0

    assert by_city.model_dump() == by_state.model_dump()


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_zone_filter_matches_country_parent_dimension_without_duplication(
    ui_dev_reporting_db,
):
    result = await get_total_sales_data(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", zones=["IH Mexico"])
    )

    assert result.current.total_revenue == 5400.0
    assert result.current.total_clients == 3
    assert result.current.total_exams == 5


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_jan_to_mar_uses_payment_date_range_and_prior_year_only_when_available(
    ui_dev_reporting_db,
):
    result = await get_total_sales_data(ReportFilters(date_from="2025-01-01", date_to="2025-03-31"))

    assert result.current.total_revenue == 4400.0
    assert result.current.total_clients == 2
    assert result.current.total_exams == 4
    assert result.comparison is None
    assert [point.model_dump() for point in result.current.trend_points] == [
        {"month": "2025-01", "revenue": 2000.0},
        {"month": "2025-02", "revenue": 1500.0},
        {"month": "2025-03", "revenue": 900.0},
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_future_empty_slice_returns_zeros_and_no_mix(ui_dev_reporting_db):
    result = await get_total_sales_data(ReportFilters(date_from="2030-01-01", date_to="2030-12-31"))

    assert result.current.total_revenue == 0.0
    assert result.current.total_clients == 0
    assert result.current.total_exams == 0
    assert result.current.total_books == 0
    assert result.current.total_courses == 0
    assert result.current.product_mix is None
    assert result.current.trend_points == []
    assert result.current.geo_points == []
