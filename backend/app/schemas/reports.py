from pydantic import BaseModel
from typing import Optional

## se usa type string porque no hay un catalogo definido de los valores de pais, zona, estado, ciudad
class ReportFilters(BaseModel):
    date_from: Optional[str] = None    # "2025-01-01"
    date_to: Optional[str] = None      # "2025-12-31"
    countries: list[str] = []     # "MX"
    zones: list[str] = []         # "IH-CDMX"
    states: list[str] = []        # "CDMX"
    cities: list[str] = []


class TrendPoint(BaseModel): 
    month: str 
    revenue: float 


class ProductMix(BaseModel):
    exams_pct: float
    books_pct: float
    courses_pct: float


class GeoPoint(BaseModel):
    dimension: str          # nombre de pais o zona 
    revenue: float


class TotalSalesResponse(BaseModel): 
    total_clients: int
    total_exams: int
    exam_revenue: float
    total_books: int
    book_revenue: float
    total_courses: int
    course_revenue: float
    total_revenue: float
    profit_margin: float        # porcentaje
    prior_year_revenue: float
    growth_pct: Optional[float] = None        # porcentaje
    trend_points: list[TrendPoint]
    geo_points: list[GeoPoint]
    product_mix: Optional[ProductMix] = None


class FilterOptionsResponse(BaseModel):
    countries: list[str]
    zones: list[str]
    states: list[str]
    cities: list[str]


class SellerOptionsResponse(BaseModel):
    sellers: list[str]


class AsesorFilters(BaseModel):
    year: int
    countries: list[str] = []
    zones: list[str] = []
    states: list[str] = []
    cities: list[str] = []
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
    exam_breakdown: dict[str, ExamBrandDetail]
    ganados: BusinessStatusDetail
    perdidos: BusinessStatusDetail
    mantenidos: BusinessStatusDetail
