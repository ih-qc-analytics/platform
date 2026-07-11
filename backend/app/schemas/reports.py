from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from app.enums import ComparisonMode

AsesorSortColumn = Literal[
    "seller_name",
    "total_revenue",
    "allocated_revenue",
    "expected_revenue",
    "expected_cost",
    "profit_margin",
]
AsesorSortDir = Literal["asc", "desc"]


class BaseGeoFilters(BaseModel):
    countries: list[str] = []
    zones: list[str] = []
    states: list[str] = []
    cities: list[str] = []


class ComparisonFilterFields(BaseModel):
    show_comparison: bool = False
    comparison_mode: ComparisonMode = ComparisonMode.PREVIOUS_YEAR
    comparison_date_from: Optional[str] = None
    comparison_date_to: Optional[str] = None


class DateRangeFilterFields(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class ReportFilters(BaseGeoFilters, DateRangeFilterFields, ComparisonFilterFields):
    pass


class ComparisonMeta(BaseModel):
    mode: ComparisonMode
    date_from: str
    date_to: str


class MetricDelta(BaseModel):
    comparison_value: Optional[float] = None
    pct_change: Optional[float] = None


class TrendPoint(BaseModel):
    month: str
    revenue: float


class GeoPoint(BaseModel):
    dimension: str
    revenue: float


class ProductMix(BaseModel):
    exams_pct: float
    books_pct: float
    courses_pct: float
    unknown_pct: float


class TotalSalesBase(BaseModel):
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
    expected_revenue: float
    expected_cost: float
    uncategorized_revenue: float
    unknown_site_revenue: float
    unknown_site_expected_revenue: float
    profit_margin: float
    trend_points: list[TrendPoint]
    geo_points: list[GeoPoint]
    product_mix: Optional[ProductMix] = None


class TotalSalesComparison(BaseModel):
    meta: ComparisonMeta
    data: TotalSalesBase
    deltas: dict[str, MetricDelta]


class TotalSalesResponse(BaseModel):
    current: TotalSalesBase
    comparison_mode: Optional[ComparisonMode] = None
    comparison: Optional[TotalSalesComparison] = None


class FilterOptionsResponse(BaseModel):
    countries: list[str]
    zones: list[str]
    states: list[str]
    cities: list[str]


class SellerOptionsResponse(BaseModel):
    sellers: list[str]


class AsesorFilters(BaseGeoFilters, DateRangeFilterFields, ComparisonFilterFields):
    sellers: list[str] = []
    limit: int = 25
    cursor: Optional[str] = None
    sort_by: AsesorSortColumn = "total_revenue"
    sort_dir: AsesorSortDir = "desc"


class AsesorRow(BaseModel):
    seller_id: int
    seller_name: str
    exam_breakdown: dict[str, int]
    ganados: int
    perdidos: int
    mantenidos: int
    total_revenue: float
    uncategorized_revenue: float
    total_books: int = 0
    total_courses: int = 0
    exam_revenue: float = 0.0
    book_revenue: float = 0.0
    course_revenue: float = 0.0
    books_courses_ganados: int = 0
    books_courses_perdidos: int = 0
    books_courses_mantenidos: int = 0
    allocated_revenue: float = 0.0
    expected_revenue: float = 0.0
    expected_cost: float = 0.0
    profit_margin: float = 0.0


class AsesorReportBase(BaseModel):
    rows: list[AsesorRow]
    next_cursor: Optional[str] = None
    has_more: bool = False


class AsesorReportComparison(BaseModel):
    meta: ComparisonMeta
    data: AsesorReportBase
    deltas: dict[str, MetricDelta] = {}


class AsesorReportResponse(BaseModel):
    current: AsesorReportBase
    comparison_mode: Optional[ComparisonMode] = None
    comparison: Optional[AsesorReportComparison] = None


class ExamBrandDetail(BaseModel):
    exams: int
    schools: int
    revenue: float


class BusinessStatusDetail(BaseModel):
    schools: int
    exams: int
    books: int = 0
    courses: int = 0
    revenue: float


class AsesorDetailBase(BaseModel):
    seller_name: str
    countries: list[str]
    zones: list[str]
    states: list[str]
    cities: list[str]
    total_schools: int
    total_exams: int
    total_revenue: float
    uncategorized_revenue: float
    exam_breakdown: dict[str, ExamBrandDetail | int]
    ganados: BusinessStatusDetail
    perdidos: BusinessStatusDetail
    mantenidos: BusinessStatusDetail
    total_books: int = 0
    total_courses: int = 0
    book_revenue: float = 0.0
    course_revenue: float = 0.0
    allocated_revenue: float = 0.0
    expected_revenue: float = 0.0
    expected_cost: float = 0.0
    profit_margin: float = 0.0


class AsesorDetailComparison(BaseModel):
    meta: ComparisonMeta
    data: AsesorDetailBase
    deltas: dict[str, MetricDelta] = {}


class AsesorDetailResponse(BaseModel):
    current: AsesorDetailBase
    comparison_mode: Optional[ComparisonMode] = None
    comparison: Optional[AsesorDetailComparison] = None


class DetalleFilters(ReportFilters):
    search: Optional[str] = None
    cursor: Optional[int] = None
    page_size: int = 8


class DetalleRow(BaseModel):
    id: int
    seller_name: str
    school_name: str
    exam_date: str
    exam_type: str
    exam_counts: dict[str, int]
    total: int


class DetalleReportBase(BaseModel):
    rows: list[DetalleRow]
    next_cursor: Optional[int]
    has_more: bool


class DetalleReportResponse(BaseModel):
    current: DetalleReportBase


class PorPaisFilters(DateRangeFilterFields, ComparisonFilterFields):
    date_from: str
    date_to: str


class PorPaisSummaryRow(BaseModel):
    country: str
    total_schools: int
    total_revenue: float
    uncategorized_revenue: float
    cambridge: int
    ielts: int
    michigan: int
    tea: int
    other: int
    total_books: int = 0
    total_courses: int = 0
    exam_revenue: float = 0.0
    book_revenue: float = 0.0
    course_revenue: float = 0.0


class PorPaisStatusRow(BaseModel):
    country: str
    schools_ganados: int
    schools_perdidos: int
    schools_mantenidos: int
    exams_ganados: int
    exams_perdidos: int
    exams_mantenidos: int
    books_courses_ganados: int = 0
    books_courses_perdidos: int = 0
    books_courses_mantenidos: int = 0


class PorPaisReportBase(BaseModel):
    summary_rows: list[PorPaisSummaryRow]
    status_rows: list[PorPaisStatusRow]


class PorPaisReportComparison(BaseModel):
    meta: ComparisonMeta
    data: PorPaisReportBase
    deltas: dict[str, MetricDelta] = {}


class PorPaisReportResponse(BaseModel):
    current: PorPaisReportBase
    comparison_mode: Optional[ComparisonMode] = None
    comparison: Optional[PorPaisReportComparison] = None


class PorPaisDetailResponse(BaseModel):
    country: str
    exam_counts: dict[str, int]
    comparison_exam_counts: dict[str, int] | None = None
    total_books: int = 0
    total_courses: int = 0
    book_revenue: float = 0.0
    course_revenue: float = 0.0
    comparison_total_books: int | None = None
    comparison_total_courses: int | None = None
    comparison_book_revenue: float | None = None
    comparison_course_revenue: float | None = None
    exam_revenue: float = 0.0
    comparison_exam_revenue: float | None = None
