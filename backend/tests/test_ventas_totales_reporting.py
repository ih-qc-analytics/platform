"""
Ventas Totales report query tests.

Seed rows directly into report_line_items — no Jones DB needed.
Each test cleans up via clean_reporting_db fixture.
"""
import pytest
from datetime import datetime, date
from sqlalchemy import text

from app.schemas.reports import ReportFilters
from app.services.total_sales.total_sales import getTotalSalesData
from tests.conftest_reporting import bind_test_reporting_database


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def make_row(**overrides) -> dict:
    defaults = {
        "cart_product_id":      1,
        "etl_date":             date.today(),
        "seller_id":            1,
        "seller_name":          "Ana Garcia",
        "lead_id":              1,
        "school_name":          "Colegio Test",
        "site":                 "mexico",
        "zone_name":            "IH Mexico",
        "state_name":           "CDMX",
        "city":                 "Ciudad de Mexico",
        "business_status":      "ganado",
        "cart_id":              1,
        "created_at":           datetime(2025, 1, 15),
        "year":                 2025,
        "month":                1,
        "payment_status":       "Aprobado",
        "payment_date":         date(2025, 1, 16),
        "billing_status":       "Aprobado",
        "product_id":           1,
        "product_type":         "exam",
        "exam_cat_name":        "KET",
        "exam_category":        "Cambridge English (Main Suite)",
        "exam_canonical_name":  "A2 Key",
        "exam_date_type":       "fixed",
        "quantity":             5,
        "total":                5000.00,
        "cost":                 2000.00,
        "discount":             0,
        "book_commission":      0,
        "exam_commission":      0,
        "base_currency":        "MXN",
        "total_mxn":            5000.00,
        "cost_mxn":             2000.00,
        "is_active":            True,
    }
    return {**defaults, **overrides}


async def _insert(session_factory, *rows):
    cols = list(rows[0].keys())
    col_str = ", ".join(cols)
    val_str = ", ".join(f":{c}" for c in cols)
    sql = text(f"INSERT INTO report_line_items ({col_str}) VALUES ({val_str})")
    async with session_factory() as session:
        async with session.begin():
            for row in rows:
                await session.execute(sql, row)


def _bind(session_factory):
    bind_test_reporting_database(session_factory)
    import app.services.total_sales.total_sales as svc
    svc.ReportingSessionLocal = session_factory


# ─────────────────────────────────────────────────────────────
# Basic inclusion / exclusion
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_filters_returns_all_approved_active_rows(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, lead_id=1, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, lead_id=2, total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.total_revenue == pytest.approx(3000.0)
    assert result.total_clients == 2


@pytest.mark.asyncio
async def test_inactive_rows_excluded(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, total_mxn=2000.0, cost_mxn=800.0, is_active=False),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_unapproved_payment_rows_excluded(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, total_mxn=1000.0, cost_mxn=400.0, payment_status="Aprobado"),
        make_row(cart_product_id=2, total_mxn=2000.0, cost_mxn=800.0, payment_status="Pendiente"),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.total_revenue == pytest.approx(1000.0)


# ─────────────────────────────────────────────────────────────
# Geo filters
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_country_filter_mexico_only(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico",   total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters(countries=["mexico"]))
    assert result.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_country_filter_colombia_only(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico",   total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters(countries=["colombia"]))
    assert result.total_revenue == pytest.approx(2000.0)


@pytest.mark.asyncio
async def test_two_countries_sum_correctly(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico",   total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
        make_row(cart_product_id=3, site="peru",     total_mxn=3000.0, cost_mxn=1200.0),
    )
    result = await getTotalSalesData(ReportFilters(countries=["mexico", "colombia"]))
    assert result.total_revenue == pytest.approx(3000.0)


@pytest.mark.asyncio
async def test_zone_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, zone_name="Zona Norte", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, zone_name="Zona Sur",   total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters(zones=["Zona Norte"]))
    assert result.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_state_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, state_name="CDMX",      total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, state_name="Jalisco",    total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters(states=["CDMX"]))
    assert result.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_city_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, city="CDMX",        total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, city="Guadalajara",  total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters(cities=["CDMX"]))
    assert result.total_revenue == pytest.approx(1000.0)


