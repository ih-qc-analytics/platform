"""
ETL test suite.

Transform tests: pure unit tests — no DB needed.
Upsert tests: require test reporting DB (clean_reporting_db fixture).
Business status tests: require Jones test DB (ui_dev_db fixture).
Integration tests: require both DBs.
"""
import pytest
import pytest_asyncio
from datetime import datetime, date
from sqlalchemy import text

from app.etl.payment_upsert import _transform, _upsert, calculate_business_status
from app.enums import PaymentStatus, ProductType, BusinessStatus, ExamCategory
from tests.conftest_reporting import bind_test_reporting_database


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _base_row(**overrides) -> dict:
    row = {
        "cart_product_id": 1,
        "seller_id": 1,
        "seller_name": "Ana Garcia",
        "lead_id": 1,
        "school_name": "Test School",
        "site": "mexico",
        "zone_name": "IH Mexico",
        "state_name": "CDMX",
        "city": "Ciudad de Mexico",
        "cart_id": 1,
        "billing_status": "Aprobado",
        "created_at": datetime(2025, 3, 15),
        "book_commission": 0,
        "exam_commission": 0,
        "payment_status": "Aprobado",
        "payment_date": date(2025, 3, 16),
        "product_id": 1,
        "product_type": "exam",
        "exam_cat_name": "KET",
        "exam_date_type": "fixed",
        "quantity": 5,
        "total": 5000.00,
        "cost": 2000.00,
        "discount": 0,
    }
    row.update(overrides)
    return row


def _do_transform(row: dict, ganados=None, perdidos=None, mantenidos=None) -> dict:
    return _transform(row, ganados or set(), perdidos or set(), mantenidos or set())


# ─────────────────────────────────────────────────────────────
# Transform tests (pure unit — no DB)
# ─────────────────────────────────────────────────────────────

def test_transform_product_type_known():
    result = _do_transform(_base_row(product_type="exam"))
    assert result["product_type"] == "exam"


def test_transform_product_type_unknown():
    result = _do_transform(_base_row(product_type=""))
    assert result["product_type"] == ProductType.UNCATEGORIZED.value


def test_transform_product_type_none():
    result = _do_transform(_base_row(product_type=None))
    assert result["product_type"] == ProductType.UNCATEGORIZED.value


def test_transform_payment_status_empty():
    result = _do_transform(_base_row(payment_status=None))
    assert result["payment_status"] == PaymentStatus.UNCATEGORIZED.value


def test_transform_is_active_true_for_aprobado():
    result = _do_transform(_base_row(payment_status="Aprobado"))
    assert result["is_active"] is True


def test_transform_is_active_false_for_cancelado():
    result = _do_transform(_base_row(payment_status="Cancelado"))
    assert result["is_active"] is False


def test_transform_is_active_true_for_pendiente():
    result = _do_transform(_base_row(payment_status="Pendiente"))
    assert result["is_active"] is True


def test_transform_business_status_ganado():
    result = _do_transform(_base_row(lead_id=10), ganados={10})
    assert result["business_status"] == BusinessStatus.GANADO.value


def test_transform_business_status_perdido():
    result = _do_transform(_base_row(lead_id=20), perdidos={20})
    assert result["business_status"] == BusinessStatus.PERDIDO.value


def test_transform_business_status_mantenido():
    result = _do_transform(_base_row(lead_id=30), mantenidos={30})
    assert result["business_status"] == BusinessStatus.MANTENIDO.value


def test_transform_business_status_uncategorized():
    result = _do_transform(_base_row(lead_id=99))
    assert result["business_status"] == BusinessStatus.UNCATEGORIZED.value


def test_transform_year_month_extracted():
    result = _do_transform(_base_row(created_at=datetime(2025, 3, 15)))
    assert result["year"] == 2025
    assert result["month"] == 3


def test_transform_exam_category_mapped():
    result = _do_transform(_base_row(exam_cat_name="KET"))
    assert result["exam_category"] == ExamCategory.CAMBRIDGE_ENGLISH.value


def test_transform_exam_category_uncategorized_empty():
    result = _do_transform(_base_row(exam_cat_name=""))
    assert result["exam_category"] == ExamCategory.UNCATEGORIZED.value


def test_transform_exam_category_uncategorized_none():
    result = _do_transform(_base_row(exam_cat_name=None))
    assert result["exam_category"] == ExamCategory.UNCATEGORIZED.value


def test_transform_exam_canonical_name_mapped():
    result = _do_transform(_base_row(exam_cat_name="KET"))
    assert result["exam_canonical_name"] == "A2 Key"


def test_transform_exam_canonical_name_uncategorized():
    result = _do_transform(_base_row(exam_cat_name=None))
    assert result["exam_canonical_name"] == "UNCATEGORIZED"


