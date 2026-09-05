from datetime import date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text

from app.config import settings
from app.etl.dimensional_refresh import run_dimensional_refresh
from app.etl.exchange_rate_backfill import ensure_exchange_rates_for_range
from app.etl.frankfurter import (
    FXRateFetchError,
    fetch_frankfurter_rate,
    fetch_frankfurter_time_series,
)
from app.etl.startup_backfill import (
    STARTUP_BACKFILL_FLOOR,
    get_startup_backfill_since,
    run_startup_backfill_if_needed,
)
from app.etl.shared import (
    SYNC_FALLBACK,
    SYNC_MAX_CATCHUP,
    SYNC_OVERLAP,
    calculate_business_status,
    convert_currency,
    extract_dimensions,
    get_incremental_since,
    get_rate,
    get_source_clock_offset,
    to_source_time,
    resolve_business_status,
)
from app.etl.upsert import run_upsert
from app.enums import BusinessStatus, ETLJobName
from tests.conftest_reporting import bind_test_reporting_database


def _base_dimension_row(**overrides) -> dict:
    row = {
        "seller_id": 1,
        "seller_name": "Ana Garcia",
        "lead_id": 1,
        "school_name": "Colegio Test",
        "site": "mexico",
        "zone_name": "IH Mexico",
        "state_name": "CDMX",
        "city": "Ciudad de Mexico",
        "all_states": "CDMX||Jalisco",
        "all_cities": "Ciudad de Mexico||Guadalajara",
        "created_at": datetime(2025, 1, 15, 10, 0, 0),
        "payment_date": date(2025, 1, 16),
    }
    row.update(overrides)
    return row


def test_extract_dimensions_splits_multi_value_geo():
    result = extract_dimensions(_base_dimension_row())
    assert result["all_states"] == ["CDMX", "Jalisco"]
    assert result["all_cities"] == ["Ciudad de Mexico", "Guadalajara"]
    assert result["state_names"] == ["CDMX", "Jalisco"]
    assert result["city_names"] == ["Ciudad de Mexico", "Guadalajara"]
    assert result["year"] == 2025
    assert result["month"] == 1


def test_resolve_business_status_prefers_matching_bucket():
    assert resolve_business_status(1, {1}, set(), set()) == BusinessStatus.GANADO.value
    assert resolve_business_status(2, set(), {2}, set()) == BusinessStatus.PERDIDO.value
    assert resolve_business_status(3, set(), set(), {3}) == BusinessStatus.MANTENIDO.value
    assert resolve_business_status(4, set(), set(), set()) == BusinessStatus.UNCATEGORIZED.value


@pytest.mark.asyncio
async def test_convert_currency_uses_exact_rate():
    rates = {
        (date(2025, 1, 16), "COP", "MXN"): 0.0048,
        (date(2025, 1, 16), "COP", "USD"): 0.00029,
    }
    amount_mxn, amount_usd = await convert_currency(1000, "colombia", date(2025, 1, 16), rates)
    assert amount_mxn == pytest.approx(4.8)
    assert amount_usd == pytest.approx(0.29)


@pytest.mark.asyncio
async def test_fetch_frankfurter_rate_uses_pair_endpoint_and_requested_date():
    requested_url: str | None = None
    requested_params: dict[str, str] | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested_url, requested_params
        requested_url = str(request.url)
        requested_params = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "date": "2025-01-16",
                "base": "COP",
                "quote": "MXN",
                "rate": 0.0048,
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider_date, rate = await fetch_frankfurter_rate(
            "COP",
            "MXN",
            date(2025, 1, 16),
            client=client,
        )

    assert requested_url is not None and "/v2/rate/COP/MXN" in requested_url
    assert requested_params == {"date": "2025-01-16"}
    assert provider_date == date(2025, 1, 16)
    assert rate == pytest.approx(0.0048)


@pytest.mark.asyncio
async def test_fetch_frankfurter_rate_raises_domain_error_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "not found"}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(FXRateFetchError, match="COP/MXN"):
            await fetch_frankfurter_rate(
                "COP",
                "MXN",
                date(2025, 1, 16),
                client=client,
            )


