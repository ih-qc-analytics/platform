"""
Ventas Totales report query tests.

Seed rows directly into report_line_items — no Jones DB needed.
Each test cleans up via clean_reporting_db fixture.
"""

import pytest
from datetime import datetime, date
from sqlalchemy import text

from app.schemas.reports import ReportFilters
from app.services.total_sales.total_sales import get_total_sales_data
from tests.conftest_reporting import bind_test_reporting_database


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


_LINE_ITEMS_EXCLUDED = frozenset({"payment_day", "payment_date", "paid_total", "paid_total_mxn", "paid_total_usd"})


def make_row(**overrides) -> dict:
    created_at = overrides.get("created_at", datetime(2025, 1, 15))
    payment_date = overrides.get("payment_date", created_at.date())
    defaults = {
        "cart_product_id": 1,
        "etl_date": date.today(),
        "seller_id": 1,
        "seller_name": "Ana Garcia",
        "lead_id": 1,
        "school_name": "Colegio Test",
        "site": "mexico",
        "zone_name": "IH Mexico",
        "state_name": "CDMX",
        "state_names": ["CDMX"],
        "city": "Ciudad de Mexico",
        "city_names": ["Ciudad de Mexico"],
        "business_status": "ganado",
        "cart_id": 1,
        "created_at": created_at,
        "year": 2025,
        "month": 1,
        "payment_status": "Aprobado",
        # payment_date kept for report_payments insert; not inserted into report_line_items
        "payment_date": payment_date,
        # first_payment_date replaces payment_day for line_items date filtering
        "first_payment_date": payment_date,
        "billing_status": "Aprobado",
        "product_id": 1,
        "product_type": "exam",
        "exam_cat_name": "KET",
        "exam_category": "Cambridge English (Main Suite)",
        "exam_canonical_name": "A2 Key",
        "exam_date_type": "fixed",
        "quantity": 5,
        "total": 5000.00,
        "cost": 2000.00,
        "discount": 0,
        "book_commission": 0,
        "exam_commission": 0,
        "base_currency": "MXN",
        "include_in_product_breakdown": True,
        "expected_total": 5000.00,
        "expected_cost": 2000.00,
        "expected_total_mxn": 5000.00,
        "expected_total_usd": None,
        "expected_cost_mxn": 2000.00,
        "expected_cost_usd": None,
        "student_count": 1,
        "payment_count": 1,
        "total_mxn": 5000.00,
        "cost_mxn": 2000.00,
        "total_usd": None,
        "cost_usd": None,
        "is_active": True,
    }
    row = {**defaults, **overrides}
    if "expected_total" not in overrides:
        row["expected_total"] = row["total"]
    if "expected_cost" not in overrides:
        row["expected_cost"] = row["cost"]
    if "expected_total_mxn" not in overrides:
        row["expected_total_mxn"] = row["total_mxn"]
    if "expected_cost_mxn" not in overrides:
        row["expected_cost_mxn"] = row["cost_mxn"]
    row["state_names"] = overrides.get(
        "state_names", [row["state_name"]] if row.get("state_name") else []
    )
    row["city_names"] = overrides.get("city_names", [row["city"]] if row.get("city") else [])
    return row


