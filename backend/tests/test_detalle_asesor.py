import pytest

from app.schemas.reports import DetalleFilters
from app.services.detalle_asesor.detalle_asesor import getDetalleData


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_2025_returns_only_paid_exam_cart_products(ui_dev_reporting_db):
    # Explicit sort to keep a deterministic order independent of the default
    result = await getDetalleData(
        DetalleFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            page_size=20,
            sort_by="seller_name",
            sort_dir="asc",
        )
    )

    assert set(row.id for row in result.current.rows) == {4, 5, 7, 8, 10, 11, 12, 13}
    assert result.current.has_more is False
    assert result.current.next_cursor is None


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_dedupes_multi_student_allocations_to_single_cart_product_quantities(
    ui_dev_reporting_db,
):
    result = await getDetalleData(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=20)
    )
    rows = {row.id: row for row in result.current.rows}

    assert rows[4].exam_counts["A2 Key"] == 2
    assert rows[4].total == 2
    assert rows[8].exam_counts["B2 First"] == 2
    assert rows[8].total == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_excludes_non_exam_pending_and_deleted_rows(ui_dev_reporting_db):
    result = await getDetalleData(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=20)
    )

    ids = [row.id for row in result.current.rows]
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

    assert set(row.id for row in result.current.rows) == {4, 5, 7}
    assert {row.seller_name for row in result.current.rows} == {"Ana Garcia"}


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

    assert set(row.id for row in result.current.rows) == {10, 11}
    assert {row.school_name for row in result.current.rows} == {"Colegio Colombia Dos"}


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_cursor_pagination_stable(ui_dev_reporting_db):
    """Paginating under seller_name ASC yields no duplicates and full coverage."""
    all_ids: list[int] = []
    cursor = None
    while True:
        page = await getDetalleData(
            DetalleFilters(
                date_from="2025-01-01",
                date_to="2025-12-31",
                page_size=3,
                sort_by="seller_name",
                sort_dir="asc",
                cursor=cursor,
            )
        )
        all_ids.extend(row.id for row in page.current.rows)
        if not page.current.has_more or page.current.next_cursor is None:
            break
        # cursor is now a base64 string
        assert isinstance(page.current.next_cursor, str)
        cursor = page.current.next_cursor

    assert len(all_ids) == len(set(all_ids)), "Duplicate row IDs across pages"
    assert set(all_ids) == {4, 5, 7, 8, 10, 11, 12, 13}


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_empty_range_returns_no_rows(ui_dev_reporting_db):
    result = await getDetalleData(
        DetalleFilters(date_from="2030-01-01", date_to="2030-12-31", page_size=20)
    )

    assert result.current.rows == []
    assert result.current.has_more is False
    assert result.current.next_cursor is None


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_default_sort_is_exam_date_desc(ui_dev_reporting_db):
    result = await getDetalleData(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=20)
    )

    dates = [row.exam_date for row in result.current.rows]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_sort_by_seller_name_asc(ui_dev_reporting_db):
    result = await getDetalleData(
        DetalleFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            page_size=20,
            sort_by="seller_name",
            sort_dir="asc",
        )
    )

    names = [row.seller_name for row in result.current.rows]
    assert names == sorted(names)


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_sort_pagination_stable(ui_dev_reporting_db):
    """Paginating under a non-default sort yields no duplicates and full coverage."""
    all_ids: list[int] = []
    cursor = None
    while True:
        page = await getDetalleData(
            DetalleFilters(
                date_from="2025-01-01",
                date_to="2025-12-31",
                page_size=3,
                sort_by="school_name",
                sort_dir="asc",
                cursor=cursor,
            )
        )
        all_ids.extend(row.id for row in page.current.rows)
        if not page.current.has_more or page.current.next_cursor is None:
            break
        cursor = page.current.next_cursor

    assert len(all_ids) == len(set(all_ids)), "Duplicate row IDs across pages"
    assert set(all_ids) == {4, 5, 7, 8, 10, 11, 12, 13}
