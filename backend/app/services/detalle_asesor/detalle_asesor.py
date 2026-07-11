import base64
import json
from datetime import date as date_type

from app.schemas.pdf import DetalleAsesorPDFPayload, PDFTable, PDFTableRow
from app.schemas.reports import (
    DetalleFilters,
    DetalleReportBase,
    DetalleReportResponse,
    DetalleRow,
)
from app.services.exports.excel import ExcelColumn, ExcelWorksheetSpec
from app.services.exports.pdf_helpers import build_pdf_header, format_date, format_integer
from app.services.por_asesor.product_grouping import EXAM_NAME_ORDER
from app.services.shared import coerce_iso_date_param, report_date_expr
from app.reporting.database import ReportingSessionLocal
from app.enums import PaymentStatus
from sqlalchemy import text

DETALLE_EXAM_NAME_ORDER = [*EXAM_NAME_ORDER, "Other"]

DETALLE_EXPORT_COLUMNS = [
    ExcelColumn("seller_name", "Asesor"),
    ExcelColumn("school_name", "Colegio"),
    ExcelColumn("exam_date", "Fecha de Examen"),
    *[ExcelColumn(name, name) for name in DETALLE_EXAM_NAME_ORDER],
    ExcelColumn("total", "Total"),
]

# Whitelist — only these strings ever reach SQL interpolation
SORTABLE_COLUMNS: dict[str, str] = {
    "seller_name": "seller_name",
    "school_name": "school_name",
    "exam_date": "payment_day",
    "total": "quantity",
}


