export type ReportFilters = {
    date_from?: string
    date_to?: string
    countries?: string[]
    zones?: string[]
    states?: string[]
    cities?: string[]
}

export type TrendPoint = {
    month: string
    revenue: number
}

export type ProductMix = {
    exams_pct: number
    books_pct: number
    courses_pct: number
}

export type GeoPoint = {
    dimension: string
    revenue: number
}

export type TotalSalesResponse = {
    total_clients: number
    total_exams: number
    exam_revenue: number
    total_books: number
    book_revenue: number
    total_courses: number
    course_revenue: number
    total_revenue: number
    profit_margin: number
    prior_year_revenue: number
    growth_pct: number
    trend_points: TrendPoint[]
    geo_points: GeoPoint[]
    product_mix: ProductMix | null
}

export type FilterOptionsResponse = {
    countries: string[]
    zones: string[]
    states: string[]
    cities: string[]
}

export type SellerOptionsResponse = {
    sellers: string[]
}

export type AsesorFilters = {
    year: number
    countries?: string[]
    zones?: string[]
    states?: string[]
    cities?: string[]
    sellers?: string[]
    limit?: number
    cursor?: string | null
}

export type AsesorRow = {
    seller_id: number
    seller_name: string
    exam_breakdown: Record<string, number>
    ganados: number
    perdidos: number
    mantenidos: number
    total_revenue: number
}

export type AsesorReportResponse = {
    rows: AsesorRow[]
    year: number
    next_cursor: string | null
    has_more: boolean
}

export type ExamBrandDetail = {
    exams: number
    schools: number
    revenue: number
}

export type BusinessStatusDetail = {
    schools: number
    exams: number
    revenue: number
}

export type AsesorDetail = {
    seller_name: string
    countries: string[]
    zones: string[]
    states: string[]
    cities: string[]
    total_schools: number
    total_exams: number
    total_revenue: number
    exam_breakdown: Record<string, ExamBrandDetail>
    ganados: BusinessStatusDetail
    perdidos: BusinessStatusDetail
    mantenidos: BusinessStatusDetail
}

export type DetalleAsesorFilters = ReportFilters & {
    search?: string
    cursor?: number | null
    page_size?: number
}

export type DetalleAsesorRow = {
    id: number
    seller_name: string
    school_name: string
    exam_date: string
    exam_counts: Record<string, number>
    total: number
}

export type DetalleAsesorReportResponse = {
    rows: DetalleAsesorRow[]
    next_cursor: number | null
    has_more: boolean
}
