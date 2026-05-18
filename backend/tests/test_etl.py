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

from app.etl.exchange_rate_backfill import get_source_earliest_rate_date
from app.etl.payment_upsert import (
    EXTRACT_QUERY,
    _conversion_date,
    _convert_amount,
    _delete_cart_products,
    _incremental_since,
    _transform,
    _upsert,
    calculate_business_status,
)
from app.enums import PaymentStatus, ProductType, BusinessStatus, ExamCategory
from tests.conftest_reporting import bind_test_reporting_database


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _base_row(**overrides) -> dict:
    created_at = overrides.get("created_at", datetime(2025, 3, 15))
    payment_date = overrides.get("payment_date", date(2025, 3, 16))
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
        "state_names": ["CDMX"],
        "city_names": ["Ciudad de Mexico"],
        "cart_id": 1,
        "billing_status": "Aprobado",
        "created_at": created_at,
        "book_commission": 0,
        "exam_commission": 0,
        "payment_status": "Aprobado",
        "payment_date": payment_date,
        "payment_day": payment_date,
        "product_id": 1,
        "product_type": "exam",
        "exam_cat_name": "KET",
        "exam_date_type": "fixed",
        "quantity": 5,
        "total": 5000.00,
        "cost": 2000.00,
        "discount": 0,
        "has_paid_allocation": 1,
    }
    row.update(overrides)
    return row


def _default_rate_history() -> dict[tuple[str, str], dict[str, list]]:
    return {
        ("MXN", "USD"): {
            "dates": [date(2025, 3, 14), date(2025, 3, 16)],
            "rates": [0.059, 0.058],
        },
        ("COP", "MXN"): {
            "dates": [date(2025, 3, 14), date(2025, 3, 16)],
            "rates": [0.0047, 0.0048],
        },
        ("COP", "USD"): {
            "dates": [date(2025, 3, 14), date(2025, 3, 16)],
            "rates": [0.00028, 0.00029],
        },
        ("PEN", "MXN"): {
            "dates": [date(2025, 3, 14), date(2025, 3, 16)],
            "rates": [5.10, 5.15],
        },
        ("PEN", "USD"): {
            "dates": [date(2025, 3, 14), date(2025, 3, 16)],
            "rates": [0.27, 0.28],
        },
    }


def _do_transform(row: dict, ganados=None, perdidos=None, mantenidos=None, rate_history=None) -> dict:
    return _transform(
        row,
        ganados or set(),
        perdidos or set(),
        mantenidos or set(),
        rate_history or _default_rate_history(),
    )


async def _fetch_extract_rows_for_cart_product(session_factory, cart_product_id: int) -> list[dict]:
    query = text(EXTRACT_QUERY + " AND cp.id = :cart_product_id")
    async with session_factory() as session:
        result = await session.execute(
            query,
            {"since": datetime(2023, 1, 1), "cart_product_id": cart_product_id},
        )
        return [dict(row) for row in result.mappings().fetchall()]


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


def test_transform_computes_mxn_and_usd_for_mxn_rows():
    result = _do_transform(_base_row(total=1000, cost=400, site="mexico"))
    assert result["base_currency"] == "MXN"
    assert result["total_mxn"] == pytest.approx(1000.0)
    assert result["cost_mxn"] == pytest.approx(400.0)
    assert result["total_usd"] == pytest.approx(58.0)
    assert result["cost_usd"] == pytest.approx(23.2)


def test_transform_computes_mxn_and_usd_for_foreign_rows():
    result = _do_transform(_base_row(total=1000, cost=400, site="colombia"))
    assert result["base_currency"] == "COP"
    assert result["total_mxn"] == pytest.approx(4.8)
    assert result["cost_mxn"] == pytest.approx(1.92)
    assert result["total_usd"] == pytest.approx(0.29)
    assert result["cost_usd"] == pytest.approx(0.12)


def test_incremental_since_uses_configured_lookback(monkeypatch):
    now = datetime(2026, 5, 17, 12, 0, 0)
    monkeypatch.setenv("PAYMENT_UPSERT_LOOKBACK_HOURS", "6")

    assert _incremental_since(now) == datetime(2026, 5, 17, 6, 0, 0)


def test_conversion_date_uses_payment_date_first():
    row = _base_row(payment_date=date(2025, 3, 16), created_at=datetime(2025, 3, 10))
    assert _conversion_date(row) == date(2025, 3, 16)


def test_conversion_date_falls_back_to_created_at():
    row = _base_row(payment_date=None, created_at=datetime(2025, 3, 10, 9, 0, 0))
    assert _conversion_date(row) == date(2025, 3, 10)


def test_convert_amount_uses_previous_published_day():
    rate_history = {
        ("COP", "MXN"): {
            "dates": [date(2025, 3, 14), date(2025, 3, 17)],
            "rates": [0.0047, 0.0049],
        }
    }
    assert _convert_amount(1000, "COP", "MXN", date(2025, 3, 15), rate_history) == pytest.approx(4.7)


@pytest.mark.asyncio
async def test_get_source_earliest_rate_date_uses_payment_date_fallback(ui_dev_db):
    earliest_date = await get_source_earliest_rate_date()
    assert earliest_date is not None
    assert isinstance(earliest_date, date)


