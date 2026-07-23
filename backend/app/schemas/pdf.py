from typing import Optional

from pydantic import BaseModel


class PDFHeader(BaseModel):
    title: str
    subtitle: str
    generated_at: str
    filters_summary: dict[str, str]


class PDFKpiItem(BaseModel):
    label: str
    value: str
    growth: Optional[str] = None
    growth_positive: Optional[bool] = None
    comparison_value: Optional[str] = None


class PDFTrendPoint(BaseModel):
    label: str
    value: float
    scaled: float
    comparison_value: Optional[float] = None
    comparison_scaled: Optional[float] = None


class PDFGeoPoint(BaseModel):
    label: str
    value: float
    scaled: float
    comparison_value: Optional[float] = None
    comparison_scaled: Optional[float] = None


class PDFTableCellDelta(BaseModel):
    comparison_value: Optional[str] = None
    pct_change: Optional[str] = None
    positive: Optional[bool] = None


class PDFTableRow(BaseModel):
    cells: list[str]
    deltas: list[Optional[PDFTableCellDelta]] = []


class PDFTable(BaseModel):
    headers: list[str]
    rows: list[PDFTableRow]
    column_widths: list[int]


class VentasTotalesPDFPayload(BaseModel):
    header: PDFHeader
    kpis: list[PDFKpiItem]
    trend_points: list[PDFTrendPoint]
    geo_points: list[PDFGeoPoint]


class PorAsesorPDFPayload(BaseModel):
    header: PDFHeader
    kpis: list[PDFKpiItem]
    table: PDFTable


class AsesorDetailPDFPayload(BaseModel):
    header: PDFHeader
    kpis: list[PDFKpiItem]
    geo_table: PDFTable
    categories_table: PDFTable
    status_table: PDFTable


class DetalleAsesorPDFPayload(BaseModel):
    header: PDFHeader
    table_identity: PDFTable
    table_exams: PDFTable
    orientation: str = "landscape"


class PorPaisPDFPayload(BaseModel):
    header: PDFHeader
    kpis: list[PDFKpiItem]
    summary_table: PDFTable
    status_table: Optional[PDFTable] = None


class PorPaisDetailPDFPayload(BaseModel):
    header: PDFHeader
    kpis: list[PDFKpiItem]
    detail_table: PDFTable
