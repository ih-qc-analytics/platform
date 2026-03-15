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