@pytest.mark.asyncio
async def test_extract_query_does_not_duplicate_when_one_student_has_multiple_student_payments(
    ui_dev_db,
    session_factory,
):
    target_cart_product_id = 1001
    async with session_factory() as session:
        async with session.begin():
            await session.execute(text("""
                INSERT INTO `lead` (id, name, site, zoneId, campaign)
                VALUES (1001, 'Colegio Dup Uno', 'mexico', 1, 'etl-test')
            """))
            await session.execute(text("""
                INSERT INTO lead_address (id, leadId, stateName, city, comments, deletedAt, isFavorite)
                VALUES (1001, 1001, 'CDMX', 'Mexico City', '', NULL, 1)
            """))
            await session.execute(text("""
                INSERT INTO seller_lead (id, sellerId, leadId, businessStatus)
                VALUES (1001, 1, 1001, 'ganado')
            """))
            await session.execute(text("""
                INSERT INTO cart (id, sellerLeadId, total, cost, createdAt, deletedAt)
                VALUES (1001, 1001, 1000, 500, '2025-11-01 10:00:00', NULL)
            """))
            await session.execute(text("""
                INSERT INTO cart (id, sellerLeadId, total, cost, createdAt, deletedAt)
                VALUES (1002, 1001, 500, 250, '2025-11-02 10:00:00', NULL)
            """))
            await session.execute(text("""
                INSERT INTO payment (
                    id, quantity, status, createdAt, updatedAt, cartId, `use`, comments, billingStatus,
                    studentId, paymentDate
                ) VALUES
                    (1001, 1000, 'Aprobado', '2025-11-01 10:00:00', '2025-11-01 10:00:00', 1001, '', '', '', 0, '2025-11-01'),
                    (1002, 500, 'Aprobado', '2025-11-02 10:00:00', '2025-11-02 10:00:00', 1002, '', '', '', 0, '2025-11-02')
            """))
            await session.execute(text("""
                INSERT INTO cart_product (id, cartId, productId, quantity, total, cost, testDate, deletedAt)
                VALUES (1001, 1001, 1, 1, 1000, 500, '2025-11-10', NULL)
            """))
            await session.execute(text("""
                INSERT INTO student (id, cartProductId)
                VALUES (1001, 1001)
            """))
            await session.execute(text("""
                INSERT INTO student_payments (student_id, payment_id, amount)
                VALUES
                    (1001, 1001, 500.00),
                    (1001, 1002, 500.00)
            """))

    rows = await _fetch_extract_rows_for_cart_product(session_factory, target_cart_product_id)

    assert len(rows) == 1
    assert rows[0]["cart_product_id"] == target_cart_product_id
    assert rows[0]["has_paid_allocation"] == 1


@pytest.mark.asyncio
async def test_extract_query_does_not_duplicate_when_multiple_students_share_one_cart_product(
    ui_dev_db,
    session_factory,
):
    target_cart_product_id = 1101
    async with session_factory() as session:
        async with session.begin():
            await session.execute(text("""
                INSERT INTO `lead` (id, name, site, zoneId, campaign)
                VALUES (1101, 'Colegio Dup Dos', 'mexico', 1, 'etl-test')
            """))
            await session.execute(text("""
                INSERT INTO lead_address (id, leadId, stateName, city, comments, deletedAt, isFavorite)
                VALUES (1101, 1101, 'Jalisco', 'Guadalajara', '', NULL, 1)
            """))
            await session.execute(text("""
                INSERT INTO seller_lead (id, sellerId, leadId, businessStatus)
                VALUES (1101, 1, 1101, 'ganado')
            """))
            await session.execute(text("""
                INSERT INTO cart (id, sellerLeadId, total, cost, createdAt, deletedAt)
                VALUES (1101, 1101, 1200, 600, '2025-11-03 10:00:00', NULL)
            """))
            await session.execute(text("""
                INSERT INTO payment (
                    id, quantity, status, createdAt, updatedAt, cartId, `use`, comments, billingStatus,
                    studentId, paymentDate
                ) VALUES
                    (1101, 1200, 'Aprobado', '2025-11-03 10:00:00', '2025-11-03 10:00:00', 1101, '', '', '', 0, '2025-11-03')
            """))
            await session.execute(text("""
                INSERT INTO cart_product (id, cartId, productId, quantity, total, cost, testDate, deletedAt)
                VALUES (1101, 1101, 2, 2, 1200, 600, '2025-11-12', NULL)
            """))
            await session.execute(text("""
                INSERT INTO student (id, cartProductId)
                VALUES
                    (1101, 1101),
                    (1102, 1101)
            """))
            await session.execute(text("""
                INSERT INTO student_payments (student_id, payment_id, amount)
                VALUES
                    (1101, 1101, 600.00),
                    (1102, 1101, 600.00)
            """))

    rows = await _fetch_extract_rows_for_cart_product(session_factory, target_cart_product_id)

    assert len(rows) == 1
    assert rows[0]["cart_product_id"] == target_cart_product_id
    assert rows[0]["has_paid_allocation"] == 1


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
async def test_delete_cart_products_removes_soft_deleted_rows(reporting_engine, reporting_session_factory, clean_reporting_db):
    bind_test_reporting_database(reporting_session_factory)
    rows = [
        _do_transform(_base_row(cart_product_id=17)),
        _do_transform(_base_row(cart_product_id=18, lead_id=18, cart_id=18)),
    ]
    async with reporting_session_factory() as session:
        async with session.begin():
            await _upsert(session, rows)
    async with reporting_session_factory() as session:
        async with session.begin():
            await _delete_cart_products(session, [17])
    async with reporting_engine.connect() as conn:
        remaining_ids = [row[0] for row in (await conn.execute(
            text("SELECT cart_product_id FROM report_line_items ORDER BY cart_product_id")
        )).fetchall()]
    assert remaining_ids == [18]


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
        result = (await conn.execute(text("SELECT total, cost, total_usd, cost_usd FROM report_line_items"))).fetchone()
    assert float(result.total) == 1000.0
    assert float(result.cost) == 500.0
    assert float(result.total_usd) == pytest.approx(58.0)
    assert float(result.cost_usd) == pytest.approx(29.0)


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