# ─────────────────────────────────────────────────────────────
# Upsert tests (require test reporting DB)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_inserts_new_row(reporting_engine, reporting_session_factory, clean_reporting_db):
    bind_test_reporting_database(reporting_session_factory)
    row = _do_transform(_base_row())
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row])
    async with reporting_engine.connect() as conn:
        count = (await conn.execute(text("SELECT COUNT(*) FROM report_line_items"))).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_upsert_updates_existing_row_on_conflict(reporting_engine, reporting_session_factory, clean_reporting_db):
    bind_test_reporting_database(reporting_session_factory)
    row_pending = _do_transform(_base_row(cart_product_id=1, payment_status="Pendiente"))
    row_aprobado = _do_transform(_base_row(cart_product_id=1, payment_status="Aprobado"))
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row_pending])
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row_aprobado])
    async with reporting_engine.connect() as conn:
        result = await conn.execute(text("SELECT payment_status, COUNT(*) as cnt FROM report_line_items GROUP BY payment_status"))
        rows = result.fetchall()
    assert len(rows) == 1
    assert rows[0].payment_status == "Aprobado"
    assert rows[0].cnt == 1


@pytest.mark.asyncio
async def test_upsert_does_not_duplicate(reporting_engine, reporting_session_factory, clean_reporting_db):
    bind_test_reporting_database(reporting_session_factory)
    row = _do_transform(_base_row())
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row])
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row])
    async with reporting_engine.connect() as conn:
        count = (await conn.execute(text("SELECT COUNT(*) FROM report_line_items"))).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_upsert_updates_dimensions_on_conflict(reporting_engine, reporting_session_factory, clean_reporting_db):
    bind_test_reporting_database(reporting_session_factory)
    old_row = _do_transform(_base_row(cart_product_id=1, school_name="Old Name"))
    new_row = _do_transform(_base_row(cart_product_id=1, school_name="New Name"))
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [old_row])
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [new_row])
    async with reporting_engine.connect() as conn:
        name = (await conn.execute(text("SELECT school_name FROM report_line_items WHERE cart_product_id = 1"))).scalar()
    assert name == "New Name"


@pytest.mark.asyncio
async def test_upsert_preserves_financials_correctly(reporting_engine, reporting_session_factory, clean_reporting_db):
    bind_test_reporting_database(reporting_session_factory)
    row = _do_transform(_base_row(total=1000, cost=500))
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row])
    async with reporting_engine.connect() as conn:
        result = (await conn.execute(text("SELECT total, cost FROM report_line_items"))).fetchone()
    assert float(result.total) == 1000.0
    assert float(result.cost) == 500.0


@pytest.mark.asyncio
async def test_upsert_handles_large_batch(reporting_engine, reporting_session_factory, clean_reporting_db):
    bind_test_reporting_database(reporting_session_factory)
    rows = [_do_transform(_base_row(cart_product_id=i, lead_id=i, cart_id=i)) for i in range(1, 1501)]
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, rows)
    async with reporting_engine.connect() as conn:
        count = (await conn.execute(text("SELECT COUNT(*) FROM report_line_items"))).scalar()
    assert count == 1500


@pytest.mark.asyncio
async def test_upsert_sets_is_active_false_for_cancelado(reporting_engine, reporting_session_factory, clean_reporting_db):
    bind_test_reporting_database(reporting_session_factory)
    row = _do_transform(_base_row(payment_status="Cancelado"))
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row])
    async with reporting_engine.connect() as conn:
        is_active = (await conn.execute(text("SELECT is_active FROM report_line_items"))).scalar()
    assert is_active is False


@pytest.mark.asyncio
async def test_upsert_sets_is_active_true_for_aprobado(reporting_engine, reporting_session_factory, clean_reporting_db):
    bind_test_reporting_database(reporting_session_factory)
    row = _do_transform(_base_row(payment_status="Aprobado"))
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row])
    async with reporting_engine.connect() as conn:
        is_active = (await conn.execute(text("SELECT is_active FROM report_line_items"))).scalar()
    assert is_active is True


# ─────────────────────────────────────────────────────────────
# Business status calculation tests (require Jones test DB)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ganado_school_in_current_not_prior(ui_dev_db):
    from tests.seeds.business_status_helpers import seed_lead_with_payment
    lead_id = await seed_lead_with_payment(year_current=True, year_prior=False)
    ganados, perdidos, mantenidos = await calculate_business_status({lead_id})
    assert lead_id in ganados
    assert lead_id not in perdidos
    assert lead_id not in mantenidos