@pytest.mark.asyncio
async def test_fetch_frankfurter_time_series_uses_date_range_endpoint():
    requested_url: str | None = None
    requested_params: dict[str, str] | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested_url, requested_params
        requested_url = str(request.url)
        requested_params = dict(request.url.params)
        return httpx.Response(
            200,
            json=[
                {
                    "date": "2025-01-01",
                    "base": "COP",
                    "quote": "MXN",
                    "rate": 0.0048,
                },
                {
                    "date": "2025-01-02",
                    "base": "COP",
                    "quote": "MXN",
                    "rate": 0.0049,
                },
            ],
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        rows = await fetch_frankfurter_time_series(
            "COP",
            ["MXN"],
            date(2025, 1, 1),
            date(2025, 1, 2),
            client=client,
        )

    assert requested_url is not None and "/v2/rates" in requested_url
    assert requested_params == {
        "base": "COP",
        "quotes": "MXN",
        "from": "2025-01-01",
        "to": "2025-01-02",
    }
    assert rows == [
        {
            "date": date(2025, 1, 1),
            "from_currency": "COP",
            "to_currency": "MXN",
            "rate": pytest.approx(0.0048),
        },
        {
            "date": date(2025, 1, 2),
            "from_currency": "COP",
            "to_currency": "MXN",
            "rate": pytest.approx(0.0049),
        },
    ]


@pytest.mark.asyncio
async def test_get_rate_does_not_fallback_to_today_rate(monkeypatch):
    requested_rate_date = date(2025, 1, 16)
    rates = {
        (date.today(), "COP", "MXN"): 999.0,
    }

    async def fake_fetch_live_rate(rate_date: date, from_cur: str, to_cur: str) -> float:
        assert rate_date == requested_rate_date
        assert from_cur == "COP"
        assert to_cur == "MXN"
        return 0.0048

    monkeypatch.setattr("app.etl.shared.fetch_live_rate", fake_fetch_live_rate)

    rate = await get_rate(requested_rate_date, "COP", "MXN", rates)

    assert rate == pytest.approx(0.0048)
    assert rates[(requested_rate_date, "COP", "MXN")] == pytest.approx(0.0048)


@pytest.mark.asyncio
async def test_exchange_rate_backfill_honors_full_requested_range(
    reporting_engine,
    reporting_session_factory,
    clean_reporting_db,
    monkeypatch,
):
    bind_test_reporting_database(reporting_session_factory)
    async with reporting_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY"
            )
        )

    async def fake_fetch_time_series(
        base_currency: str,
        quote_currencies: list[str],
        start_date: date,
        end_date: date,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> list[dict[str, object]]:
        del client
        rows: list[dict[str, object]] = []
        current_date = start_date
        while current_date <= end_date:
            for quote_currency in quote_currencies:
                rows.append(
                    {
                        "date": current_date,
                        "from_currency": base_currency,
                        "to_currency": quote_currency,
                        "rate": float(len(base_currency) + len(quote_currency)),
                    }
                )
            current_date += timedelta(days=1)
        return rows

    monkeypatch.setattr(
        "app.etl.exchange_rate_backfill.fetch_frankfurter_time_series", fake_fetch_time_series
    )

    await ensure_exchange_rates_for_range(date(2025, 1, 1), date(2025, 1, 2))

    async with reporting_engine.connect() as conn:
        count = (await conn.execute(text("SELECT COUNT(*) FROM exchange_rates"))).scalar()

    assert count == 10


@pytest.mark.asyncio
async def test_business_status_classifies_seeded_leads(ui_dev_db):
    from tests.seeds.business_status_helpers import seed_lead_with_payment

    ganado_id = await seed_lead_with_payment(year_current=True, year_prior=False)
    perdido_id = await seed_lead_with_payment(year_current=False, year_prior=True)
    mantenido_id = await seed_lead_with_payment(year_current=True, year_prior=True)

    ganados, perdidos, mantenidos = await calculate_business_status(
        {ganado_id, perdido_id, mantenido_id}
    )
    assert ganado_id in ganados
    assert perdido_id in perdidos
    assert mantenido_id in mantenidos


@pytest.mark.asyncio(loop_scope="session")
async def test_upsert_populates_all_three_reporting_tables(ui_dev_reporting_db, reporting_engine):
    async with reporting_engine.connect() as conn:
        payment_count = (await conn.execute(text("SELECT COUNT(*) FROM report_payments"))).scalar()
        line_item_count = (
            await conn.execute(text("SELECT COUNT(*) FROM report_line_items"))
        ).scalar()
        allocation_count = (
            await conn.execute(text("SELECT COUNT(*) FROM report_payment_allocations"))
        ).scalar()

    assert payment_count == 15
    assert line_item_count == 16
    assert allocation_count > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_products_without_students_get_allocated_from_remainder(
    ui_dev_reporting_db, reporting_engine
):
    # cart_product_id=14 is an Admin Fee (UNCATEGORIZED, no students) on cart 11.
    # Cart 11 has two payments totalling 500, and cp14 is the sole cart_product,
    # so it receives 100% of each payment's remainder.
    # Verify: first_payment_date is set, include_in_product_breakdown = True,
    # and allocations sum to 500.
    async with reporting_engine.connect() as conn:
        row = (
            await conn.execute(
                text("""
                    SELECT expected_total, first_payment_date, include_in_product_breakdown, payment_status
                    FROM report_line_items
                    WHERE cart_product_id = 14
                """)
            )
        ).fetchone()
        alloc_total = (
            await conn.execute(
                text("""
                    SELECT COALESCE(SUM(allocated_amount), 0)
                    FROM report_payment_allocations
                    WHERE cart_product_id = 14
                """)
            )
        ).scalar()

    assert row is not None
    assert float(row.expected_total) == 500.0
    assert row.first_payment_date is not None
    assert row.include_in_product_breakdown is True
    assert row.payment_status == "Aprobado"
    assert float(alloc_total) == pytest.approx(500.0)


@pytest.mark.asyncio(loop_scope="session")
async def test_line_items_student_counts_without_duplication(ui_dev_reporting_db, reporting_engine):
    async with reporting_engine.connect() as conn:
        row = (
            await conn.execute(
                text("""
                    SELECT student_count, payment_count
                    FROM report_line_items
                    WHERE cart_product_id = 4
                """)
            )
        ).fetchone()

    assert row is not None
    assert row.student_count == 2
    assert row.payment_count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_payment_allocations_sum_back_to_payment_amount(
    ui_dev_reporting_db, reporting_engine
):
    async with reporting_engine.connect() as conn:
        payment_total = (
            await conn.execute(text("SELECT amount FROM report_payments WHERE payment_id = 5"))
        ).scalar()
        allocation_total = (
            await conn.execute(
                text("""
                    SELECT COALESCE(SUM(allocated_amount), 0)
                    FROM report_payment_allocations
                    WHERE payment_id = 5
                """)
            )
        ).scalar()

    assert float(payment_total) == 1500.0
    assert float(allocation_total) == pytest.approx(1500.0)


@pytest.mark.asyncio(loop_scope="session")
async def test_book_without_students_gets_remainder_allocation(
    ui_dev_reporting_db, reporting_engine
):
    # cart_product_id=19 is a Prep Book on cart 14 with no student entry.
    # Payment 15 (quantity=1300, Aprobado) covers cart 14 which has two cart_products:
    #   cp18 PET Exam total=1000, cp19 Prep Book total=300  →  cart_total=1300
    # student_amount for cp18 = 1000; remainder = 1300 - 1000 = 300
    # cp19 (no-student) gets 100% of remainder = 300.
    # first_payment_date should be set; include_in_product_breakdown = True.
    async with reporting_engine.connect() as conn:
        row = (
            await conn.execute(
                text("""
                    SELECT product_type, first_payment_date, include_in_product_breakdown, payment_status
                    FROM report_line_items
                    WHERE cart_product_id = 19
                """)
            )
        ).fetchone()
        alloc_row = (
            await conn.execute(
                text("""
                    SELECT COALESCE(SUM(allocated_amount), 0) AS total
                    FROM report_payment_allocations
                    WHERE cart_product_id = 19
                """)
            )
        ).fetchone()

    assert row is not None
    assert row.product_type == "book"
    assert row.first_payment_date is not None
    assert row.include_in_product_breakdown is True
    assert row.payment_status == "Aprobado"
    assert float(alloc_row.total) == pytest.approx(300.0)


@pytest.mark.asyncio(loop_scope="session")
async def test_exam_on_same_cart_as_book_uses_student_amount(ui_dev_reporting_db, reporting_engine):
    # cart_product_id=18 is a PET Exam on cart 14 with student 16 (student_payment=1000).
    # The allocation must use the exact student_payment amount (1000), not a
    # proportional share of the cart total.
    async with reporting_engine.connect() as conn:
        row = (
            await conn.execute(
                text("""
                    SELECT product_type, student_count, payment_count, include_in_product_breakdown
                    FROM report_line_items
                    WHERE cart_product_id = 18
                """)
            )
        ).fetchone()
        alloc_total = (
            await conn.execute(
                text("""
                    SELECT COALESCE(SUM(allocated_amount), 0)
                    FROM report_payment_allocations
                    WHERE cart_product_id = 18
                """)
            )
        ).scalar()

    assert row is not None
    assert row.product_type == "exam"
    assert float(alloc_total) == pytest.approx(1000.0)
    assert row.student_count == 1
    assert row.payment_count == 1
    assert row.include_in_product_breakdown is True


@pytest.mark.asyncio(loop_scope="session")
async def test_allocations_on_mixed_cart_sum_to_payment_amount(
    ui_dev_reporting_db, reporting_engine
):
    # On cart 14, the exam (cp18, student_amount=1000) and book (cp19, remainder=300)
    # allocations together must equal payment 15 quantity (1300).
    # Verifies remainder approach: no money created or lost.
    async with reporting_engine.connect() as conn:
        total = (
            await conn.execute(
                text("""
                    SELECT COALESCE(SUM(allocated_amount), 0)
                    FROM report_payment_allocations
                    WHERE cart_product_id IN (18, 19)
                """)
            )
        ).scalar()

    assert float(total) == pytest.approx(1300.0)


@pytest.mark.asyncio(loop_scope="session")
async def test_book_with_existing_student_uses_student_amount_not_remainder(
    ui_dev_reporting_db, reporting_engine
):
    # cart_product_id=6 is a Prep Book on cart 5 with student 7 (student_payment=300).
    # Since it has a student_payments entry, it uses the exact student amount (300),
    # not a proportional remainder share.
    async with reporting_engine.connect() as conn:
        row = (
            await conn.execute(
                text("""
                    SELECT product_type, student_count, include_in_product_breakdown
                    FROM report_line_items
                    WHERE cart_product_id = 6
                """)
            )
        ).fetchone()
        alloc_total = (
            await conn.execute(
                text("""
                    SELECT COALESCE(SUM(allocated_amount), 0)
                    FROM report_payment_allocations
                    WHERE cart_product_id = 6
                """)
            )
        ).scalar()

    assert row is not None
    assert row.product_type == "book"
    assert float(alloc_total) == pytest.approx(300.0)
    assert row.student_count == 1
    assert row.include_in_product_breakdown is True


@pytest.mark.asyncio(loop_scope="session")
async def test_first_payment_date_set_on_line_items(ui_dev_reporting_db, reporting_engine):
    # cp19 is the Prep Book on cart 14. Payment 15 has paymentDate='2025-03-05'.
    # first_payment_date must equal that sanitised payment date.
    async with reporting_engine.connect() as conn:
        fpd = (
            await conn.execute(
                text("""
                    SELECT first_payment_date
                    FROM report_line_items
                    WHERE cart_product_id = 19
                """)
            )
        ).scalar()

    from datetime import date as date_type

    assert fpd is not None
    assert isinstance(fpd, date_type)
    # Payment 15 paymentDate = '2025-03-05' → first_payment_date must be 2025-03-05
    assert fpd == date_type(2025, 3, 5)


@pytest.mark.asyncio(loop_scope="session")
async def test_allocation_payment_date_is_payments_actual_date(
    ui_dev_reporting_db, reporting_engine
):
    # Allocation row for payment 15 / cp18 must carry payment_date = 2025-03-05
    # (the actual paymentDate of payment 15), not cart.createdAt.
    # cart 14 createdAt = '2025-03-01', payment 15 paymentDate = '2025-03-05'.
    async with reporting_engine.connect() as conn:
        payment_date = (
            await conn.execute(
                text("""
                    SELECT payment_date
                    FROM report_payment_allocations
                    WHERE payment_id = 15 AND cart_product_id = 18
                """)
            )
        ).scalar()

    from datetime import date as date_type

    assert payment_date is not None
    assert payment_date == date_type(2025, 3, 5)


@pytest.mark.asyncio
async def test_deleted_cart_products_are_removed_on_rerun(
    ui_dev_db,
    reporting_engine,
    reporting_session_factory,
    session_factory,
):
    bind_test_reporting_database(reporting_session_factory)

    async with reporting_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY"
            )
        )

    async with reporting_session_factory() as session:
        async with session.begin():
            today = date.today()
            for row in [
                {"date": today, "from_currency": "MXN", "to_currency": "USD", "rate": 1.0},
                {"date": today, "from_currency": "COP", "to_currency": "MXN", "rate": 1.0},
                {"date": today, "from_currency": "COP", "to_currency": "USD", "rate": 1.0},
                {"date": today, "from_currency": "PEN", "to_currency": "MXN", "rate": 1.0},
                {"date": today, "from_currency": "PEN", "to_currency": "USD", "rate": 1.0},
            ]:
                await session.execute(
                    text("""
                        INSERT INTO exchange_rates (date, from_currency, to_currency, rate)
                        VALUES (:date, :from_currency, :to_currency, :rate)
                        ON CONFLICT (date, from_currency, to_currency) DO UPDATE
                        SET rate = EXCLUDED.rate
                    """),
                    row,
                )

    await run_upsert(since=settings.payment_upsert_initial_since, job_name=ETLJobName.UPSERT)

    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                text("UPDATE cart_product SET deletedAt = '2026-05-18 10:00:00' WHERE id = 4")
            )

    await run_upsert(since=datetime(2026, 5, 18, 0, 0, 0), job_name=ETLJobName.UPSERT)

    async with reporting_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT COUNT(*) FROM report_line_items WHERE cart_product_id = 4")
            )
        ).scalar()

    assert row == 0