async def _insert(session_factory, *rows):
    li_cols = [c for c in rows[0].keys() if c not in _LINE_ITEMS_EXCLUDED]
    line_col_str = ", ".join(li_cols)
    line_val_str = ", ".join(f":{c}" for c in li_cols)
    line_sql = text(f"INSERT INTO report_line_items ({line_col_str}) VALUES ({line_val_str})")
    async with session_factory() as session:
        async with session.begin():
            for row in rows:
                await session.execute(line_sql, row)
                payment_row = {
                    "payment_id": row["cart_product_id"],
                    "etl_date": row["etl_date"],
                    "seller_id": row["seller_id"],
                    "seller_name": row["seller_name"],
                    "lead_id": row["lead_id"],
                    "school_name": row["school_name"],
                    "site": row["site"],
                    "zone_name": row["zone_name"],
                    "state_name": row["state_name"],
                    "city": row["city"],
                    "all_states": row.get("state_names", []),
                    "all_cities": row.get("city_names", []),
                    "state_names": row.get("state_names", []),
                    "city_names": row.get("city_names", []),
                    "year": row["year"],
                    "month": row["month"],
                    "created_at": row["created_at"],
                    "payment_date": row["payment_date"],
                    "base_currency": row["base_currency"],
                    "cart_id": row["cart_id"],
                    "payment_status": row["payment_status"],
                    "business_status": row["business_status"],
                    "is_active": row["is_active"],
                    "amount": row["total"],
                    "amount_mxn": row["total_mxn"],
                    "amount_usd": None,
                }
                await session.execute(
                    text("""
                    INSERT INTO report_payments (
                        payment_id, etl_date, seller_id, seller_name, lead_id, school_name, site, zone_name,
                        state_name, city, all_states, all_cities, state_names, city_names, year, month,
                        created_at, payment_date, base_currency, cart_id, payment_status, business_status,
                        is_active, amount, amount_mxn, amount_usd
                    ) VALUES (
                        :payment_id, :etl_date, :seller_id, :seller_name, :lead_id, :school_name, :site, :zone_name,
                        :state_name, :city, :all_states, :all_cities, :state_names, :city_names, :year, :month,
                        :created_at, :payment_date, :base_currency, :cart_id, :payment_status, :business_status,
                        :is_active, :amount, :amount_mxn, :amount_usd
                    )
                """),
                    payment_row,
                )
                # Insert allocation row so product-type revenue metrics are populated.
                # allocated_amount_mxn = total_mxn mirrors the payment amount for simple unit tests.
                await session.execute(
                    text("""
                    INSERT INTO report_payment_allocations (
                        payment_id, cart_product_id, etl_date,
                        allocated_amount, allocated_amount_mxn, allocated_amount_usd,
                        payment_date, seller_id, seller_name, lead_id, site, product_type, is_active
                    ) VALUES (
                        :payment_id, :cart_product_id, :etl_date,
                        :allocated_amount, :allocated_amount_mxn, :allocated_amount_usd,
                        :payment_date, :seller_id, :seller_name, :lead_id, :site, :product_type, :is_active
                    )
                """),
                    {
                        "payment_id": row["cart_product_id"],
                        "cart_product_id": row["cart_product_id"],
                        "etl_date": row["etl_date"],
                        "allocated_amount": row["total"],
                        "allocated_amount_mxn": row["total_mxn"],
                        "allocated_amount_usd": row.get("total_usd"),
                        "payment_date": row["payment_date"],
                        "seller_id": row["seller_id"],
                        "seller_name": row["seller_name"],
                        "lead_id": row["lead_id"],
                        "site": row["site"],
                        "product_type": row["product_type"],
                        "is_active": row["is_active"],
                    },
                )


def _bind(session_factory):
    bind_test_reporting_database(session_factory)
    import app.services.total_sales.total_sales as svc

    svc.ReportingSessionLocal = session_factory


# ─────────────────────────────────────────────────────────────
# Basic inclusion / exclusion
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_filters_returns_all_approved_active_rows(
    reporting_session_factory, clean_reporting_db
):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, lead_id=1, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, lead_id=2, total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await get_total_sales_data(ReportFilters())
    assert result.current.total_revenue == pytest.approx(3000.0)
    assert result.current.total_clients == 2


@pytest.mark.asyncio
async def test_inactive_rows_excluded(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, total_mxn=2000.0, cost_mxn=800.0, is_active=False),
    )
    result = await get_total_sales_data(ReportFilters())
    assert result.current.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_unapproved_payment_rows_excluded(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, total_mxn=1000.0, cost_mxn=400.0, payment_status="Aprobado"),
        make_row(cart_product_id=2, total_mxn=2000.0, cost_mxn=800.0, payment_status="Pendiente"),
    )
    result = await get_total_sales_data(ReportFilters())
    assert result.current.total_revenue == pytest.approx(1000.0)


# ─────────────────────────────────────────────────────────────
# Geo filters
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_country_filter_mexico_only(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await get_total_sales_data(ReportFilters(countries=["mexico"]))
    assert result.current.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_country_filter_colombia_only(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await get_total_sales_data(ReportFilters(countries=["colombia"]))
    assert result.current.total_revenue == pytest.approx(2000.0)


@pytest.mark.asyncio
async def test_two_countries_sum_correctly(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
        make_row(cart_product_id=3, site="peru", total_mxn=3000.0, cost_mxn=1200.0),
    )
    result = await get_total_sales_data(ReportFilters(countries=["mexico", "colombia"]))
    assert result.current.total_revenue == pytest.approx(3000.0)


@pytest.mark.asyncio
async def test_zone_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, zone_name="Zona Norte", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, zone_name="Zona Sur", total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await get_total_sales_data(ReportFilters(zones=["Zona Norte"]))
    assert result.current.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_state_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, state_name="CDMX", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, state_name="Jalisco", total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await get_total_sales_data(ReportFilters(states=["CDMX"]))
    assert result.current.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_city_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, city="CDMX", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, city="Guadalajara", total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await get_total_sales_data(ReportFilters(cities=["CDMX"]))
    assert result.current.total_revenue == pytest.approx(1000.0)


# ─────────────────────────────────────────────────────────────
# Date filters
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_date_from_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, created_at=datetime(2025, 1, 10), total_mxn=1000.0, cost_mxn=400.0
        ),
        make_row(
            cart_product_id=2, created_at=datetime(2025, 2, 10), total_mxn=2000.0, cost_mxn=800.0
        ),
    )
    result = await get_total_sales_data(ReportFilters(date_from="2025-02-01"))
    assert result.current.total_revenue == pytest.approx(2000.0)


