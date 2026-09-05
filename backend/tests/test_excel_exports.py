"""
Excel export tests.

These assert the workbook that actually reaches the user, not just the spec:
ExcelColumn.key is resolved with row.get(column.key), so a typo'd key produces a
silently blank column rather than an error. Only a round-trip through
build_excel_workbook catches that.
"""

from app.schemas.reports import DetalleReportBase, DetalleReportResponse, DetalleRow
from app.services.detalle_asesor.detalle_asesor import (
    DETALLE_EXAM_NAME_ORDER,
    DETALLE_EXPORT_COLUMNS,
    build_detalle_export_worksheets,
)
from app.services.exports.excel import build_excel_workbook


def _report(**overrides) -> DetalleReportResponse:
    row = DetalleRow(
        id=0,
        seller_name="Ana Garcia",
        school_name="Colegio Test",
        exam_date="2025-01-15",
        exam_type="",
        exam_counts={"A2 Key": 3},
        total=3,
        **overrides,
    )
    return DetalleReportResponse(
        current=DetalleReportBase(rows=[row], next_cursor=None, has_more=False)
    )


def _sheet(**overrides):
    specs = build_detalle_export_worksheets(_report(**overrides))
    return build_excel_workbook(specs)["Detalle Asesor"]


def test_export_column_headers_and_count():
    headers = [column.header for column in DETALLE_EXPORT_COLUMNS]
    assert headers[:5] == ["Asesor", "Colegio", "País", "Estado", "Fecha de Examen"]
    assert headers[-1] == "Total"
    # Asesor, Colegio, País, Estado, Fecha + one per exam + Total
    assert len(DETALLE_EXPORT_COLUMNS) == 5 + len(DETALLE_EXAM_NAME_ORDER) + 1


def test_geo_values_land_in_columns_c_and_d():
    worksheet = _sheet(site="mexico", state_name="CDMX")
    assert (worksheet["C1"].value, worksheet["D1"].value) == ("País", "Estado")
    assert (worksheet["C2"].value, worksheet["D2"].value) == ("mexico", "CDMX")
    # The exam block starts immediately after the two new columns.
    assert worksheet["E1"].value == "Fecha de Examen"
    assert worksheet["F1"].value == DETALLE_EXAM_NAME_ORDER[0]


def test_geo_defaults_render_blank():
    worksheet = _sheet()
    assert worksheet["C2"].value in ("", None)
    assert worksheet["D2"].value in ("", None)