@pytest.mark.asyncio
async def test_dimensional_refresh_updates_both_main_tables(
    ui_dev_db,
    reporting_engine,
    reporting_session_factory,
    session_factory,
):
    bind_test_reporting_database(reporting_session_factory)

    async with reporting_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY"
            )
        )

    async with reporting_session_factory() as session:
        async with session.begin():
            today = date.today()
            for row in [
                {"date": today, "from_currency": "MXN", "to_currency": "USD", "rate": 1.0},
                {"date": today, "from_currency": "COP", "to_currency": "MXN", "rate": 1.0},
                {"date": today, "from_currency": "COP", "to_currency": "USD", "rate": 1.0},
                {"date": today, "from_currency": "PEN", "to_currency": "MXN", "rate": 1.0},
                {"date": today, "from_currency": "PEN", "to_currency": "USD", "rate": 1.0},
            ]:
                await session.execute(
                    text("""
                        INSERT INTO exchange_rates (date, from_currency, to_currency, rate)
                        VALUES (:date, :from_currency, :to_currency, :rate)
                        ON CONFLICT (date, from_currency, to_currency) DO UPDATE
                        SET rate = EXCLUDED.rate
                    """),
                    row,
                )

    await run_upsert(since=settings.payment_upsert_initial_since, job_name=ETLJobName.UPSERT)

    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                text("UPDATE `lead` SET name = 'Colegio Renombrado' WHERE id = 1")
            )

    await run_dimensional_refresh()

    async with reporting_engine.connect() as conn:
        payment_name = (
            await conn.execute(
                text("SELECT school_name FROM report_payments WHERE lead_id = 1 LIMIT 1")
            )
        ).scalar()
        line_item_name = (
            await conn.execute(
                text("SELECT school_name FROM report_line_items WHERE lead_id = 1 LIMIT 1")
            )
        ).scalar()

    assert payment_name == "Colegio Renombrado"
    assert line_item_name == "Colegio Renombrado"


