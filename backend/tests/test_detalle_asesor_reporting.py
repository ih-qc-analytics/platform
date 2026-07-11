"""
Detalle Asesor report query tests.

Seed rows directly into report_line_items — no Jones DB needed.
Each row IS one cart_product (no grouping). Cursor is cart_product_id.
The detalle WHERE always includes product_type = 'exam'.
"""

import pytest
from datetime import datetime, date
from sqlalchemy import text

from app.schemas.reports import DetalleFilters
from app.services.detalle_asesor.detalle_asesor import getDetalleData
from tests.conftest_reporting import bind_test_reporting_database


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


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
        "payment_date": payment_date,
        "payment_day": payment_date,
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
        "total_mxn": 5000.00,
        "cost_mxn": 2000.00,
        "is_active": True,
    }
    row = {**defaults, **overrides}
    row["state_names"] = overrides.get(
        "state_names", [row["state_name"]] if row.get("state_name") else []
    )
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
    import app.services.detalle_asesor.detalle_asesor as svc

    svc.ReportingSessionLocal = session_factory


def _filters(**overrides) -> DetalleFilters:
    defaults = {"page_size": 25}
    return DetalleFilters(**{**defaults, **overrides})


# ─────────────────────────────────────────────────────────────
# Basic row structure
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_one_row_per_cart_product(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, exam_canonical_name="A2 Key", quantity=3),
        make_row(cart_product_id=2, exam_canonical_name="B2 First", quantity=7, lead_id=2),
        make_row(cart_product_id=3, exam_canonical_name="C1 Advanced", quantity=2, lead_id=3),
    )
    result = await getDetalleData(_filters())
    assert len(result.current.rows) == 3
    ids = {row.id for row in result.current.rows}
    assert ids == {1, 2, 3}


@pytest.mark.asyncio
async def test_exam_counts_keyed_by_canonical_name(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, exam_canonical_name="A2 Key", quantity=5),
    )
    result = await getDetalleData(_filters())
    assert len(result.current.rows) == 1
    row = result.current.rows[0]
    assert row.exam_counts.get("A2 Key") == 5


@pytest.mark.asyncio
async def test_total_equals_sum_of_exam_counts(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, exam_canonical_name="B2 First", quantity=8),
    )
    result = await getDetalleData(_filters())
    assert len(result.current.rows) == 1
    row = result.current.rows[0]
    assert row.total == sum(row.exam_counts.values())


# ─────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_by_seller_name(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_name="Ana Garcia", quantity=3),
        make_row(cart_product_id=2, seller_name="Luis Rodriguez", quantity=5, lead_id=2),
    )
    result = await getDetalleData(_filters(search="Ana"))
    assert len(result.current.rows) == 1
    assert result.current.rows[0].seller_name == "Ana Garcia"


@pytest.mark.asyncio
async def test_search_by_school_name(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, school_name="Colegio Americano", quantity=3),
        make_row(cart_product_id=2, school_name="Instituto Moderno", quantity=5, lead_id=2),
    )
    result = await getDetalleData(_filters(search="Instituto"))
    assert len(result.current.rows) == 1
    assert result.current.rows[0].school_name == "Instituto Moderno"


@pytest.mark.asyncio
async def test_search_case_insensitive(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_name="Ana Garcia", quantity=3),
    )
    result = await getDetalleData(_filters(search="ana garcia"))
    assert len(result.current.rows) == 1

    result2 = await getDetalleData(_filters(search="ANA GARCIA"))
    assert len(result2.current.rows) == 1


@pytest.mark.asyncio
async def test_search_partial_match(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, seller_name="Ana Garcia", quantity=3),
        make_row(cart_product_id=2, seller_name="Luis Rodriguez", quantity=5, lead_id=2),
    )
    result = await getDetalleData(_filters(search="Garc"))
    assert len(result.current.rows) == 1
    assert result.current.rows[0].seller_name == "Ana Garcia"


# ─────────────────────────────────────────────────────────────
# Cursor pagination
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cursor_pagination_first_page(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    for i in range(1, 6):
        await _insert(
            reporting_session_factory,
            make_row(cart_product_id=i, lead_id=i, quantity=i),
        )
    result = await getDetalleData(_filters(page_size=3))
    assert len(result.current.rows) == 3
    assert result.current.rows[0].id == 1
    assert result.current.rows[2].id == 3


@pytest.mark.asyncio
async def test_cursor_pagination_second_page(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    for i in range(1, 6):
        await _insert(
            reporting_session_factory,
            make_row(cart_product_id=i, lead_id=i, quantity=i),
        )
    first_page = await getDetalleData(_filters(page_size=3))
    assert isinstance(first_page.current.next_cursor, str)

    second_page = await getDetalleData(_filters(page_size=3, cursor=first_page.current.next_cursor))
    assert len(second_page.current.rows) == 2
    assert second_page.current.rows[0].id == 4


@pytest.mark.asyncio
async def test_cursor_pagination_has_more_true(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    for i in range(1, 6):
        await _insert(
            reporting_session_factory,
            make_row(cart_product_id=i, lead_id=i, quantity=i),
        )
    result = await getDetalleData(_filters(page_size=3))
    assert result.current.has_more is True
    assert isinstance(result.current.next_cursor, str)


@pytest.mark.asyncio
async def test_cursor_pagination_has_more_false_on_last_page(
    reporting_session_factory, clean_reporting_db
):
    _bind(reporting_session_factory)
    for i in range(1, 4):
        await _insert(
            reporting_session_factory,
            make_row(cart_product_id=i, lead_id=i, quantity=i),
        )
    result = await getDetalleData(_filters(page_size=5))
    assert result.current.has_more is False
    assert result.current.next_cursor is None


@pytest.mark.asyncio
async def test_cursor_pagination_no_duplicates_across_pages(
    reporting_session_factory, clean_reporting_db
):
    _bind(reporting_session_factory)
    for i in range(1, 8):
        await _insert(
            reporting_session_factory,
            make_row(cart_product_id=i, lead_id=i, quantity=i),
        )
    page1 = await getDetalleData(_filters(page_size=4))
    page2 = await getDetalleData(_filters(page_size=4, cursor=page1.current.next_cursor))

    ids_p1 = {r.id for r in page1.current.rows}
    ids_p2 = {r.id for r in page2.current.rows}
    assert ids_p1.isdisjoint(ids_p2)
    assert ids_p1 | ids_p2 == set(range(1, 8))


# ─────────────────────────────────────────────────────────────
# Date & country filters
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_date_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, created_at=datetime(2025, 1, 10), quantity=3),
        make_row(cart_product_id=2, created_at=datetime(2025, 3, 10), quantity=5, lead_id=2),
    )
    result = await getDetalleData(_filters(date_from="2025-02-01", date_to="2025-12-31"))
    assert len(result.current.rows) == 1
    assert result.current.rows[0].id == 2


@pytest.mark.asyncio
async def test_country_filter(reporting_session_factory, clean_reporting_db):
    _bind(reporting_session_factory)
    await _insert(
        reporting_session_factory,
        make_row(cart_product_id=1, site="mexico", quantity=3),
        make_row(cart_product_id=2, site="colombia", quantity=5, lead_id=2),
    )
    result = await getDetalleData(_filters(countries=["colombia"]))
    assert len(result.current.rows) == 1
    assert result.current.rows[0].id == 2