@pytest.mark.asyncio
async def test_date_to_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, created_at=datetime(2025, 1, 10), total_mxn=1000.0, cost_mxn=400.0
        ),
        make_row(
            cart_product_id=2, created_at=datetime(2025, 2, 10), total_mxn=2000.0, cost_mxn=800.0
        ),
    )
    result = await get_total_sales_data(ReportFilters(date_to="2025-01-31"))
    assert result.current.total_revenue == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_date_range_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, created_at=datetime(2025, 1, 10), total_mxn=500.0, cost_mxn=200.0
        ),
        make_row(
            cart_product_id=2, created_at=datetime(2025, 3, 15), total_mxn=1500.0, cost_mxn=600.0
        ),
        make_row(
            cart_product_id=3, created_at=datetime(2025, 6, 20), total_mxn=2000.0, cost_mxn=800.0
        ),
    )
    result = await get_total_sales_data(ReportFilters(date_from="2025-02-01", date_to="2025-05-31"))
    assert result.current.total_revenue == pytest.approx(1500.0)


@pytest.mark.asyncio
async def test_future_date_returns_zeros(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, created_at=datetime(2025, 1, 15), total_mxn=5000.0, cost_mxn=2000.0
        ),
    )
    result = await get_total_sales_data(ReportFilters(date_from="2099-01-01", date_to="2099-12-31"))
    assert result.current.total_revenue == 0.0
    assert result.current.total_clients == 0


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
    result = await get_total_sales_data(ReportFilters())
    assert result.current.exam_revenue == pytest.approx(3000.0)
    assert result.current.total_exams == 5


@pytest.mark.asyncio
async def test_book_revenue_calculation(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, product_type="exam", total_mxn=3000.0, cost_mxn=1200.0),
        make_row(
            cart_product_id=2, product_type="book", total_mxn=1000.0, cost_mxn=400.0, quantity=2
        ),
    )
    result = await get_total_sales_data(ReportFilters())
    assert result.current.book_revenue == pytest.approx(1000.0)
    assert result.current.total_books == 2


@pytest.mark.asyncio
async def test_course_revenue_calculation(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, product_type="course", total_mxn=4000.0, cost_mxn=1600.0, quantity=1
        ),
    )
    result = await get_total_sales_data(ReportFilters())
    assert result.current.course_revenue == pytest.approx(4000.0)
    assert result.current.total_courses == 1


@pytest.mark.asyncio
async def test_otros_revenue_catches_uncategorized(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1,
            product_type="UNCATEGORIZED",
            total_mxn=500.0,
            cost_mxn=200.0,
            quantity=1,
        ),
    )
    result = await get_total_sales_data(ReportFilters())
    assert result.current.otros_revenue == pytest.approx(500.0)
    assert result.current.total_otros == 1


@pytest.mark.asyncio
async def test_total_revenue_sum_of_all_types(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, product_type="exam", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, product_type="book", total_mxn=500.0, cost_mxn=200.0),
        make_row(cart_product_id=3, product_type="course", total_mxn=750.0, cost_mxn=300.0),
        make_row(cart_product_id=4, product_type="UNCATEGORIZED", total_mxn=250.0, cost_mxn=100.0),
    )
    result = await get_total_sales_data(ReportFilters())
    assert result.current.total_revenue == pytest.approx(2500.0)
    assert (
        result.current.exam_revenue
        + result.current.book_revenue
        + result.current.course_revenue
        + result.current.otros_revenue
        == pytest.approx(2500.0)
    )


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
    result = await get_total_sales_data(ReportFilters())
    # profit_margin = (10000 - 4000) / 10000 * 100 = 60%
    assert result.current.profit_margin == pytest.approx(60.0)


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
    result = await get_total_sales_data(ReportFilters())
    assert result.current.total_clients == 3