@pytest.mark.asyncio
async def test_startup_backfill_uses_floor_when_no_successful_payment_sync_runs(
    reporting_engine,
    reporting_session_factory,
    clean_reporting_db,
):
    bind_test_reporting_database(reporting_session_factory)
    async with reporting_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY"
            )
        )

    since = await get_startup_backfill_since(now=datetime(2026, 5, 21, 12, 0, 0))

    assert since == STARTUP_BACKFILL_FLOOR


@pytest.mark.asyncio
async def test_startup_backfill_skips_when_latest_upsert_is_recent(
    reporting_engine,
    reporting_session_factory,
    clean_reporting_db,
):
    bind_test_reporting_database(reporting_session_factory)
    current_time = datetime(2026, 5, 21, 12, 0, 0)
    async with reporting_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY"
            )
        )

    async with reporting_session_factory() as session:
        async with session.begin():
            await session.execute(
                text("""
                    INSERT INTO etl_meta (job_name, run_at, rows_processed, status, error, duration_seconds)
                    VALUES (:job_name, :run_at, 10, 'success', NULL, 5)
                """),
                {
                    "job_name": ETLJobName.UPSERT.value,
                    "run_at": current_time - timedelta(hours=2, minutes=59),
                },
            )

    since = await get_startup_backfill_since(now=current_time)

    assert since is None


