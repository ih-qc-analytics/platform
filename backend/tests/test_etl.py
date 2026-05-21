from datetime import date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text

from app.config import settings
from app.etl.dimensional_refresh import run_dimensional_refresh
from app.etl.exchange_rate_backfill import ensure_exchange_rates_for_range
from app.etl.frankfurter import FXRateFetchError, fetch_frankfurter_rate, fetch_frankfurter_time_series
from app.etl.startup_backfill import (
    STARTUP_BACKFILL_FLOOR,
    get_startup_backfill_since,
    run_startup_backfill_if_needed,
)
from app.etl.shared import (
    calculate_business_status,
    convert_currency,
    extract_dimensions,
    get_rate,
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
            text("TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY")
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

    monkeypatch.setattr("app.etl.exchange_rate_backfill.fetch_frankfurter_time_series", fake_fetch_time_series)

    await ensure_exchange_rates_for_range(date(2025, 1, 1), date(2025, 1, 2))

    async with reporting_engine.connect() as conn:
        count = (
            await conn.execute(text("SELECT COUNT(*) FROM exchange_rates"))
        ).scalar()

    assert count == 10


@pytest.mark.asyncio
async def test_business_status_classifies_seeded_leads(ui_dev_db):
    from tests.seeds.business_status_helpers import seed_lead_with_payment

    ganado_id = await seed_lead_with_payment(year_current=True, year_prior=False)
    perdido_id = await seed_lead_with_payment(year_current=False, year_prior=True)
    mantenido_id = await seed_lead_with_payment(year_current=True, year_prior=True)

    ganados, perdidos, mantenidos = await calculate_business_status({ganado_id, perdido_id, mantenido_id})
    assert ganado_id in ganados
    assert perdido_id in perdidos
    assert mantenido_id in mantenidos


@pytest.mark.asyncio(loop_scope="session")
async def test_upsert_populates_all_three_reporting_tables(ui_dev_reporting_db, reporting_engine):
    async with reporting_engine.connect() as conn:
        payment_count = (await conn.execute(text("SELECT COUNT(*) FROM report_payments"))).scalar()
        line_item_count = (await conn.execute(text("SELECT COUNT(*) FROM report_line_items"))).scalar()
        allocation_count = (await conn.execute(text("SELECT COUNT(*) FROM report_payment_allocations"))).scalar()

    assert payment_count == 14
    assert line_item_count == 14
    assert allocation_count > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_line_items_include_unpaid_products_in_approved_payment_carts(ui_dev_reporting_db, reporting_engine):
    async with reporting_engine.connect() as conn:
        row = (
            await conn.execute(
                text("""
                    SELECT expected_total, paid_total, include_in_product_breakdown, payment_status
                    FROM report_line_items
                    WHERE cart_product_id = 14
                """)
            )
        ).fetchone()

    assert row is not None
    assert float(row.expected_total) == 500.0
    assert float(row.paid_total) == 0.0
    assert row.include_in_product_breakdown is False
    assert row.payment_status == "Aprobado"


@pytest.mark.asyncio(loop_scope="session")
async def test_line_items_aggregate_paid_totals_without_duplication(ui_dev_reporting_db, reporting_engine):
    async with reporting_engine.connect() as conn:
        row = (
            await conn.execute(
                text("""
                    SELECT paid_total, student_count, payment_count
                    FROM report_line_items
                    WHERE cart_product_id = 4
                """)
            )
        ).fetchone()

    assert row is not None
    assert float(row.paid_total) == 2000.0
    assert row.student_count == 2
    assert row.payment_count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_payment_allocations_sum_back_to_payment_amount(ui_dev_reporting_db, reporting_engine):
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
            text("TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY")
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
            await conn.execute(text("SELECT COUNT(*) FROM report_line_items WHERE cart_product_id = 4"))
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
            text("TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY")
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
            await session.execute(text("UPDATE `lead` SET name = 'Colegio Renombrado' WHERE id = 1"))

    await run_dimensional_refresh()

    async with reporting_engine.connect() as conn:
        payment_name = (
            await conn.execute(text("SELECT school_name FROM report_payments WHERE lead_id = 1 LIMIT 1"))
        ).scalar()
        line_item_name = (
            await conn.execute(text("SELECT school_name FROM report_line_items WHERE lead_id = 1 LIMIT 1"))
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
            text("TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY")
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
            text("TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY")
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
            text("TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY")
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
            text("TRUNCATE report_payment_allocations, report_payments, report_line_items, exchange_rates, etl_meta RESTART IDENTITY")
        )
    calls: list[tuple[datetime, ETLJobName]] = []

    async def fake_run_upsert(*, since: datetime | None = None, job_name: ETLJobName = ETLJobName.UPSERT) -> None:
        calls.append((since, job_name))

    monkeypatch.setattr("app.etl.startup_backfill.run_upsert", fake_run_upsert)

    await run_startup_backfill_if_needed(now=datetime(2026, 5, 21, 12, 0, 0))

    assert calls == [(STARTUP_BACKFILL_FLOOR, ETLJobName.STARTUP_BACKFILL)]
