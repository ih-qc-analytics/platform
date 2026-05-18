"""
Por Asesor report query tests.

Seed rows directly into report_line_items — no Jones DB needed.
The service re-computes ganado/perdido/mantenido from year presence data,
so rows with year=filters.year vs year=filters.year-1 determine the status.
"""
import pytest
from datetime import datetime, date
from sqlalchemy import text

from app.schemas.reports import AsesorFilters
from app.services.por_asesor.por_asesor import getAsesorReport
from tests.conftest_reporting import bind_test_reporting_database


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def make_row(**overrides) -> dict:
    created_at = overrides.get("created_at", datetime(2025, 1, 15))
    payment_date = overrides.get("payment_date", created_at.date())
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
        "state_names":          ["CDMX"],
        "city":                 "Ciudad de Mexico",
        "city_names":           ["Ciudad de Mexico"],
        "business_status":      "ganado",
        "cart_id":              1,
        "created_at":           created_at,
        "year":                 2025,
        "month":                1,
        "payment_status":       "Aprobado",
        "payment_date":         payment_date,
        "payment_day":          payment_date,
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
        "include_in_product_breakdown": True,
        "total_mxn":            5000.00,
        "cost_mxn":             2000.00,
        "is_active":            True,
    }
    row = {**defaults, **overrides}
    row["state_names"] = overrides.get("state_names", [row["state_name"]] if row.get("state_name") else [])
    row["city_names"] = overrides.get("city_names", [row["city"]] if row.get("city") else [])
    row["payment_day"] = overrides.get("payment_day", row["payment_date"])
    return row


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
    import app.services.por_asesor.por_asesor as svc
    import app.services.por_asesor.repository as repo
    svc.ReportingSessionLocal = session_factory
    repo.ReportingSessionLocal = session_factory


def _filters(**overrides) -> AsesorFilters:
    defaults = {"year": 2025, "limit": 25}
    return AsesorFilters(**{**defaults, **overrides})


# ─────────────────────────────────────────────────────────────
# Summary rows
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_one_row_per_seller(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, seller_name="Ana",  year=2025, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, seller_id=1, seller_name="Ana",  year=2025, total_mxn=500.0,  cost_mxn=200.0, lead_id=2),
        make_row(cart_product_id=3, seller_id=2, seller_name="Luis", year=2025, total_mxn=2000.0, cost_mxn=800.0, lead_id=3),
    )
    result = await getAsesorReport(_filters(year=2025))
    assert len(result.rows) == 2
    seller_ids = {row.seller_id for row in result.rows}
    assert seller_ids == {1, 2}


@pytest.mark.asyncio
async def test_total_revenue_per_seller(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, seller_name="Ana", year=2025, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, seller_id=1, seller_name="Ana", year=2025, total_mxn=500.0,  cost_mxn=200.0, lead_id=2),
    )
    result = await getAsesorReport(_filters(year=2025))
    assert len(result.rows) == 1
    assert result.rows[0].total_revenue == pytest.approx(1500.0)


# ─────────────────────────────────────────────────────────────
# Exam breakdown
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exam_breakdown_keyed_by_canonical_name(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1, seller_id=1, year=2025,
            product_type="exam",
            exam_category="Cambridge English (Main Suite)",
            total_mxn=1000.0, cost_mxn=400.0,
        ),
    )
    result = await getAsesorReport(_filters(year=2025))
    assert len(result.rows) == 1
    breakdown = result.rows[0].exam_breakdown
    assert "Cambridge English (Main Suite)" in breakdown


@pytest.mark.asyncio
async def test_exam_breakdown_sums_correctly(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, year=2025, product_type="exam",
                 exam_category="Cambridge English (Main Suite)", quantity=3, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, seller_id=1, year=2025, product_type="exam",
                 exam_category="Cambridge English (Main Suite)", quantity=7, total_mxn=2000.0, cost_mxn=800.0, lead_id=2),
    )
    result = await getAsesorReport(_filters(year=2025))
    assert len(result.rows) == 1
    cambridge_count = result.rows[0].exam_breakdown.get("Cambridge English (Main Suite)", 0)
    assert cambridge_count == 10  # 3 + 7


