import pytest

from app.schemas.reports import DetalleFilters
from app.services.detalle_asesor.detalle_asesor import get_detalle_data


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_2025_returns_only_paid_exam_cart_products(ui_dev_reporting_db):
    result = await get_detalle_data(
        DetalleFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            page_size=20,
            sort_by="seller_name",
            sort_dir="asc",
        )
    )

    # 9 source cart_products, but cp10 + cp11 share (Carlos Rodriguez, Colegio Colombia Dos,
    # 2025-05-12) → 8 groups after GROUP BY seller/school/date
    assert len(result.current.rows) == 8
    assert result.current.has_more is False
    assert result.current.next_cursor is None
    keys = {(r.seller_name, r.school_name, r.exam_date) for r in result.current.rows}
    assert ("Carlos Rodriguez", "Colegio Colombia Dos", "2025-05-12") in keys


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_dedupes_multi_student_allocations_to_single_cart_product_quantities(
    ui_dev_reporting_db,
):
    result = await get_detalle_data(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=20)
    )
    by_key = {(r.seller_name, r.school_name, r.exam_date): r for r in result.current.rows}

    # cp4: 2 students allocated to the same cart_product → quantity stays 2 (not doubled)
    row_cp4 = by_key[("Ana Garcia", "Colegio Mexico Uno", "2025-01-15")]
    assert row_cp4.exam_counts["A2 Key"] == 2
    assert row_cp4.total == 2

    # cp8: 2 students allocated to the same cart_product → quantity stays 2 (not doubled)
    row_cp8 = by_key[("Carlos Rodriguez", "Colegio Colombia Uno", "2025-04-02")]
    assert row_cp8.exam_counts["B2 First"] == 2
    assert row_cp8.total == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_excludes_non_exam_pending_and_deleted_rows(ui_dev_reporting_db):
    result = await get_detalle_data(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=20)
    )
    rows = result.current.rows
    by_key = {(r.seller_name, r.school_name, r.exam_date): r for r in rows}

    # 8 groups: books/courses/pending/deleted excluded, cp10+cp11 merged into one
    assert len(rows) == 8

    # cp6 (book, same cart as cp5 = Ana/Colegio Mexico Dos/2025-02-07) must not inflate total
    assert by_key[("Ana Garcia", "Colegio Mexico Dos", "2025-02-07")].total == 1

    # cp9 (course, same cart as cp8 = Carlos/Colegio Colombia Uno/2025-04-02) must not inflate total
    assert by_key[("Carlos Rodriguez", "Colegio Colombia Uno", "2025-04-02")].total == 2

    # cp14 (admin fee, cart11) and cp15 (pending payment, cart12) → no extra row for Miguel
    miguel_rows = [r for r in rows if r.seller_name == "Miguel Torres"]
    assert len(miguel_rows) == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_supports_search_by_seller_name(ui_dev_reporting_db):
    result = await get_detalle_data(
        DetalleFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            search="Ana",
            page_size=20,
        )
    )

    assert len(result.current.rows) == 4  # 4 groups for Ana Garcia in 2025
    assert {row.seller_name for row in result.current.rows} == {"Ana Garcia"}


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_supports_search_by_school_name(ui_dev_reporting_db):
    result = await get_detalle_data(
        DetalleFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            search="Colombia Dos",
            page_size=20,
        )
    )

    # cp10 (TEA) and cp11 (MET) share (Carlos Rodriguez, Colegio Colombia Dos, 2025-05-12)
    # → 1 merged group with both exam counts
    assert len(result.current.rows) == 1
    assert result.current.rows[0].school_name == "Colegio Colombia Dos"
    assert result.current.rows[0].exam_counts.get("TEA", 0) == 2
    assert result.current.rows[0].exam_counts.get("MET", 0) == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_cursor_pagination_stable(ui_dev_reporting_db):
    """Paginating under seller_name ASC yields no duplicates and full coverage."""
    all_keys: list[tuple] = []
    cursor = None
    while True:
        page = await get_detalle_data(
            DetalleFilters(
                date_from="2025-01-01",
                date_to="2025-12-31",
                page_size=3,
                sort_by="seller_name",
                sort_dir="asc",
                cursor=cursor,
            )
        )
        all_keys.extend((r.seller_name, r.school_name, r.exam_date) for r in page.current.rows)
        if not page.current.has_more or page.current.next_cursor is None:
            break
        assert isinstance(page.current.next_cursor, str)
        cursor = page.current.next_cursor

    assert len(all_keys) == len(set(all_keys)), "Duplicate rows across pages"
    assert len(all_keys) == 8  # 9 cart_products → 8 groups (cp10+cp11 merge)


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_empty_range_returns_no_rows(ui_dev_reporting_db):
    result = await get_detalle_data(
        DetalleFilters(date_from="2030-01-01", date_to="2030-12-31", page_size=20)
    )

    assert result.current.rows == []
    assert result.current.has_more is False
    assert result.current.next_cursor is None


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_default_sort_is_exam_date_desc(ui_dev_reporting_db):
    result = await get_detalle_data(
        DetalleFilters(date_from="2025-01-01", date_to="2025-12-31", page_size=20)
    )

    dates = [row.exam_date for row in result.current.rows]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_asesor_sort_by_seller_name_asc(ui_dev_reporting_db):
    result = await get_detalle_data(
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
    all_keys: list[tuple] = []
    cursor = None
    while True:
        page = await get_detalle_data(
            DetalleFilters(
                date_from="2025-01-01",
                date_to="2025-12-31",
                page_size=3,
                sort_by="school_name",
                sort_dir="asc",
                cursor=cursor,
            )
        )
        all_keys.extend((r.seller_name, r.school_name, r.exam_date) for r in page.current.rows)
        if not page.current.has_more or page.current.next_cursor is None:
            break
        cursor = page.current.next_cursor

    assert len(all_keys) == len(set(all_keys)), "Duplicate rows across pages"
    assert len(all_keys) == 8  # 9 cart_products → 8 groups (cp10+cp11 merge)
