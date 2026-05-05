import pytest

from app.schemas.reports import DetalleFilters
from app.services.detalle_asesor.detalle_asesor import getDetalleData


# ─────────────────────────────────────────────
# No filters
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_no_filters_returns_all_rows(detalle_asesor_db):
    result = await getDetalleData(DetalleFilters())
    # cp ids 1–6 (2025) + cp 7 (2024, no date filter); cp 8 (deleted cart) and cp 9 (book) excluded
    assert result.has_more is False
    assert [row.id for row in result.rows] == [1, 2, 3, 4, 5, 6, 7]


# ─────────────────────────────────────────────
# Date range filter
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_date_range_reduces_results(detalle_asesor_db):
    result = await getDetalleData(DetalleFilters(
        date_from="2025-01-01",
        date_to="2025-04-30",
    ))
    assert [row.id for row in result.rows] == [1, 2, 3]
    assert result.has_more is False


# ─────────────────────────────────────────────
# Country filter
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_country_filter(detalle_asesor_db):
    result = await getDetalleData(DetalleFilters(countries=["colombia"]))
    assert [row.id for row in result.rows] == [4, 5, 6]
    for row in result.rows:
        assert row.seller_name == "Carlos Lopez"


# ─────────────────────────────────────────────
# Search filters
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_search_by_seller_name(detalle_asesor_db):
    result = await getDetalleData(DetalleFilters(search="Ana"))
    assert [row.id for row in result.rows] == [1, 2, 3, 7]
    for row in result.rows:
        assert row.seller_name == "Ana Garcia"


@pytest.mark.asyncio(loop_scope="session")
async def test_search_by_school_name(detalle_asesor_db):
    result = await getDetalleData(DetalleFilters(search="Gamma"))
    assert len(result.rows) == 1
    assert result.rows[0].id == 3
    assert result.rows[0].school_name == "Colegio Gamma"


# ─────────────────────────────────────────────
# Cursor pagination
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_cursor_pagination_returns_next_page(detalle_asesor_db):
    first = await getDetalleData(DetalleFilters(page_size=2))
    assert [row.id for row in first.rows] == [1, 2]
    assert first.has_more is True
    assert first.next_cursor == 2

    second = await getDetalleData(DetalleFilters(page_size=2, cursor=first.next_cursor))
    assert [row.id for row in second.rows] == [3, 4]
    assert second.has_more is True


@pytest.mark.asyncio(loop_scope="session")
async def test_has_more_false_on_last_page(detalle_asesor_db):
    result = await getDetalleData(DetalleFilters(page_size=10))
    assert result.has_more is False
    assert result.next_cursor is None
    assert len(result.rows) == 7


# ─────────────────────────────────────────────
# exam_counts and total
# ─────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_exam_counts_are_correct(detalle_asesor_db):
    result = await getDetalleData(DetalleFilters())
    rows_by_id = {row.id: row for row in result.rows}

    assert rows_by_id[1].exam_counts["A2 Key"] == 5
    assert rows_by_id[4].exam_counts["B1 Preliminary"] == 6
    assert rows_by_id[5].exam_counts["B2 First"] == 2
    assert rows_by_id[1].exam_counts["Other"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_total_equals_sum_of_exam_counts(detalle_asesor_db):
    result = await getDetalleData(DetalleFilters())
    for row in result.rows:
        assert row.total == sum(row.exam_counts.values())