# ─────────────────────────────────────────────────────────────
# Business status counts (re-computed from year presence data)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ganado_count_correct(reporting_session_factory, clean_reporting_db):
    """Lead present in 2025 but NOT in 2024 → ganado."""
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, lead_id=10, year=2025, total_mxn=1000.0, cost_mxn=400.0),
    )
    result = await getAsesorReport(_filters(year=2025))
    assert len(result.rows) == 1
    assert result.rows[0].ganados == 1
    assert result.rows[0].perdidos == 0
    assert result.rows[0].mantenidos == 0


@pytest.mark.asyncio
async def test_perdido_count_correct(reporting_session_factory, clean_reporting_db):
    """Lead present in 2024 but NOT in 2025 → perdido. Seller must have a current-year row to appear in summary."""
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        # 2025 row for a different lead (so seller appears in current summary)
        make_row(cart_product_id=1, seller_id=1, lead_id=10, year=2025, total_mxn=1000.0, cost_mxn=400.0),
        # 2024 row for lead_id=20 (not present in 2025 → perdido)
        make_row(cart_product_id=2, seller_id=1, lead_id=20, year=2024,
                 created_at=datetime(2024, 6, 1), total_mxn=800.0, cost_mxn=320.0),
    )
    result = await getAsesorReport(_filters(year=2025))
    assert len(result.rows) == 1
    assert result.rows[0].perdidos == 1   # lead_id=20 was in 2024 not in 2025
    assert result.rows[0].ganados == 1    # lead_id=10 is new in 2025


@pytest.mark.asyncio
async def test_mantenido_count_correct(reporting_session_factory, clean_reporting_db):
    """Lead present in BOTH 2025 and 2024 → mantenido."""
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, lead_id=10, year=2025, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, seller_id=1, lead_id=10, year=2024,
                 created_at=datetime(2024, 6, 1), total_mxn=800.0, cost_mxn=320.0),
    )
    result = await getAsesorReport(_filters(year=2025))
    assert len(result.rows) == 1
    assert result.rows[0].mantenidos == 1
    assert result.rows[0].ganados == 0
    assert result.rows[0].perdidos == 0


@pytest.mark.asyncio
async def test_uncategorized_business_status_row_still_classified_by_year(reporting_session_factory, clean_reporting_db):
    """A row with business_status=UNCATEGORIZED is still classified by year data."""
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, lead_id=10, year=2025,
                 business_status="UNCATEGORIZED", total_mxn=1000.0, cost_mxn=400.0),
    )
    # Service ignores business_status column; recomputes from year presence
    result = await getAsesorReport(_filters(year=2025))
    assert len(result.rows) == 1
    # lead_id=10 only in 2025 → ganado
    assert result.rows[0].ganados == 1


# ─────────────────────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_year_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, year=2025, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, seller_id=1, year=2024,
                 created_at=datetime(2024, 6, 1), total_mxn=500.0, cost_mxn=200.0),
    )
    result_2025 = await getAsesorReport(_filters(year=2025))
    assert len(result_2025.rows) == 1
    assert result_2025.rows[0].total_revenue == pytest.approx(1000.0)

    result_2024 = await getAsesorReport(_filters(year=2024))
    assert len(result_2024.rows) == 1
    assert result_2024.rows[0].total_revenue == pytest.approx(500.0)


@pytest.mark.asyncio
async def test_country_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, site="mexico",   year=2025, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, seller_id=2, site="colombia", year=2025, total_mxn=2000.0, cost_mxn=800.0, lead_id=2),
    )
    result = await getAsesorReport(_filters(year=2025, countries=["mexico"]))
    assert len(result.rows) == 1
    assert result.rows[0].seller_id == 1


@pytest.mark.asyncio
async def test_seller_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, seller_name="Ana",  year=2025, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, seller_id=2, seller_name="Luis", year=2025, total_mxn=2000.0, cost_mxn=800.0, lead_id=2),
    )
    result = await getAsesorReport(_filters(year=2025, sellers=["Ana"]))
    assert len(result.rows) == 1
    assert result.rows[0].seller_name == "Ana"


@pytest.mark.asyncio
async def test_multiple_sellers_independent(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_id=1, seller_name="Ana",  lead_id=10, year=2025, total_mxn=1000.0, cost_mxn=400.0),
        make_row(cart_product_id=2, seller_id=2, seller_name="Luis", lead_id=20, year=2025, total_mxn=3000.0, cost_mxn=1200.0),
    )
    result = await getAsesorReport(_filters(year=2025))
    revenues = {row.seller_id: row.total_revenue for row in result.rows}
    assert revenues[1] == pytest.approx(1000.0)
    assert revenues[2] == pytest.approx(3000.0)
