from sqlalchemy import text

from app.reporting.database import ReportingSessionLocal
from app.enums import PaymentStatus
from app.schemas.pdf import DetalleAsesorPDFPayload, PDFTable, PDFTableRow
from app.schemas.reports import DetalleFilters, DetalleReportResponse, DetalleRow
from app.services.exports.excel import ExcelColumn, ExcelWorksheetSpec
from app.services.exports.pdf_helpers import build_pdf_header, format_date, format_integer
from app.services.por_asesor.product_grouping import EXAM_NAME_ORDER
from app.services.shared import coerce_iso_date_param, report_date_expr

DETALLE_EXAM_NAME_ORDER = [*EXAM_NAME_ORDER, "Other"]

DETALLE_EXPORT_COLUMNS = [
    ExcelColumn("seller_name", "Seller"),
    ExcelColumn("school_name", "School"),
    ExcelColumn("exam_date",   "Exam Date"),
    *[ExcelColumn(name, name) for name in DETALLE_EXAM_NAME_ORDER],
    ExcelColumn("total", "Total"),
]


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
        conditions.append(
            "COALESCE(state_names, ARRAY[]::text[]) && CAST(:states AS text[])"
        )
        params["states"] = list(filters.states)
    if getattr(filters, "cities", None):
        conditions.append(
            "COALESCE(city_names, ARRAY[]::text[]) && CAST(:cities AS text[])"
        )
        params["cities"] = list(filters.cities)
    if getattr(filters, "date_from", None):
        conditions.append(f"{report_date_expr()} >= :date_from")
        params["date_from"] = coerce_iso_date_param(filters.date_from)
    if getattr(filters, "date_to", None):
        conditions.append(f"{report_date_expr()} <= :date_to")
        params["date_to"] = coerce_iso_date_param(filters.date_to)
    if filters.cursor is not None:
        conditions.append("cart_product_id > :cursor")
        params["cursor"] = filters.cursor
    if filters.search:
        # Use ILIKE for simplicity; the GIN index on to_tsvector accelerates full-text if needed
        conditions.append("(seller_name ILIKE :search OR school_name ILIKE :search)")
        params["search"] = f"%{filters.search}%"

    return " AND ".join(conditions), params


async def getDetalleData(filters: DetalleFilters) -> DetalleReportResponse:
    where, params = _build_where(filters)
    params["page_size"] = filters.page_size + 1

    # Each report_line_items row is one cart_product — no grouping needed.
    # exam_canonical_name is already standardised by the ETL.
    query = f"""
        SELECT
            cart_product_id       AS id,
            seller_name,
            school_name,
            payment_date::text    AS exam_date,
            exam_canonical_name   AS exam_name,
            quantity
        FROM report_line_items
        WHERE {where}
        ORDER BY cart_product_id ASC
        LIMIT :page_size
    """

    async with ReportingSessionLocal() as session:
        raw_rows = (await session.execute(text(query), params)).fetchall()

    rows_list: list[DetalleRow] = []
    for row in raw_rows[:filters.page_size]:
        exam_counts = {name: 0 for name in DETALLE_EXAM_NAME_ORDER}
        name = row.exam_name if row.exam_name in exam_counts else "Other"
        exam_counts[name] = int(row.quantity or 0)
        rows_list.append(DetalleRow(
            id=row.id,
            seller_name=row.seller_name,
            school_name=row.school_name or "",
            exam_date=str(row.exam_date) if row.exam_date else "",
            exam_counts=exam_counts,
            total=sum(exam_counts.values()),
        ))

    has_more   = len(raw_rows) > filters.page_size
    next_cursor = rows_list[-1].id if has_more and rows_list else None

    return DetalleReportResponse(rows=rows_list, next_cursor=next_cursor, has_more=has_more)


def build_detalle_export_filters_for_all(filters: DetalleFilters) -> DetalleFilters:
    return filters.model_copy(update={
        "countries": [], "zones": [], "states": [], "cities": [],
        "search": None, "cursor": None, "page_size": 500,
    })


async def getAllDetalleRows(filters: DetalleFilters) -> DetalleReportResponse:
    all_rows: list[DetalleRow] = []
    cursor = filters.cursor

    while True:
        page = await getDetalleData(filters.model_copy(update={"cursor": cursor}))
        all_rows.extend(page.rows)
        if not page.has_more or page.next_cursor is None:
            break
        cursor = page.next_cursor

    return DetalleReportResponse(rows=all_rows, next_cursor=None, has_more=False)


def build_detalle_export_worksheets(report: DetalleReportResponse) -> list[ExcelWorksheetSpec]:
    rows = []
    for row in report.rows:
        export_row = {
            "seller_name": row.seller_name,
            "school_name": row.school_name,
            "exam_date":   row.exam_date,
            "total":       row.total,
        }
        for name in DETALLE_EXAM_NAME_ORDER:
            export_row[name] = int(row.exam_counts.get(name, 0) or 0)
        rows.append(export_row)

    return [ExcelWorksheetSpec(name="Detalle Asesor", columns=DETALLE_EXPORT_COLUMNS, rows=rows)]


async def build_detalle_asesor_pdf_payload(filters: DetalleFilters) -> DetalleAsesorPDFPayload:
    report = await getAllDetalleRows(build_detalle_export_filters_for_all(filters))

    identity_rows = [
        PDFTableRow(cells=[
            row.seller_name,
            row.school_name,
            format_date(row.exam_date) if row.exam_date else "-",
            format_integer(row.total),
        ])
        for row in report.rows
    ]
    exam_rows = [
        PDFTableRow(cells=[
            row.seller_name,
            row.school_name,
            *[format_integer(row.exam_counts.get(name, 0) or 0) for name in DETALLE_EXAM_NAME_ORDER],
            format_integer(row.total),
        ])
        for row in report.rows
    ]

    return DetalleAsesorPDFPayload(
        header=build_pdf_header("Detalle por Asesor", "Desglose por asesor, escuela y fecha de examen", filters),
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
