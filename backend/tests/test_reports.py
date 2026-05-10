import pytest

from app.schemas.reports import ReportFilters
from app.services.total_sales.total_sales import getTotalSalesData


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_full_dataset_uses_payment_totals_and_allocated_breakdowns(ui_dev_db):
    result = await getTotalSalesData(ReportFilters())

    assert result.total_clients == 6
    assert result.total_revenue == 18200.0
    assert result.total_exams == 14
    assert result.exam_revenue == 16800.0
    assert result.total_books == 1
    assert result.book_revenue == 300.0
    assert result.total_courses == 1
    assert result.course_revenue == 600.0
    assert result.total_otros == 0
    assert result.otros_revenue == 0.0
    assert round(result.profit_margin, 2) == 53.02
    assert result.prior_year_revenue == 0.0
    assert result.growth_pct == 0.0
    assert result.product_mix is not None
    assert result.product_mix.model_dump() == {
        "exams_pct": 92.3,
        "books_pct": 1.6,
        "courses_pct": 3.3,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_2025_gap_between_payment_total_and_allocated_breakdown_is_preserved(ui_dev_db):
    result = await getTotalSalesData(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31")
    )

    allocated_breakdown_total = (
        result.exam_revenue
        + result.book_revenue
        + result.course_revenue
        + result.otros_revenue
    )

    assert result.total_revenue == 14200.0
    assert allocated_breakdown_total == 13700.0
    assert result.total_revenue - allocated_breakdown_total == 500.0


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_2025_excludes_pending_deleted_and_deleted_cart_product_rows(ui_dev_db):
    result = await getTotalSalesData(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31")
    )

    assert result.total_revenue == 14200.0
    assert result.total_exams == 11
    assert [point.month for point in result.trend_points] == [
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
async def test_total_sales_country_breakdowns_match_expected_2025_slices(ui_dev_db):
    mexico = await getTotalSalesData(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", countries=["mexico"])
    )
    colombia = await getTotalSalesData(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", countries=["colombia"])
    )
    peru = await getTotalSalesData(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", countries=["peru"])
    )

    assert mexico.total_revenue == 5400.0
    assert mexico.total_clients == 3
    assert mexico.total_exams == 5
    assert mexico.exam_revenue == 4600.0
    assert mexico.book_revenue == 300.0

    assert colombia.total_revenue == 7100.0
    assert colombia.total_clients == 2
    assert colombia.total_exams == 5
    assert colombia.exam_revenue == 6500.0
    assert colombia.course_revenue == 600.0

    assert peru.total_revenue == 1700.0
    assert peru.total_clients == 1
    assert peru.total_exams == 1
    assert peru.exam_revenue == 1700.0


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_state_and_city_filters_do_not_duplicate_multi_address_leads(ui_dev_db):
    by_state = await getTotalSalesData(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", states=["CDMX"])
    )
    by_city = await getTotalSalesData(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", cities=["Mexico City"])
    )

    assert by_state.total_revenue == 4400.0
    assert by_state.total_clients == 2
    assert by_state.total_exams == 4
    assert by_state.book_revenue == 300.0

    assert by_city.model_dump() == by_state.model_dump()


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_zone_filter_matches_country_parent_dimension_without_duplication(ui_dev_db):
    result = await getTotalSalesData(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", zones=["IH Mexico"])
    )

    assert result.total_revenue == 5400.0
    assert result.total_clients == 3
    assert result.total_exams == 5


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_jan_to_mar_uses_payment_date_range_and_prior_year_only_when_available(ui_dev_db):
    result = await getTotalSalesData(
        ReportFilters(date_from="2025-01-01", date_to="2025-03-31")
    )

    assert result.total_revenue == 4400.0
    assert result.total_clients == 2
    assert result.total_exams == 4
    assert result.prior_year_revenue == 0.0
    assert result.growth_pct == 0.0
    assert [point.model_dump() for point in result.trend_points] == [
        {"month": "2025-01", "revenue": 2000.0},
        {"month": "2025-02", "revenue": 1500.0},
        {"month": "2025-03", "revenue": 900.0},
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_future_empty_slice_returns_zeros_and_no_mix(ui_dev_db):
    result = await getTotalSalesData(
        ReportFilters(date_from="2030-01-01", date_to="2030-12-31")
    )

    assert result.total_revenue == 0.0
    assert result.total_clients == 0
    assert result.total_exams == 0
    assert result.total_books == 0
    assert result.total_courses == 0
    assert result.product_mix is None
    assert result.trend_points == []
    assert result.geo_points == []
