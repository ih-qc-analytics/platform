"""
Por País report query tests.

Seed rows directly into report_line_items — no Jones DB needed.
PorPaisFilters uses date_from/date_to (not year) to filter created_at.

Summary rows: total_schools = COUNT(DISTINCT lead_id) per site.
Exam counts: SUM(quantity) per (site, exam_canonical_name) for product_type='exam'.
Status rows: ganado/perdido/mantenido based on current vs prior year date range presence.
"""

import pytest
from datetime import datetime, date
from sqlalchemy import text

from app.schemas.reports import PorPaisFilters
from app.services.por_pais.por_pais import get_por_pais_report
from tests.conftest_reporting import bind_test_reporting_database


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


_LINE_ITEMS_EXCLUDED = frozenset(
    {"payment_day", "payment_date", "paid_total", "paid_total_mxn", "paid_total_usd"}
)


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
    col_str = ", ".join(li_cols)
    val_str = ", ".join(f":{c}" for c in li_cols)
    sql = text(f"INSERT INTO report_line_items ({col_str}) VALUES ({val_str})")
    async with session_factory() as session:
        async with session.begin():
            for row in rows:
                await session.execute(sql, row)
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
                    {
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
                    },
                )


def _bind(session_factory):
    bind_test_reporting_database(session_factory)
    import app.services.por_pais.por_pais as svc
    import app.services.por_pais.repository as repo

    svc.ReportingSessionLocal = session_factory
    repo.ReportingSessionLocal = session_factory


def _filters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=False) -> PorPaisFilters:
    return PorPaisFilters(date_from=date_from, date_to=date_to, show_comparison=show_comparison)


# ─────────────────────────────────────────────────────────────
# Summary rows
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_one_row_per_country(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico", lead_id=1, created_at=datetime(2025, 3, 1)),
        make_row(cart_product_id=2, site="colombia", lead_id=2, created_at=datetime(2025, 3, 1)),
        make_row(cart_product_id=3, site="mexico", lead_id=3, created_at=datetime(2025, 4, 1)),
    )
    result = await get_por_pais_report(_filters())
    countries = {row.country for row in result.current.summary_rows}
    assert countries == {"mexico", "colombia"}
    assert len(result.current.summary_rows) == 2


@pytest.mark.asyncio
async def test_exam_count_per_country_correct(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1,
            site="mexico",
            lead_id=1,
            product_type="exam",
            exam_canonical_name="A2 Key",
            quantity=3,
            created_at=datetime(2025, 3, 1),
        ),
        make_row(
            cart_product_id=2,
            site="mexico",
            lead_id=2,
            product_type="exam",
            exam_canonical_name="A2 Key",
            quantity=7,
            created_at=datetime(2025, 4, 1),
        ),
        make_row(
            cart_product_id=3,
            site="colombia",
            lead_id=3,
            product_type="exam",
            exam_canonical_name="B2 First",
            quantity=5,
            created_at=datetime(2025, 5, 1),
        ),
    )
    result = await get_por_pais_report(_filters())
    mexico_row = next(r for r in result.current.summary_rows if r.country == "mexico")
    colombia_row = next(r for r in result.current.summary_rows if r.country == "colombia")
    # A2 Key maps to cambridge bucket
    assert mexico_row.cambridge == 10  # 3 + 7
    assert colombia_row.cambridge == 5


@pytest.mark.asyncio
async def test_inactive_excluded(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1,
            site="mexico",
            lead_id=1,
            is_active=True,
            created_at=datetime(2025, 3, 1),
        ),
        make_row(
            cart_product_id=2,
            site="mexico",
            lead_id=2,
            is_active=False,
            created_at=datetime(2025, 3, 1),
        ),
    )
    result = await get_por_pais_report(_filters())
    assert len(result.current.summary_rows) == 1
    mexico_row = result.current.summary_rows[0]
    assert mexico_row.total_schools == 1  # only the active lead


@pytest.mark.asyncio
async def test_unapproved_excluded(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1,
            site="mexico",
            lead_id=1,
            payment_status="Aprobado",
            created_at=datetime(2025, 3, 1),
        ),
        make_row(
            cart_product_id=2,
            site="mexico",
            lead_id=2,
            payment_status="Pendiente",
            created_at=datetime(2025, 3, 1),
        ),
    )
    result = await get_por_pais_report(_filters())
    assert len(result.current.summary_rows) == 1
    assert result.current.summary_rows[0].total_schools == 1


@pytest.mark.asyncio
async def test_date_range_filter(reporting_session_factory, clean_reporting_db):
    """Rows outside the date range are not counted in summary or status."""
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico", lead_id=1, created_at=datetime(2025, 6, 15)),
        make_row(cart_product_id=2, site="mexico", lead_id=2, created_at=datetime(2026, 1, 10)),
    )
    # Only 2025 rows included
    result = await get_por_pais_report(_filters(date_from="2025-01-01", date_to="2025-12-31"))
    assert len(result.current.summary_rows) == 1
    assert result.current.summary_rows[0].total_schools == 1


@pytest.mark.asyncio
async def test_multiple_countries(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(
            cart_product_id=1,
            site="mexico",
            lead_id=1,
            created_at=datetime(2025, 1, 1),
            quantity=10,
        ),
        make_row(
            cart_product_id=2,
            site="colombia",
            lead_id=2,
            created_at=datetime(2025, 2, 1),
            quantity=5,
        ),
        make_row(
            cart_product_id=3, site="peru", lead_id=3, created_at=datetime(2025, 3, 1), quantity=8
        ),
    )
    result = await get_por_pais_report(_filters())
    assert len(result.current.summary_rows) == 3
    countries = {row.country for row in result.current.summary_rows}
    assert countries == {"mexico", "colombia", "peru"}


@pytest.mark.asyncio
async def test_status_rows_ganado_perdido_mantenido(reporting_session_factory, clean_reporting_db):
    """
    Status rows use the active comparison range (show_comparison=True, default previous year).
    - lead_id=1 in 2025 only → ganado
    - lead_id=2 in 2024 only → perdido
    - lead_id=3 in both → mantenido
    """
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        # Current year (2025): lead_id=1 and lead_id=3
        make_row(cart_product_id=1, site="mexico", lead_id=1, created_at=datetime(2025, 6, 1)),
        make_row(cart_product_id=2, site="mexico", lead_id=3, created_at=datetime(2025, 7, 1)),
        # Prior year (2024): lead_id=2 and lead_id=3
        make_row(cart_product_id=3, site="mexico", lead_id=2, created_at=datetime(2024, 6, 1)),
        make_row(cart_product_id=4, site="mexico", lead_id=3, created_at=datetime(2024, 7, 1)),
    )
    result = await get_por_pais_report(
        _filters(date_from="2025-01-01", date_to="2025-12-31", show_comparison=True)
    )
    mexico_status = next((r for r in result.current.status_rows if r.country == "mexico"), None)
    assert mexico_status is not None
    assert mexico_status.schools_ganados == 1  # lead_id=1
    assert mexico_status.schools_perdidos == 1  # lead_id=2
    assert mexico_status.schools_mantenidos == 1  # lead_id=3
