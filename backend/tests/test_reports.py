import pytest
from app.services.total_sales.total_sales import getTotalSalesData
from app.schemas.reports import ReportFilters

# ─────────────────────────────────────────────
# KNOWN VALUES FROM SEED (see ventas_totales.sql)
# ─────────────────────────────────────────────
TOTAL_REVENUE      = 7400.0
TOTAL_COST         = 3500.0
MEXICO_REVENUE     = 3900.0
COLOMBIA_REVENUE   = 3500.0
EXAM_REVENUE       = 6000.0
BOOK_REVENUE       = 900.0
COURSE_REVENUE     = 500.0
TOTAL_EXAMS        = 6
TOTAL_BOOKS        = 3
TOTAL_COURSES      = 1
TOTAL_CLIENTS      = 3
PROFIT_MARGIN      = (TOTAL_REVENUE - TOTAL_COST) / TOTAL_REVENUE * 100


JAN_FEB_REVENUE    = 5800.0

JAN_ONLY_REVENUE   = 2300.0


# ─────────────────────────────────────────────
# SECTION 1 — Basic aggregation
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_no_filters_returns_all_data(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    assert result.total_clients == TOTAL_CLIENTS
    assert result.total_revenue == TOTAL_REVENUE
    assert result.total_exams == TOTAL_EXAMS
    assert result.total_books == TOTAL_BOOKS
    assert result.total_courses == TOTAL_COURSES


@pytest.mark.asyncio(loop_scope="session")
async def test_revenue_breakdown_by_product_type(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    assert result.exam_revenue == EXAM_REVENUE
    assert result.book_revenue == BOOK_REVENUE
    assert result.course_revenue == COURSE_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_product_revenues_sum_to_total(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    combined = result.exam_revenue + result.book_revenue + result.course_revenue
    assert abs(combined - result.total_revenue) < 0.01


@pytest.mark.asyncio(loop_scope="session")
async def test_profit_margin_calculation(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    assert abs(result.profit_margin - PROFIT_MARGIN) < 0.1


@pytest.mark.asyncio(loop_scope="session")
async def test_profit_margin_between_0_and_100(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    assert 0 <= result.profit_margin <= 100


# ─────────────────────────────────────────────
# SECTION 2 — Country filter
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_mexico_filter(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters(countries=["mexico"]))
    assert result.total_revenue == MEXICO_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_colombia_filter(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters(countries=["colombia"]))
    assert result.total_revenue == COLOMBIA_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_countries_sum_equals_total(ventas_totales_db):
    mexico = await getTotalSalesData(ReportFilters(countries=["mexico"]))
    colombia = await getTotalSalesData(ReportFilters(countries=["colombia"]))
    combined = mexico.total_revenue + colombia.total_revenue
    assert abs(combined - TOTAL_REVENUE) < 0.01


@pytest.mark.asyncio(loop_scope="session")
async def test_nonexistent_country_returns_zeros(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters(countries=["peru"]))
    assert result.total_revenue == 0
    assert result.total_clients == 0
    assert result.total_exams == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_country_filter_less_than_total(ventas_totales_db):
    total = await getTotalSalesData(ReportFilters())
    mexico = await getTotalSalesData(ReportFilters(countries=["mexico"]))
    assert mexico.total_revenue < total.total_revenue


# ─────────────────────────────────────────────
# SECTION 3 — Date range filter
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_date_range_jan_to_feb(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters(
        date_from="2025-01-01",
        date_to="2025-02-28"
    ))
    assert result.total_revenue == JAN_FEB_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_date_range_jan_only(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters(
        date_from="2025-01-01",
        date_to="2025-01-31"
    ))
    assert result.total_revenue == JAN_ONLY_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_future_date_range_returns_zeros(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters(
        date_from="2030-01-01",
        date_to="2030-12-31"
    ))
    assert result.total_revenue == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_date_range_reduces_results(ventas_totales_db):
    total = await getTotalSalesData(ReportFilters())
    filtered = await getTotalSalesData(ReportFilters(
        date_from="2025-01-01",
        date_to="2025-01-31"
    ))
    assert filtered.total_revenue < total.total_revenue


# ─────────────────────────────────────────────
# SECTION 4 — Deleted cart exclusion
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_deleted_cart_excluded_from_revenue(ventas_totales_db):
    # cart 5 is deleted with 1000 revenue — total must NOT include it
    result = await getTotalSalesData(ReportFilters())
    assert result.total_revenue == TOTAL_REVENUE  # 7400, not 8400


@pytest.mark.asyncio(loop_scope="session")
async def test_deleted_cart_excluded_from_exam_count(ventas_totales_db):
    # cart 5 has 1 exam — total exams must NOT include it
    result = await getTotalSalesData(ReportFilters())
    assert result.total_exams == TOTAL_EXAMS  # 6, not 7


# ─────────────────────────────────────────────
# SECTION 5 — JOIN multiplication
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_no_revenue_duplication(ventas_totales_db):
    # if JOIN multiplication occurs, revenue will be higher than expected
    result = await getTotalSalesData(ReportFilters())
    assert result.total_revenue == TOTAL_REVENUE


@pytest.mark.asyncio(loop_scope="session")
async def test_client_count_not_duplicated(ventas_totales_db):
    # COUNT(DISTINCT lead.id) — must be 3 not higher
    result = await getTotalSalesData(ReportFilters())
    assert result.total_clients == TOTAL_CLIENTS


# ─────────────────────────────────────────────
# SECTION 6 — Product mix
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_product_mix_percentages_sum_to_100(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    assert result.product_mix is not None
    total_pct = result.product_mix.exams_pct + result.product_mix.books_pct + result.product_mix.courses_pct
    assert abs(total_pct - 100.0) < 0.2


@pytest.mark.asyncio(loop_scope="session")
async def test_product_mix_is_none_when_no_revenue(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters(countries=["peru"]))
    assert result.product_mix is None


@pytest.mark.asyncio(loop_scope="session")
async def test_product_mix_exam_dominant(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    assert result.product_mix is not None
    assert result.product_mix.exams_pct > result.product_mix.books_pct
    assert result.product_mix.exams_pct > result.product_mix.courses_pct


# ─────────────────────────────────────────────
# SECTION 7 — Trend points
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_trend_points_in_chronological_order(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    months = [p.month for p in result.trend_points]
    assert months == sorted(months)


@pytest.mark.asyncio(loop_scope="session")
async def test_trend_points_valid_format(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    for point in result.trend_points:
        assert len(point.month) == 7       # YYYY-MM
        assert point.month[4] == "-"
        assert point.revenue >= 0


@pytest.mark.asyncio(loop_scope="session")
async def test_trend_points_revenue_sum_equals_total(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    trend_sum = sum(p.revenue for p in result.trend_points)
    assert abs(trend_sum - result.total_revenue) < 0.01


# ─────────────────────────────────────────────
# SECTION 8 — Geo points
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_geo_points_cover_all_countries(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    dimensions = {p.dimension for p in result.geo_points}
    assert "mexico" in dimensions
    assert "colombia" in dimensions


@pytest.mark.asyncio(loop_scope="session")
async def test_geo_points_revenue_sum_equals_total(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    geo_sum = sum(p.revenue for p in result.geo_points)
    assert abs(geo_sum - result.total_revenue) < 0.01


@pytest.mark.asyncio(loop_scope="session")
async def test_geo_points_all_non_negative(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    for point in result.geo_points:
        assert point.revenue >= 0


# ─────────────────────────────────────────────
# SECTION 9 — Prior year
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_prior_year_not_populated_without_dates(ventas_totales_db):
    result = await getTotalSalesData(ReportFilters())
    assert result.prior_year_revenue == 0
    assert result.growth_pct == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_prior_year_populated_with_dates(ventas_totales_db):
    # 2025 jan data exists, 2024 jan has no data → prior = 0, growth = 0
    result = await getTotalSalesData(ReportFilters(
        date_from="2025-01-01",
        date_to="2025-01-31"
    ))
    assert result.prior_year_revenue == 0  # no 2024 jan data


@pytest.mark.asyncio(loop_scope="session")
async def test_prior_year_with_existing_data(ventas_totales_db):
    # 2025 jan data: 2300
    # 2024 dec data: 600 → shift dec 2025 back = dec 2024 = 600
    result = await getTotalSalesData(ReportFilters(
        date_from="2025-12-01",
        date_to="2025-12-31"
    ))
    # no 2025 dec data so current = 0, prior (2024 dec) = 600
    assert result.prior_year_revenue == TOTAL_REVENUE - (MEXICO_REVENUE - 600.0) - COLOMBIA_REVENUE