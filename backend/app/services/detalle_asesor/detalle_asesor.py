from sqlalchemy import bindparam, text

from app.database import SessionLocal
from app.schemas.pdf import DetalleAsesorPDFPayload, PDFTable, PDFTableRow
from app.schemas.reports import DetalleFilters, DetalleReportResponse, DetalleRow
from app.services.exports.excel import ExcelColumn, ExcelWorksheetSpec
from app.services.exports.pdf_helpers import build_pdf_header, format_date, format_integer
from app.services.por_asesor.product_grouping import EXAM_NAME_ORDER, canonical_exam_name
from app.services.utils.fact_subqueries import (
    build_deduped_paid_cart_product_fact_subquery,
    build_paid_student_allocation_fact_subquery,
)
from app.services.utils.report_filters import (
    build_student_payment_fact_where_clause,
)


DETALLE_EXAM_NAME_ORDER = [*EXAM_NAME_ORDER, "Other"]
DETALLE_EXPORT_COLUMNS = [
    ExcelColumn("seller_name", "Seller"),
    ExcelColumn("school_name", "School"),
    ExcelColumn("exam_date", "Exam Date"),
    *[ExcelColumn(exam_name, exam_name) for exam_name in DETALLE_EXAM_NAME_ORDER],
    ExcelColumn("total", "Total"),
]


def create_empty_exam_counts() -> dict[str, int]:
    return {exam_name: 0 for exam_name in DETALLE_EXAM_NAME_ORDER}


def build_detalle_where(filters: DetalleFilters) -> tuple[str, dict, list[str]]:
    where_clause, params, expanding_keys = build_student_payment_fact_where_clause(
        filters,
        include_exam_product=True,
    )
    conditions = [where_clause]

    if filters.cursor is not None:
        conditions.append("cp.id > :cursor")
        params["cursor"] = filters.cursor

    if filters.search:
        conditions.append(
            "(CONCAT(s.name, ' ', s.lastName) LIKE :search OR l.name LIKE :search)"
        )
        params["search"] = f"%{filters.search}%"

    return " AND ".join(conditions), params, expanding_keys


async def getDetalleData(filters: DetalleFilters) -> DetalleReportResponse:
    where_clause, params, expanding_keys = build_detalle_where(filters)
    params["page_size"] = filters.page_size + 1
    paid_allocation_fact = build_paid_student_allocation_fact_subquery(where_clause)
    paid_cart_product_fact = build_deduped_paid_cart_product_fact_subquery(paid_allocation_fact)

    query = f"""
        SELECT DISTINCT
            pcp.cart_product_id AS id,
            pcp.seller_name,
            pcp.school_name,
            pcp.exam_date,
            pcp.exam_name,
            pcp.cart_product_quantity AS quantity
        FROM ({paid_cart_product_fact}) pcp
        ORDER BY pcp.cart_product_id ASC
        LIMIT :page_size
    """

    stmt = text(query)
    if expanding_keys:
        stmt = stmt.bindparams(*(bindparam(key, expanding=True) for key in expanding_keys))

    async with SessionLocal() as session:
        result = await session.execute(stmt, params)
        raw_rows = result.fetchall()

    # One DetalleRow per paid cart-product line.
    grouped: dict[int, dict] = {}
    order: list[int] = []
    for row in raw_rows:
        cp_id = row.id
        if cp_id not in grouped:
            grouped[cp_id] = {
                "id": cp_id,
                "seller_name": row.seller_name,
                "school_name": row.school_name,
                "exam_date": str(row.exam_date) if row.exam_date else "",
                "exam_counts": create_empty_exam_counts(),
            }
            order.append(cp_id)
        if row.exam_name:
            exam_counts = grouped[cp_id]["exam_counts"]
            exam_name = canonical_exam_name(row.exam_name)
            exam_counts[exam_name] = exam_counts.get(exam_name, 0) + row.quantity

    pivoted = [grouped[k] for k in order]
    has_more = len(pivoted) > filters.page_size
    if has_more:
        pivoted = pivoted[: filters.page_size]

    rows = [
        DetalleRow(
            id=r["id"],
            seller_name=r["seller_name"],
            school_name=r["school_name"],
            exam_date=r["exam_date"],
            exam_counts=r["exam_counts"],
            total=sum(r["exam_counts"].values()),
        )
        for r in pivoted
    ]

    next_cursor = rows[-1].id if has_more and rows else None

    return DetalleReportResponse(rows=rows, next_cursor=next_cursor, has_more=has_more)


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
        }
    )


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
            "exam_date": row.exam_date,
            "total": row.total,
        }
        for exam_name in DETALLE_EXAM_NAME_ORDER:
            export_row[exam_name] = int(row.exam_counts.get(exam_name, 0) or 0)
        rows.append(export_row)

    return [
        ExcelWorksheetSpec(
            name="Detalle Asesor",
            columns=DETALLE_EXPORT_COLUMNS,
            rows=rows,
        )
    ]


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
        for row in report.rows
    ]
    exam_rows = [
        PDFTableRow(
            cells=[
                row.seller_name,
                row.school_name,
                *[format_integer(row.exam_counts.get(exam_name, 0) or 0) for exam_name in DETALLE_EXAM_NAME_ORDER],
                format_integer(row.total),
            ]
        )
        for row in report.rows
    ]

    return DetalleAsesorPDFPayload(
        header=build_pdf_header(
            "Detalle por Asesor",
            "Desglose por asesor, escuela y fecha de examen",
            filters,
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