# ─────────────────────────────────────────────────────────────
# Date filters
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_date_from_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 1, 10), total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, created_at=datetime(2025, 2, 10), total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters(date_from="2025-02-01"))
    assert result.total_revenue == pytest.approx(2000.0)


@pytest.mark.asyncio
async def test_date_to_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 1, 10), total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, created_at=datetime(2025, 2, 10), total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters(date_to="2025-01-31"))
    assert result.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_date_range_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 1, 10), total_mxn=500.0,  cost_mxn=200.0),
        make_row(cart_product_id=2, created_at=datetime(2025, 3, 15), total_mxn=1500.0, cost_mxn=600.0),
        make_row(cart_product_id=3, created_at=datetime(2025, 6, 20), total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters(date_from="2025-02-01", date_to="2025-05-31"))
    assert result.total_revenue == pytest.approx(1500.0)


@pytest.mark.asyncio
async def test_future_date_returns_zeros(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 1, 15), total_mxn=5000.0, cost_mxn=2000.0),
    )
    result = await getTotalSalesData(ReportFilters(date_from="2099-01-01", date_to="2099-12-31"))
    assert result.total_revenue == 0.0
    assert result.total_clients == 0


# ─────────────────────────────────────────────────────────────
# Revenue by product type
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exam_revenue_calculation(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, product_type="exam", total_mxn=3000.0, cost_mxn=1200.0),
        make_row(cart_product_id=2, product_type="book", total_mxn=1000.0, cost_mxn=400.0),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.exam_revenue == pytest.approx(3000.0)
    assert result.total_exams == 5


@pytest.mark.asyncio
async def test_book_revenue_calculation(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, product_type="exam", total_mxn=3000.0, cost_mxn=1200.0),
        make_row(cart_product_id=2, product_type="book", total_mxn=1000.0, cost_mxn=400.0, quantity=2),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.book_revenue == pytest.approx(1000.0)
    assert result.total_books == 2


@pytest.mark.asyncio
async def test_course_revenue_calculation(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, product_type="course", total_mxn=4000.0, cost_mxn=1600.0, quantity=1),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.course_revenue == pytest.approx(4000.0)
    assert result.total_courses == 1


@pytest.mark.asyncio
async def test_otros_revenue_catches_uncategorized(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, product_type="UNCATEGORIZED", total_mxn=500.0, cost_mxn=200.0, quantity=1),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.otros_revenue == pytest.approx(500.0)
    assert result.total_otros == 1


@pytest.mark.asyncio
async def test_total_revenue_sum_of_all_types(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, product_type="exam",         total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, product_type="book",         total_mxn=500.0,  cost_mxn=200.0),
        make_row(cart_product_id=3, product_type="course",       total_mxn=750.0,  cost_mxn=300.0),
        make_row(cart_product_id=4, product_type="UNCATEGORIZED",total_mxn=250.0,  cost_mxn=100.0),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.total_revenue == pytest.approx(2500.0)
    assert result.exam_revenue + result.book_revenue + result.course_revenue + result.otros_revenue == pytest.approx(2500.0)


# ─────────────────────────────────────────────────────────────
# Profit margin
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_profit_margin_calculation(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, total_mxn=10000.0, cost_mxn=4000.0),
    )
    result = await getTotalSalesData(ReportFilters())
    # profit_margin = (10000 - 4000) / 10000 * 100 = 60%
    assert result.profit_margin == pytest.approx(60.0)


# ─────────────────────────────────────────────────────────────
# Client deduplication
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_total_clients_distinct_lead_ids(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, lead_id=10, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, lead_id=20, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=3, lead_id=30, total_mxn=1000.0, cost_mxn=400.0),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.total_clients == 3