@pytest.mark.asyncio
async def test_startup_backfill_uses_latest_successful_payment_sync_run(
    reporting_engine,
    reporting_session_factory,
    clean_reporting_db,
):
    bind_test_reporting_database(reporting_session_factory)
    current_time = datetime(2026, 5, 21, 12, 0, 0)
    expected_since = current_time - timedelta(hours=5)
    async with reporting_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY"
            )
        )

    async with reporting_session_factory() as session:
        async with session.begin():
            await session.execute(
                text("""
                    INSERT INTO etl_meta (job_name, run_at, rows_processed, status, error, duration_seconds)
                    VALUES
                        (:failed_job_name, :failed_run_at, 0, 'failed', 'boom', 5),
                        (:dimensional_job_name, :dimensional_run_at, 10, 'success', NULL, 5),
                        (:upsert_job_name, :upsert_run_at, 10, 'success', NULL, 5)
                """),
                {
                    "failed_job_name": ETLJobName.UPSERT.value,
                    "failed_run_at": current_time - timedelta(hours=1),
                    "dimensional_job_name": ETLJobName.DIMENSIONAL_REFRESH.value,
                    "dimensional_run_at": current_time - timedelta(minutes=30),
                    "upsert_job_name": ETLJobName.STARTUP_BACKFILL.value,
                    "upsert_run_at": expected_since,
                },
            )

    since = await get_startup_backfill_since(now=current_time)

    assert since == expected_since