@pytest.mark.asyncio
async def test_client_not_double_counted_across_products(
    reporting_session_factory, clean_reporting_db
):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, lead_id=10, product_type="exam", total_mxn=1000.0, cost_mxn=400.0
        ),
        make_row(
            cart_product_id=2, lead_id=10, product_type="book", total_mxn=500.0, cost_mxn=200.0
        ),
    )
    result = await get_total_sales_data(ReportFilters())
    assert result.current.total_clients == 1  # same lead_id, counted once
    assert result.current.total_revenue == pytest.approx(1500.0)


# ─────────────────────────────────────────────────────────────
# Prior year / growth
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prior_year_revenue_with_date_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, created_at=datetime(2025, 3, 15), total_mxn=5000.0, cost_mxn=2000.0
        ),
        make_row(
            cart_product_id=2, created_at=datetime(2024, 3, 15), total_mxn=3000.0, cost_mxn=1200.0
        ),
    )
    result = await get_total_sales_data(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )
    assert result.current.total_revenue == pytest.approx(5000.0)
    assert result.comparison is not None
    assert result.comparison.data.total_revenue == pytest.approx(3000.0)


@pytest.mark.asyncio
async def test_prior_year_revenue_absent_without_dates(
    reporting_session_factory, clean_reporting_db
):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, total_mxn=5000.0, cost_mxn=2000.0),
    )
    result = await get_total_sales_data(ReportFilters())  # no date_from / date_to
    assert result.comparison is None


@pytest.mark.asyncio
async def test_growth_pct_positive(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, created_at=datetime(2025, 1, 15), total_mxn=10000.0, cost_mxn=4000.0
        ),
        make_row(
            cart_product_id=2, created_at=datetime(2024, 1, 15), total_mxn=5000.0, cost_mxn=2000.0
        ),
    )
    result = await get_total_sales_data(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )
    assert result.comparison is not None
    assert result.comparison.deltas["total_revenue"].pct_change == pytest.approx(
        100.0
    )  # (10000-5000)/5000 * 100


@pytest.mark.asyncio
async def test_growth_pct_negative(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, created_at=datetime(2025, 1, 15), total_mxn=3000.0, cost_mxn=1200.0
        ),
        make_row(
            cart_product_id=2, created_at=datetime(2024, 1, 15), total_mxn=5000.0, cost_mxn=2000.0
        ),
    )
    result = await get_total_sales_data(
        ReportFilters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )
    assert result.comparison is not None
    assert result.comparison.deltas["total_revenue"].pct_change < 0


# ─────────────────────────────────────────────────────────────
# Trend points
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trend_points_chronological_order(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, created_at=datetime(2025, 3, 1), total_mxn=300.0, cost_mxn=120.0
        ),
        make_row(
            cart_product_id=2, created_at=datetime(2025, 1, 1), total_mxn=100.0, cost_mxn=40.0
        ),
        make_row(
            cart_product_id=3, created_at=datetime(2025, 2, 1), total_mxn=200.0, cost_mxn=80.0
        ),
    )
    result = await get_total_sales_data(ReportFilters(date_from="2025-01-01", date_to="2025-12-31"))
    months = [tp.month for tp in result.current.trend_points]
    assert months == sorted(months)
    assert months == ["2025-01", "2025-02", "2025-03"]


@pytest.mark.asyncio
async def test_trend_points_revenue_matches_total(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, created_at=datetime(2025, 1, 1), total_mxn=1000.0, cost_mxn=400.0
        ),
        make_row(
            cart_product_id=2, created_at=datetime(2025, 1, 15), total_mxn=500.0, cost_mxn=200.0
        ),
        make_row(
            cart_product_id=3, created_at=datetime(2025, 2, 1), total_mxn=2000.0, cost_mxn=800.0
        ),
    )
    result = await get_total_sales_data(ReportFilters(date_from="2025-01-01", date_to="2025-12-31"))
    total_from_trend = sum(tp.revenue for tp in result.current.trend_points)
    assert total_from_trend == pytest.approx(result.current.total_revenue)


# ─────────────────────────────────────────────────────────────
# Geo points
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_geo_points_cover_all_countries(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
        make_row(cart_product_id=3, site="peru", total_mxn=3000.0, cost_mxn=1200.0),
    )
    result = await get_total_sales_data(ReportFilters())
    dimensions = {gp.dimension for gp in result.current.geo_points}
    assert dimensions == {"mexico", "colombia", "peru"}


@pytest.mark.asyncio
async def test_geo_points_revenue_matches_total(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico", total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, site="colombia", total_mxn=2000.0, cost_mxn=800.0),
    )
    result = await get_total_sales_data(ReportFilters())
    total_from_geo = sum(gp.revenue for gp in result.current.geo_points)
    assert total_from_geo == pytest.approx(result.current.total_revenue)