@pytest.mark.asyncio
async def test_client_not_double_counted_across_products(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, lead_id=10, product_type="exam", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, lead_id=10, product_type="book", total_mxn=500.0,  cost_mxn=200.0),
    )
    result = await getTotalSalesData(ReportFilters())
    assert result.total_clients == 1  # same lead_id, counted once
    assert result.total_revenue == pytest.approx(1500.0)


# ─────────────────────────────────────────────────────────────
# Prior year / growth
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prior_year_revenue_with_date_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 3, 15), total_mxn=5000.0, cost_mxn=2000.0),
        make_row(cart_product_id=2, created_at=datetime(2024, 3, 15), total_mxn=3000.0, cost_mxn=1200.0),
    )
    result = await getTotalSalesData(ReportFilters(date_from="2025-01-01", date_to="2025-12-31"))
    assert result.total_revenue == pytest.approx(5000.0)
    assert result.prior_year_revenue == pytest.approx(3000.0)


@pytest.mark.asyncio
async def test_prior_year_revenue_absent_without_dates(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, total_mxn=5000.0, cost_mxn=2000.0),
    )
    result = await getTotalSalesData(ReportFilters())  # no date_from / date_to
    assert result.prior_year_revenue == 0.0
    assert result.growth_pct is None


@pytest.mark.asyncio
async def test_growth_pct_positive(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 1, 15), total_mxn=10000.0, cost_mxn=4000.0),
        make_row(cart_product_id=2, created_at=datetime(2024, 1, 15), total_mxn=5000.0,  cost_mxn=2000.0),
    )
    result = await getTotalSalesData(ReportFilters(date_from="2025-01-01", date_to="2025-12-31"))
    assert result.growth_pct is not None
    assert result.growth_pct == pytest.approx(100.0)  # (10000-5000)/5000 * 100


@pytest.mark.asyncio
async def test_growth_pct_negative(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 1, 15), total_mxn=3000.0, cost_mxn=1200.0),
        make_row(cart_product_id=2, created_at=datetime(2024, 1, 15), total_mxn=5000.0, cost_mxn=2000.0),
    )
    result = await getTotalSalesData(ReportFilters(date_from="2025-01-01", date_to="2025-12-31"))
    assert result.growth_pct is not None
    assert result.growth_pct < 0


# ─────────────────────────────────────────────────────────────
# Trend points
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trend_points_chronological_order(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 3, 1), total_mxn=300.0, cost_mxn=120.0),
        make_row(cart_product_id=2, created_at=datetime(2025, 1, 1), total_mxn=100.0, cost_mxn=40.0),
        make_row(cart_product_id=3, created_at=datetime(2025, 2, 1), total_mxn=200.0, cost_mxn=80.0),
    )
    result = await getTotalSalesData(ReportFilters(date_from="2025-01-01", date_to="2025-12-31"))
    months = [tp.month for tp in result.trend_points]
    assert months == sorted(months)
    assert months == ["2025-01", "2025-02", "2025-03"]


@pytest.mark.asyncio
async def test_trend_points_revenue_matches_total(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 1, 1), total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, created_at=datetime(2025, 1, 15), total_mxn=500.0,  cost_mxn=200.0),
        make_row(cart_product_id=3, created_at=datetime(2025, 2, 1), total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters(date_from="2025-01-01", date_to="2025-12-31"))
    total_from_trend = sum(tp.revenue for tp in result.trend_points)
    assert total_from_trend == pytest.approx(result.total_revenue)


# ─────────────────────────────────────────────────────────────
# Geo points
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_geo_points_cover_all_countries(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico",   total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
        make_row(cart_product_id=3, site="peru",     total_mxn=3000.0, cost_mxn=1200.0),
    )
    result = await getTotalSalesData(ReportFilters())
    dimensions = {gp.dimension for gp in result.geo_points}
    assert dimensions == {"mexico", "colombia", "peru"}


@pytest.mark.asyncio
async def test_geo_points_revenue_matches_total(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico",   total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await getTotalSalesData(ReportFilters())
    total_from_geo = sum(gp.revenue for gp in result.geo_points)
    assert total_from_geo == pytest.approx(result.total_revenue)
