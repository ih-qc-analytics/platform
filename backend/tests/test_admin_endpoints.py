import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app

_VALID_KEY = "test-admin-key"


def _with_admin_key(monkeypatch_style=False):
    """Patch settings.admin_api_key for the duration of a test."""
    return patch("app.main.settings.admin_api_key", _VALID_KEY)


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_missing_key_returns_422():
    """Request with no X-Admin-Key header → 422 (missing required header)."""
    with _with_admin_key():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/admin/etl/payment-upsert")
    assert r.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_wrong_key_returns_403():
    with _with_admin_key():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/admin/etl/payment-upsert", headers={"x-admin-key": "wrong-key"})
    assert r.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_payment_upsert_returns_summary():
    summary = {"payments": 5, "line_items": 10, "allocations": 3, "deleted": 1}
    with _with_admin_key(), patch("app.main.run_upsert", new=AsyncMock(return_value=summary)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/admin/etl/payment-upsert",
                headers={"x-admin-key": _VALID_KEY},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["payments"] == 5
    assert body["line_items"] == 10
    assert body["allocations"] == 3
    assert body["deleted"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_dimensional_refresh_returns_summary():
    summary = {"leads_refreshed": 42}
    with (
        _with_admin_key(),
        patch("app.main.run_dimensional_refresh", new=AsyncMock(return_value=summary)),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/admin/etl/dimensional-refresh",
                headers={"x-admin-key": _VALID_KEY},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["leads_refreshed"] == 42


@pytest.mark.asyncio(loop_scope="session")
async def test_fetch_rates_returns_summary():
    summary = {"date": "2026-07-02"}
    with (
        _with_admin_key(),
        patch("app.main.fetch_and_store_rates", new=AsyncMock(return_value=summary)),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/admin/etl/fetch-rates",
                headers={"x-admin-key": _VALID_KEY},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["date"] == "2026-07-02"