def encode_cursor(sort_by: str, sort_dir: str, sort_value, row_id: int) -> str:
    payload = {"sort_by": sort_by, "sort_dir": sort_dir, "sort_value": sort_value, "id": row_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    padding = "=" * (-len(cursor) % 4)
    payload = json.loads(base64.urlsafe_b64decode((cursor + padding).encode()).decode())
    return {
        "cursor_sort_by": str(payload["sort_by"]),
        "cursor_sort_dir": str(payload["sort_dir"]),
        "cursor_sort_value": payload["sort_value"],
        "cursor_id": int(payload["id"]),
    }


def _build_where(filters: DetalleFilters) -> tuple[str, dict]:
    conditions = [
        "is_active = TRUE",
        "payment_status = :payment_status",
        "product_type = 'exam'",
        "include_in_product_breakdown = TRUE",
    ]
    params: dict = {"payment_status": PaymentStatus.APROBADO.value}
    if getattr(filters, "countries", None):
        conditions.append("site = ANY(:countries)")
        params["countries"] = list(filters.countries)
    if getattr(filters, "zones", None):
        conditions.append("zone_name = ANY(:zones)")
        params["zones"] = list(filters.zones)
    if getattr(filters, "states", None):
        conditions.append("COALESCE(all_states, ARRAY[]::text[]) && CAST(:states AS text[])")
        params["states"] = list(filters.states)
    if getattr(filters, "cities", None):
        conditions.append("COALESCE(all_cities, ARRAY[]::text[]) && CAST(:cities AS text[])")
        params["cities"] = list(filters.cities)
    if getattr(filters, "date_from", None):
        conditions.append(f"{report_date_expr()} >= :date_from")
        params["date_from"] = coerce_iso_date_param(filters.date_from)
    if getattr(filters, "date_to", None):
        conditions.append(f"{report_date_expr()} <= :date_to")
        params["date_to"] = coerce_iso_date_param(filters.date_to)
    if filters.search:
        conditions.append("(seller_name ILIKE :search OR school_name ILIKE :search)")
        params["search"] = f"%{filters.search}%"
    return " AND ".join(conditions), params


def _row_from_record(row) -> DetalleRow:
    exam_type = row.exam_name if row.exam_name in DETALLE_EXAM_NAME_ORDER else "Other"
    exam_counts = {name: 0 for name in DETALLE_EXAM_NAME_ORDER}
    exam_counts[exam_type] = int(row.quantity or 0)
    return DetalleRow(
        id=int(row.id),
        seller_name=row.seller_name,
        school_name=row.school_name or "",
        exam_date=str(row.exam_date) if row.exam_date else "",
        exam_type=exam_type,
        exam_counts=exam_counts,
        total=sum(exam_counts.values()),
    )


async def _fetch_current_base(filters: DetalleFilters) -> DetalleReportBase:
    where, params = _build_where(filters)

    sort_by = filters.sort_by if filters.sort_by in SORTABLE_COLUMNS else "exam_date"
    sort_dir = filters.sort_dir if filters.sort_dir in ("asc", "desc") else "desc"
    sort_col = SORTABLE_COLUMNS[sort_by]
    sort_dir_sql = sort_dir.upper()
    cmp_op = "<" if sort_dir == "desc" else ">"

    cursor_clause = ""
    if filters.cursor:
        cp = decode_cursor(filters.cursor)
        params["cursor_id"] = cp["cursor_id"]
        # asyncpg requires Python date objects for date column comparisons
        raw_cv = cp["cursor_sort_value"]
        params["cursor_sort_value"] = (
            date_type.fromisoformat(raw_cv) if sort_by == "exam_date" else raw_cv
        )
        cursor_clause = f"""
            AND (
                {sort_col} {cmp_op} :cursor_sort_value
                OR ({sort_col} = :cursor_sort_value AND cart_product_id > :cursor_id)
            )
        """

    params["page_size"] = filters.page_size + 1
    query = f"""
        SELECT
            cart_product_id AS id,
            seller_name,
            school_name,
            payment_day::text AS exam_date,
            exam_canonical_name AS exam_name,
            quantity,
            {sort_col} AS sort_val
        FROM report_line_items
        WHERE {where}
        {cursor_clause}
        ORDER BY {sort_col} {sort_dir_sql}, cart_product_id ASC
        LIMIT :page_size
    """
    async with ReportingSessionLocal() as session:
        records = (await session.execute(text(query), params)).fetchall()

    page_records = records[: filters.page_size]
    rows = [_row_from_record(row) for row in page_records]
    has_more = len(records) > filters.page_size

    next_cursor = None
    if has_more and rows:
        last_record = page_records[-1]
        last_row = rows[-1]
        raw_sort_val = last_record.sort_val
        # Normalize to JSON-safe types: strings for text/date, int for quantity
        if sort_by == "total":
            sort_value = int(raw_sort_val) if raw_sort_val is not None else 0
        else:
            sort_value = str(raw_sort_val) if raw_sort_val is not None else ""
        next_cursor = encode_cursor(sort_by, sort_dir, sort_value, last_row.id)

    return DetalleReportBase(rows=rows, next_cursor=next_cursor, has_more=has_more)


async def get_detalle_data(filters: DetalleFilters) -> DetalleReportResponse:
    current = await _fetch_current_base(filters)
    return DetalleReportResponse(current=current)


def build_detalle_export_filters_for_all(filters: DetalleFilters) -> DetalleFilters:
    return filters.model_copy(
        update={
            "countries": [],
            "zones": [],
            "states": [],
            "cities": [],
            "search": None,
            "cursor": None,
            "page_size": 500,
            "show_comparison": False,
            # sort_by and sort_dir preserved intentionally
        }
    )


def build_detalle_filtered_export_filters(filters: DetalleFilters) -> DetalleFilters:
    """Strip cursor/page_size so the filtered export fetches all matching rows, not just the current page."""
    return filters.model_copy(
        update={
            "cursor": None,
            "page_size": 500,
            "show_comparison": False,
            # countries, zones, states, cities, search, sort_by, sort_dir preserved
        }
    )


async def get_all_detalle_rows(filters: DetalleFilters) -> DetalleReportResponse:
    all_rows: list[DetalleRow] = []
    cursor = filters.cursor
    while True:
        page = await getDetalleData(
            filters.model_copy(update={"cursor": cursor, "show_comparison": False})
        )
        all_rows.extend(page.current.rows)
        if not page.current.has_more or page.current.next_cursor is None:
            break
        cursor = page.current.next_cursor
    return DetalleReportResponse(
        current=DetalleReportBase(rows=all_rows, next_cursor=None, has_more=False),
        comparison_mode=None,
        comparison=None,
    )


def build_detalle_export_worksheets(report: DetalleReportResponse) -> list[ExcelWorksheetSpec]:
    rows = []
    for row in report.current.rows:
        export_row = {
            "seller_name": row.seller_name,
            "school_name": row.school_name,
            "exam_date": row.exam_date,
            "total": row.total,
        }
        for name in DETALLE_EXAM_NAME_ORDER:
            export_row[name] = int(row.exam_counts.get(name, 0) or 0)
        rows.append(export_row)
    return [ExcelWorksheetSpec(name="Detalle Asesor", columns=DETALLE_EXPORT_COLUMNS, rows=rows)]


async def build_detalle_asesor_pdf_payload(filters: DetalleFilters) -> DetalleAsesorPDFPayload:
    report = await getAllDetalleRows(build_detalle_export_filters_for_all(filters))
    identity_rows = [
        PDFTableRow(
            cells=[
                row.seller_name,
                row.school_name,
                format_date(row.exam_date) if row.exam_date else "-",
                format_integer(row.total),
            ]
        )
        for row in report.current.rows
    ]
    exam_rows = [
        PDFTableRow(
            cells=[
                row.seller_name,
                row.school_name,
                *[
                    format_integer(row.exam_counts.get(name, 0) or 0)
                    for name in DETALLE_EXAM_NAME_ORDER
                ],
                format_integer(row.total),
            ]
        )
        for row in report.current.rows
    ]
    return DetalleAsesorPDFPayload(
        header=build_pdf_header(
            "Detalle por Asesor", "Desglose por asesor, escuela y fecha de examen", filters
        ),
        table_identity=PDFTable(
            headers=["Asesor", "Escuela", "Fecha", "Total"],
            rows=identity_rows,
            column_widths=[3, 4, 2, 1],
        ),
        table_exams=PDFTable(
            headers=["Asesor", "Escuela", *DETALLE_EXAM_NAME_ORDER, "Total"],
            rows=exam_rows,
            column_widths=[3, 4, *([1] * len(DETALLE_EXAM_NAME_ORDER)), 1],
        ),
        orientation="landscape",
    )
