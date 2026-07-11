from io import BytesIO

import pytest
from openpyxl import load_workbook

from app.schemas.reports import AsesorFilters, DetalleFilters, PorPaisFilters, ReportFilters
from app.enums import ComparisonMode
from app.services.detalle_asesor.detalle_asesor import (
    DETALLE_EXAM_NAME_ORDER,
    build_detalle_export_filters_for_all,
    build_detalle_export_worksheets,
    getAllDetalleRows,
    getDetalleData,
)
from app.services.exports.excel import (
    ExcelColumn,
    ExcelWorksheetSpec,
    generate_excel_response,
)
from app.services.por_asesor.por_asesor import (
    ASESOR_SUMMARY_COLUMNS,
    build_asesor_export_filters_for_all,
    build_asesor_export_worksheets,
    getAllAsesorReportRows,
    getAsesorDetailsForRows,
    getAsesorReport,
)
from app.services.por_pais.por_pais import (
    POR_PAIS_DETAIL_COLUMNS,
    POR_PAIS_STATUS_COLUMNS,
    POR_PAIS_SUMMARY_COLUMNS,
    build_por_pais_export_filters_for_all,
    build_por_pais_export_worksheets,
    getPorPaisDetailsForReport,
    getPorPaisReport,
)
from app.services.total_sales.total_sales import (
    TOTAL_SALES_CHART_COLUMNS,
    TOTAL_SALES_SUMMARY_COLUMNS,
    build_total_sales_export_filters_for_all,
    build_total_sales_export_worksheets,
    getTotalSalesData,
)


async def response_bytes(response) -> bytes:
    body = bytearray()
    async for chunk in response.body_iterator:
        body.extend(chunk)
    return bytes(body)


async def workbook_from_response(response):
    return load_workbook(BytesIO(await response_bytes(response)))


def row_values(worksheet, row_number: int, width: int) -> list:
    return [worksheet.cell(row=row_number, column=index).value for index in range(1, width + 1)]


def header_index(worksheet, header: str) -> int:
    headers = row_values(worksheet, 1, worksheet.max_column)
    return headers.index(header) + 1