@pytest.mark.asyncio
async def test_perdido_school_in_prior_not_current(ui_dev_db):
    from tests.seeds.business_status_helpers import seed_lead_with_payment
    lead_id = await seed_lead_with_payment(year_current=False, year_prior=True)
    ganados, perdidos, mantenidos = await calculate_business_status({lead_id})
    assert lead_id in perdidos
    assert lead_id not in ganados


@pytest.mark.asyncio
async def test_mantenido_school_in_both_years(ui_dev_db):
    from tests.seeds.business_status_helpers import seed_lead_with_payment
    lead_id = await seed_lead_with_payment(year_current=True, year_prior=True)
    ganados, perdidos, mantenidos = await calculate_business_status({lead_id})
    assert lead_id in mantenidos


@pytest.mark.asyncio
async def test_uncategorized_no_approved_payments(ui_dev_db):
    from tests.seeds.business_status_helpers import seed_lead_with_payment
    lead_id = await seed_lead_with_payment(year_current=False, year_prior=False)
    ganados, perdidos, mantenidos = await calculate_business_status({lead_id})
    assert lead_id not in ganados
    assert lead_id not in perdidos
    assert lead_id not in mantenidos


@pytest.mark.asyncio
async def test_cancelled_payment_does_not_count(ui_dev_db):
    from tests.seeds.business_status_helpers import seed_lead_with_payment
    lead_id = await seed_lead_with_payment(year_current=False, year_prior=True, cancelled_current=True)
    ganados, perdidos, mantenidos = await calculate_business_status({lead_id})
    assert lead_id in perdidos
    assert lead_id not in ganados


@pytest.mark.asyncio
async def test_multiple_leads_classified_correctly(ui_dev_db):
    from tests.seeds.business_status_helpers import seed_lead_with_payment
    ganado_id   = await seed_lead_with_payment(year_current=True,  year_prior=False)
    perdido_id  = await seed_lead_with_payment(year_current=False, year_prior=True)
    mantenido_id = await seed_lead_with_payment(year_current=True, year_prior=True)
    ganados, perdidos, mantenidos = await calculate_business_status({ganado_id, perdido_id, mantenido_id})
    assert ganado_id in ganados
    assert perdido_id in perdidos
    assert mantenido_id in mantenidos
    assert len({ganado_id, perdido_id, mantenido_id} & ganados & perdidos) == 0


# ─────────────────────────────────────────────────────────────
# Job 2 integration tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job2_updates_school_name(ui_dev_db, reporting_engine, reporting_session_factory, clean_reporting_db):
    from app.etl.dimensional_refresh import run_dimensional_refresh
    bind_test_reporting_database(reporting_session_factory)
    row = _do_transform(_base_row(lead_id=1, seller_id=1, school_name="Old Name"))
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row])
    await run_dimensional_refresh()
    async with reporting_engine.connect() as conn:
        name = (await conn.execute(
            text("SELECT school_name FROM report_line_items WHERE lead_id = 1 AND seller_id = 1")
        )).scalar()
    assert name != "Old Name"


@pytest.mark.asyncio
async def test_job2_does_not_touch_financials(ui_dev_db, reporting_engine, reporting_session_factory, clean_reporting_db):
    from app.etl.dimensional_refresh import run_dimensional_refresh
    bind_test_reporting_database(reporting_session_factory)
    row = _do_transform(_base_row(lead_id=1, seller_id=1, total=9999))
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row])
    await run_dimensional_refresh()
    async with reporting_engine.connect() as conn:
        total = (await conn.execute(text("SELECT total FROM report_line_items WHERE lead_id = 1"))).scalar()
    assert float(total) == 9999.0


@pytest.mark.asyncio
async def test_job2_does_not_touch_payment_status(ui_dev_db, reporting_engine, reporting_session_factory, clean_reporting_db):
    from app.etl.dimensional_refresh import run_dimensional_refresh
    bind_test_reporting_database(reporting_session_factory)
    row = _do_transform(_base_row(lead_id=1, seller_id=1, payment_status="Aprobado"))
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, [row])
    await run_dimensional_refresh()
    async with reporting_engine.connect() as conn:
        status = (await conn.execute(text("SELECT payment_status FROM report_line_items WHERE lead_id = 1"))).scalar()
    assert status == "Aprobado"


@pytest.mark.asyncio
async def test_job2_logs_success_to_etl_meta(ui_dev_db, reporting_engine, reporting_session_factory, clean_reporting_db):
    from app.etl.dimensional_refresh import run_dimensional_refresh
    bind_test_reporting_database(reporting_session_factory)
    await run_dimensional_refresh()
    async with reporting_engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT status FROM etl_meta WHERE job_name = 'dimensional_refresh' ORDER BY id DESC LIMIT 1")
        )).fetchone()
    assert row is not None
    assert row.status == "success"