@pytest.mark.asyncio
async def test_run_startup_backfill_if_needed_calls_run_upsert_with_startup_job_name(
    reporting_engine,
    reporting_session_factory,
    clean_reporting_db,
    monkeypatch,
):
    bind_test_reporting_database(reporting_session_factory)
    async with reporting_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY"
            )
        )
    calls: list[tuple[datetime, ETLJobName]] = []

    async def fake_run_upsert(
        *, since: datetime | None = None, job_name: ETLJobName = ETLJobName.UPSERT
    ) -> None:
        calls.append((since, job_name))

    monkeypatch.setattr("app.etl.startup_backfill.run_upsert", fake_run_upsert)

    await run_startup_backfill_if_needed(now=datetime(2026, 5, 21, 12, 0, 0))

    assert calls == [(STARTUP_BACKFILL_FLOOR, ETLJobName.STARTUP_BACKFILL)]


# ─────────────────────────────────────────────────────────────
# Incremental sync watermark
# ─────────────────────────────────────────────────────────────


async def _log_run(session_factory, job_name: str, status: str, run_at: datetime) -> None:
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                text("""
                    INSERT INTO etl_meta (job_name, run_at, rows_processed, status, duration_seconds)
                    VALUES (:job_name, :run_at, 0, :status, 0)
                """),
                {"job_name": job_name, "run_at": run_at, "status": status},
            )


@pytest.mark.asyncio
async def test_incremental_since_falls_back_when_no_successful_run(
    reporting_session_factory, clean_reporting_db
):
    bind_test_reporting_database(reporting_session_factory)
    now = datetime(2026, 9, 5, 12, 0, 0)
    assert await get_incremental_since(now=now) == now - SYNC_FALLBACK