@pytest.mark.asyncio(loop_scope="session")
async def test_excel_response_round_trips_headers_unicode_and_content_type():
    response = generate_excel_response(
        "demo",
        [
            ExcelWorksheetSpec(
                name="Resumen",
                columns=[ExcelColumn("name", "Name"), ExcelColumn("notes", "Notes")],
                rows=[{"name": "José", "notes": "x" * 80}],
            )
        ],
    )

    workbook = await workbook_from_response(response)
    sheet = workbook["Resumen"]

    assert (
        response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.headers["content-disposition"] == 'attachment; filename="demo.xlsx"'
    assert row_values(sheet, 1, 2) == ["Name", "Notes"]
    assert row_values(sheet, 2, 2) == ["José", "x" * 80]
    assert sheet.column_dimensions["B"].width == 60


@pytest.mark.asyncio(loop_scope="session")
async def test_total_sales_export_builds_summary_and_chart_sheets(ui_dev_reporting_db):
    filters = ReportFilters(
        date_from="2025-01-01",
        date_to="2025-12-31",
        countries=["mexico"],
        states=["CDMX"],
    )
    export_filters = build_total_sales_export_filters_for_all(filters)
    report = await getTotalSalesData(export_filters)
    response = generate_excel_response(
        "ventas-totales-all",
        build_total_sales_export_worksheets(report),
    )

    workbook = await workbook_from_response(response)
    summary_sheet = workbook["Ventas Totales"]
    chart_sheet = workbook["Ventas Totales Charts"]

    assert export_filters.model_dump() == {
        "countries": [],
        "zones": [],
        "states": [],
        "cities": [],
        "date_from": "2025-01-01",
        "date_to": "2025-12-31",
        "show_comparison": False,
        "comparison_mode": ComparisonMode.PREVIOUS_YEAR,
        "comparison_date_from": None,
        "comparison_date_to": None,
    }
    assert workbook.sheetnames == ["Ventas Totales", "Ventas Totales Charts"]
    assert row_values(summary_sheet, 1, len(TOTAL_SALES_SUMMARY_COLUMNS)) == [
        column.header for column in TOTAL_SALES_SUMMARY_COLUMNS
    ]
    assert summary_sheet.max_row == 2
    assert summary_sheet["A2"].value == 6
    assert summary_sheet["J2"].value == pytest.approx(14200, rel=1e-2)
    assert row_values(chart_sheet, 1, len(TOTAL_SALES_CHART_COLUMNS)) == [
        column.header for column in TOTAL_SALES_CHART_COLUMNS
    ]
    assert chart_sheet["A2"].value == "2025-01"
    assert chart_sheet["B2"].value == pytest.approx(2000, rel=1e-1)
    assert chart_sheet["C2"].value == "colombia"
    assert chart_sheet["D2"].value is not None  # revenue varies by exchange rate conversion


@pytest.mark.asyncio(loop_scope="session")
async def test_por_asesor_export_all_ignores_optional_filters_and_adds_detail_sheet(
    ui_dev_reporting_db,
):
    filters = AsesorFilters(
        date_from="2025-01-01",
        date_to="2025-12-31",
        sellers=["Carlos Rodriguez"],
        countries=["colombia"],
        zones=["IH Colombia"],
        limit=2,
        cursor="7100.0:2",
    )
    export_filters = build_asesor_export_filters_for_all(filters)
    report = await getAllAsesorReportRows(export_filters)
    details = await getAsesorDetailsForRows(report.current.rows, export_filters)
    response = generate_excel_response(
        "por-asesor-all",
        build_asesor_export_worksheets(report, details),
    )

    workbook = await workbook_from_response(response)
    summary_sheet = workbook["Por Asesor"]
    detail_sheet = workbook["Por Asesor Detail"]

    assert export_filters.model_dump() == {
        "countries": [],
        "zones": [],
        "states": [],
        "cities": [],
        "sellers": [],
        "limit": 100,
        "cursor": None,
        "show_comparison": False,
        "comparison_mode": ComparisonMode.PREVIOUS_YEAR,
        "comparison_date_from": None,
        "comparison_date_to": None,
        "date_from": "2025-01-01",
        "date_to": "2025-12-31",
        "sort_by": "total_revenue",
        "sort_dir": "desc",
    }
    assert set(row.seller_name for row in report.current.rows) == {
        "Carlos Rodriguez",
        "Ana Garcia",
        "Lucia Rios",
        "Miguel Torres",
    }
    assert len(report.current.rows) == 4
    # Summary columns are dynamic; without comparison, Ganados/Perdidos/Mantenidos are excluded
    expected_summary_headers = [
        c.header
        for c in ASESOR_SUMMARY_COLUMNS
        if c.header not in ("Ganados", "Perdidos", "Mantenidos")
    ]
    assert row_values(summary_sheet, 1, len(expected_summary_headers)) == expected_summary_headers
    assert summary_sheet.max_row == 5
    assert detail_sheet.max_row == 5
    # Find Carlos Rodriguez row (order may vary by revenue ranking)
    carlos_row = next(
        r
        for r in range(2, detail_sheet.max_row + 1)
        if detail_sheet.cell(row=r, column=1).value == "Carlos Rodriguez"
    )
    assert detail_sheet.cell(row=carlos_row, column=2).value == "colombia"
    assert detail_sheet.cell(row=carlos_row, column=6).value == 2
    assert (
        detail_sheet.cell(
            row=carlos_row,
            column=header_index(detail_sheet, "Cambridge English (Main Suite) Exams"),
        ).value
        == 2
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_detalle_export_preserves_canonical_exam_columns_and_headers_only_for_empty_ranges(
    ui_dev_reporting_db,
):
    export_filters = build_detalle_export_filters_for_all(
        DetalleFilters(
            date_from="2025-01-01",
            date_to="2025-12-31",
            search="Ana",
            countries=["mexico"],
            cursor=7,
            page_size=3,
        )
    )
    report = await getAllDetalleRows(export_filters)
    empty_report = await getDetalleData(
        DetalleFilters(date_from="2030-01-01", date_to="2030-12-31", page_size=20)
    )

    workbook = await workbook_from_response(
        generate_excel_response("detalle-asesor-all", build_detalle_export_worksheets(report))
    )
    empty_workbook = await workbook_from_response(
        generate_excel_response(
            "detalle-asesor-empty", build_detalle_export_worksheets(empty_report)
        )
    )

    sheet = workbook["Detalle Asesor"]
    empty_sheet = empty_workbook["Detalle Asesor"]

    assert export_filters.model_dump() == {
        "countries": [],
        "zones": [],
        "states": [],
        "cities": [],
        "date_from": "2025-01-01",
        "date_to": "2025-12-31",
        "search": None,
        "cursor": None,
        "page_size": 500,
        "show_comparison": False,
        "comparison_mode": ComparisonMode.PREVIOUS_YEAR,
        "comparison_date_from": None,
        "comparison_date_to": None,
    }
    assert row_values(sheet, 1, 4 + len(DETALLE_EXAM_NAME_ORDER)) == [
        "Seller",
        "School",
        "Exam Date",
        *DETALLE_EXAM_NAME_ORDER,
        "Total",
    ]
    assert sheet.max_row == 9
    assert sheet["A2"].value == "Ana Garcia"
    assert sheet.cell(row=2, column=header_index(sheet, "Pre-A1 Starters")).value == 0
    assert sheet.cell(row=2, column=header_index(sheet, "A2 Key")).value == 2
    assert sheet.cell(row=2, column=header_index(sheet, "Total")).value == 2
    assert empty_sheet.max_row == 1
    assert row_values(empty_sheet, 1, 4 + len(DETALLE_EXAM_NAME_ORDER)) == [
        "Seller",
        "School",
        "Exam Date",
        *DETALLE_EXAM_NAME_ORDER,
        "Total",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_por_pais_export_builds_three_sheets_with_country_detail_rows(ui_dev_reporting_db):
    filters = build_por_pais_export_filters_for_all(
        PorPaisFilters(date_from="2025-01-01", date_to="2025-12-31")
    )
    report = await getPorPaisReport(filters)
    details = await getPorPaisDetailsForReport(report, filters)
    response = generate_excel_response(
        "por-pais-all",
        build_por_pais_export_worksheets(report, details),
    )

    workbook = await workbook_from_response(response)
    summary_sheet = workbook["Por Pais Summary"]
    detail_sheet = workbook["Por Pais Detail"]

    assert filters.model_dump() == {
        "date_from": "2025-01-01",
        "date_to": "2025-12-31",
        "show_comparison": False,
        "comparison_mode": ComparisonMode.PREVIOUS_YEAR,
        "comparison_date_from": None,
        "comparison_date_to": None,
    }
    # Status sheet is only included when comparison mode is active
    assert workbook.sheetnames == ["Por Pais Summary", "Por Pais Detail"]
    assert row_values(summary_sheet, 1, len(POR_PAIS_SUMMARY_COLUMNS)) == [
        column.header for column in POR_PAIS_SUMMARY_COLUMNS
    ]
    assert row_values(detail_sheet, 1, len(POR_PAIS_DETAIL_COLUMNS)) == [
        column.header for column in POR_PAIS_DETAIL_COLUMNS
    ]
    assert summary_sheet.max_row == 4
    assert detail_sheet.max_row == 4
    assert detail_sheet["A2"].value == "colombia"
    assert detail_sheet.cell(row=2, column=header_index(detail_sheet, "B2 First")).value == 2
    assert detail_sheet.cell(row=2, column=header_index(detail_sheet, "MET")).value == 1
    assert detail_sheet.cell(row=2, column=header_index(detail_sheet, "TEA")).value == 2
