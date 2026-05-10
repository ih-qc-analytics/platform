from pydantic import BaseModel
from typing import Optional


# ─────────────────────────────────────────────
# Base filter classes
# ─────────────────────────────────────────────

class BaseGeoFilters(BaseModel):
    countries: list[str] = []
    zones: list[str] = []
    states: list[str] = []
    cities: list[str] = []


class ReportFilters(BaseGeoFilters):
    date_from: Optional[str] = None    # "2025-01-01"
    date_to: Optional[str] = None      # "2025-12-31"


# ─────────────────────────────────────────────
# Ventas Totales
# ─────────────────────────────────────────────

class TrendPoint(BaseModel):
    month: str
    revenue: float


class ProductMix(BaseModel):
    exams_pct: float
    books_pct: float
    courses_pct: float


class GeoPoint(BaseModel):
    dimension: str
    revenue: float


class TotalSalesResponse(BaseModel):
    total_clients: int
    total_exams: int
    exam_revenue: float
    total_books: int
    book_revenue: float
    total_courses: int
    course_revenue: float
    total_otros: int
    otros_revenue: float
    total_revenue: float
    profit_margin: float
    prior_year_revenue: float
    growth_pct: Optional[float] = None
    trend_points: list[TrendPoint]
    geo_points: list[GeoPoint]
    product_mix: Optional[ProductMix] = None


# ─────────────────────────────────────────────
# Filter options
# ─────────────────────────────────────────────

class FilterOptionsResponse(BaseModel):
    countries: list[str]
    zones: list[str]
    states: list[str]
    cities: list[str]


class SellerOptionsResponse(BaseModel):
    sellers: list[str]


# ─────────────────────────────────────────────
# Por Asesor
# ─────────────────────────────────────────────

class AsesorFilters(BaseGeoFilters):
    year: int
    sellers: list[str] = []
    limit: int = 25
    cursor: Optional[str] = None


class AsesorRow(BaseModel):
    seller_id: int
    seller_name: str
    exam_breakdown: dict[str, int]
    ganados: int
    perdidos: int
    mantenidos: int
    total_revenue: float


class AsesorReportResponse(BaseModel):
    rows: list[AsesorRow]
    year: int
    next_cursor: Optional[str] = None
    has_more: bool = False


class ExamBrandDetail(BaseModel):
    exams: int
    schools: int
    revenue: float


class BusinessStatusDetail(BaseModel):
    schools: int
    exams: int
    revenue: float


class AsesorDetail(BaseModel):
    seller_name: str
    countries: list[str]
    zones: list[str]
    states: list[str]
    cities: list[str]
    total_schools: int
    total_exams: int
    total_revenue: float
    exam_breakdown: dict[str, ExamBrandDetail | int]
    ganados: BusinessStatusDetail
    perdidos: BusinessStatusDetail
    mantenidos: BusinessStatusDetail


# ─────────────────────────────────────────────
# Detalle por Asesor
# ─────────────────────────────────────────────

class DetalleFilters(ReportFilters):
    search: Optional[str] = None   # matches seller name OR school name
    cursor: Optional[int] = None   # last row id for cursor pagination
    page_size: int = 8


class DetalleRow(BaseModel):
    id: int                        # cart_product.id, used as cursor
    seller_name: str
    school_name: str
    exam_date: str                 # YYYY-MM-DD from cart_product.testDate
    exam_counts: dict[str, int]    # { "KET": 12, "FCE": 8, ... } keyed by exam_cat.name
    total: int                     # sum of all exam_counts values


class DetalleReportResponse(BaseModel):
    rows: list[DetalleRow]
    next_cursor: Optional[int]     # None if no more pages
    has_more: bool


# ─────────────────────────────────────────────
# Por País
# ─────────────────────────────────────────────

class PorPaisFilters(BaseModel):
    date_from: str
    date_to: str


class PorPaisSummaryRow(BaseModel):
    country: str
    total_schools: int
    cambridge: int
    ielts: int
    michigan: int
    tea: int
    other: int


class PorPaisStatusRow(BaseModel):
    country: str
    schools_ganados: int
    schools_perdidos: int
    schools_mantenidos: int
    exams_ganados: int
    exams_perdidos: int
    exams_mantenidos: int


class PorPaisReportResponse(BaseModel):
    summary_rows: list[PorPaisSummaryRow]
    status_rows: list[PorPaisStatusRow]


class PorPaisDetailResponse(BaseModel):
    country: str
    exam_counts: dict[str, int]