@pytest.mark.asyncio
async def test_incremental_since_resumes_from_last_success_with_overlap(
    reporting_session_factory, clean_reporting_db
):
    """run_at is stamped at completion, so resume before it or mid-run updates are lost."""
    bind_test_reporting_database(reporting_session_factory)
    last_success = datetime(2026, 9, 5, 9, 12, 18)
    await _log_run(reporting_session_factory, "upsert", "success", last_success)

    now = datetime(2026, 9, 5, 12, 12, 15)
    assert await get_incremental_since(now=now) == last_success - SYNC_OVERLAP


@pytest.mark.asyncio
async def test_incremental_since_ignores_failed_runs(reporting_session_factory, clean_reporting_db):
    """The regression guard: a failed run must not advance the watermark, or its
    window is skipped forever."""
    bind_test_reporting_database(reporting_session_factory)
    last_success = datetime(2026, 9, 5, 0, 12, 18)
    await _log_run(reporting_session_factory, "upsert", "success", last_success)
    await _log_run(reporting_session_factory, "upsert", "failed", datetime(2026, 9, 5, 3, 12, 17))

    now = datetime(2026, 9, 5, 6, 12, 15)
    since = await get_incremental_since(now=now)
    assert since == last_success - SYNC_OVERLAP
    # The 03:12 window that failed is still covered by the next run.
    assert since < datetime(2026, 9, 5, 3, 12, 17)


@pytest.mark.asyncio
async def test_incremental_since_caps_catchup_after_long_outage(
    reporting_session_factory, clean_reporting_db
):
    bind_test_reporting_database(reporting_session_factory)
    await _log_run(reporting_session_factory, "upsert", "success", datetime(2025, 1, 1, 0, 0, 0))

    now = datetime(2026, 9, 5, 12, 0, 0)
    assert await get_incremental_since(now=now) == now - SYNC_MAX_CATCHUP


@pytest.mark.asyncio
async def test_incremental_since_counts_startup_backfill_as_a_sync(
    reporting_session_factory, clean_reporting_db
):
    bind_test_reporting_database(reporting_session_factory)
    last_success = datetime(2026, 9, 5, 9, 0, 0)
    await _log_run(reporting_session_factory, "startup_backfill", "success", last_success)

    now = datetime(2026, 9, 5, 12, 0, 0)
    assert await get_incremental_since(now=now) == last_success - SYNC_OVERLAP


# ─────────────────────────────────────────────────────────────
# Source-clock alignment
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_source_clock_offset_is_a_valid_utc_offset():
    """Measured live from the source server, so assert the invariant rather than a
    value: real UTC offsets are whole quarter-hours within +/-14h."""
    offset = await get_source_clock_offset()
    seconds = offset.total_seconds()
    assert seconds % 900 == 0
    assert abs(seconds) <= 14 * 3600


@pytest.mark.asyncio
async def test_to_source_time_shifts_the_bound_onto_the_source_clock():
    """The production failure: app on UTC, source on UTC-6, so an app-derived
    bound landed ~6h in the future and `updatedAt > :since` matched nothing."""
    app_bound = datetime(2026, 9, 5, 16, 33, 34)  # UTC, as the container sees it
    shifted = await to_source_time(app_bound, offset=timedelta(hours=6))
    assert shifted == datetime(2026, 9, 5, 10, 33, 34)  # source-local


@pytest.mark.asyncio
async def test_to_source_time_is_a_noop_when_clocks_agree():
    moment = datetime(2026, 9, 5, 12, 0, 0)
    assert await to_source_time(moment, offset=timedelta(0)) == moment


@pytest.mark.asyncio
async def test_extract_all_applies_the_source_clock_offset(monkeypatch):
    """Regression guard: the bound must be translated before it reaches SQL."""
    seen: dict = {}

    async def fake_to_source_time(moment):
        seen["bound"] = moment - timedelta(hours=6)
        return seen["bound"]

    monkeypatch.setattr("app.etl.upsert.to_source_time", fake_to_source_time)
    await run_upsert(since=datetime(2026, 9, 5, 16, 33, 34), job_name=ETLJobName.UPSERT)
    assert seen["bound"] == datetime(2026, 9, 5, 10, 33, 34)
