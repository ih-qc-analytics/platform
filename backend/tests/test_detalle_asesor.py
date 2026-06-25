import pytest

from app.schemas.reports import DetalleFilters
from app.services.detalle_asesor.detalle_asesor import getDetalleData


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_2025_returns_only_paid_exam_cart_products(ui_dev_reporting_db):
    result = await getDetalleData(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=20)
    )

    assert [row.id for row in result.rows] == [4, 5, 7, 8, 10, 11, 12, 13]
    assert result.has_more is False
    assert result.next_cursor is None


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_dedupes_multi_student_allocations_to_single_cart_product_quantities(
    ui_dev_reporting_db,
):
    result = await getDetalleData(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=20)
    )
    rows = {row.id: row for row in result.rows}

    assert rows[4].exam_counts["A2 Key"] == 2
    assert rows[4].total == 2
    assert rows[8].exam_counts["B2 First"] == 2
    assert rows[8].total == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_excludes_non_exam_pending_and_deleted_rows(ui_dev_reporting_db):
    result = await getDetalleData(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=20)
    )

    ids = [row.id for row in result.rows]
    assert 6 not in ids  # book
    assert 9 not in ids  # course
    assert 14 not in ids  # other fee with no allocation
    assert 15 not in ids  # pending payment
    assert 16 not in ids  # deleted cart
    assert 17 not in ids  # deleted cart_product


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_supports_search_by_seller_name(ui_dev_reporting_db):
    result = await getDetalleData(
        DetalleFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            search="Ana",
            page_size=20,
        )
    )

    assert [row.id for row in result.rows] == [4, 5, 7]
    assert {row.seller_name for row in result.rows} == {"Ana Garcia"}


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_supports_search_by_school_name(ui_dev_reporting_db):
    result = await getDetalleData(
        DetalleFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            search="Colombia Dos",
            page_size=20,
        )
    )

    assert [row.id for row in result.rows] == [10, 11]
    assert {row.school_name for row in result.rows} == {"Colegio Colombia Dos"}


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_cursor_pagination_uses_cart_product_id(ui_dev_reporting_db):
    first_page = await getDetalleData(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=3)
    )
    second_page = await getDetalleData(
        DetalleFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            page_size=3,
            cursor=first_page.next_cursor,
        )
    )

    assert [row.id for row in first_page.rows] == [4, 5, 7]
    assert first_page.has_more is True
    assert first_page.next_cursor == 7

    assert [row.id for row in second_page.rows] == [8, 10, 11]
    assert second_page.has_more is True
    assert second_page.next_cursor == 11


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_empty_range_returns_no_rows(ui_dev_reporting_db):
    result = await getDetalleData(
        DetalleFilters(date_from="2030-01-01", date_to="2030-12-31", page_size=20)
    )

    assert result.rows == []
    assert result.has_more is False
    assert result.next_cursor is None
