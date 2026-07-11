export type BaseCurrency = "MXN" | "USD"

export type ComparisonMode = "PREVIOUS_YEAR" | "PREVIOUS_PERIOD" | "CUSTOM"

export type ComparisonFields = {
    show_comparison?: boolean
    comparison_mode?: ComparisonMode
    comparison_date_from?: string
    comparison_date_to?: string
}

export type ReportFilters = ComparisonFields & {
    date_from?: string
    date_to?: string
    countries?: string[]
    zones?: string[]
    states?: string[]
    cities?: string[]
}

export type ComparisonMeta = {
    mode: ComparisonMode
    date_from: string
    date_to: string
}

export type MetricDelta = {
    comparison_value?: number | null
    pct_change?: number | null
}

export type ComparedResponse<T, D = Record<string, MetricDelta>> = {
    current: T
    comparison_mode?: ComparisonMode | null
    comparison?: {
        meta: ComparisonMeta
        data: T
        deltas: D
    } | null
}

export type TrendPoint = {
    month: string
    revenue: number
}

export type ProductMix = {
    exams_pct: number
    books_pct: number
    courses_pct: number
    unknown_pct: number
}

export type GeoPoint = {
    dimension: string
    revenue: number
}

export type TotalSalesBase = {
    total_clients: number
    total_exams: number
    exam_revenue: number
    total_books: number
    book_revenue: number
    total_courses: number
    course_revenue: number
    total_otros: number
    otros_revenue: number
    total_revenue: number
    expected_revenue: number
    expected_cost: number
    uncategorized_revenue: number
    unknown_site_revenue: number
    unknown_site_expected_revenue: number
    profit_margin: number
    trend_points: TrendPoint[]
    geo_points: GeoPoint[]
    product_mix: ProductMix | null
}

export type TotalSalesResponse = ComparedResponse<TotalSalesBase>

export type PDFHeader = {
    title: string
    subtitle: string
    generated_at: string
    filters_summary: Record<string, string>
}

export type PDFKpiItem = {
    label: string
    value: string
    growth?: string | null
    growth_positive?: boolean | null
}

export type PDFTrendPoint = {
    label: string
    value: number
    scaled: number
}

export type PDFGeoPoint = {
    label: string
    value: number
    scaled: number
}

export type PDFTableRow = {
    cells: string[]
}

export type PDFTable = {
    headers: string[]
    rows: PDFTableRow[]
    column_widths: number[]
}

export type VentasTotalesPDFPayload = {
    header: PDFHeader
    kpis: PDFKpiItem[]
    trend_points: PDFTrendPoint[]
    geo_points: PDFGeoPoint[]
}

export type PorAsesorPDFPayload = {
    header: PDFHeader
    kpis: PDFKpiItem[]
    table: PDFTable
}

export type AsesorDetailPDFPayload = {
    header: PDFHeader
    kpis: PDFKpiItem[]
    geo_table: PDFTable
    categories_table: PDFTable
    status_table: PDFTable
}

export type DetalleAsesorPDFPayload = {
    header: PDFHeader
    table_identity: PDFTable
    table_exams: PDFTable
    orientation: string
}

export type PorPaisPDFPayload = {
    header: PDFHeader
    kpis: PDFKpiItem[]
    summary_table: PDFTable
    status_table: PDFTable
}

export type PorPaisDetailPDFPayload = {
    header: PDFHeader
    kpis: PDFKpiItem[]
    detail_table: PDFTable
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

export type AsesorFilters = ReportFilters & {
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
    uncategorized_revenue: number
    total_revenue: number
    total_books: number
    total_courses: number
    exam_revenue: number
    book_revenue: number
    course_revenue: number
    books_courses_ganados: number
    books_courses_perdidos: number
    books_courses_mantenidos: number
    allocated_revenue: number
    expected_revenue: number
    expected_cost: number
    profit_margin: number
}

export type AsesorReportBase = {
    rows: AsesorRow[]
    next_cursor: string | null
    has_more: boolean
}

export type AsesorReportResponse = ComparedResponse<AsesorReportBase>

export type ExamBrandDetail = {
    exams: number
    schools: number
    revenue: number
}

export type BusinessStatusDetail = {
    schools: number
    exams: number
    books: number
    courses: number
    revenue: number
}

export type AsesorDetailBase = {
    seller_name: string
    countries: string[]
    zones: string[]
    states: string[]
    cities: string[]
    total_schools: number
    total_exams: number
    uncategorized_revenue: number
    total_revenue: number
    exam_breakdown: Record<string, ExamBrandDetail>
    ganados: BusinessStatusDetail
    perdidos: BusinessStatusDetail
    mantenidos: BusinessStatusDetail
    total_books: number
    total_courses: number
    book_revenue: number
    course_revenue: number
    allocated_revenue: number
    expected_revenue: number
    expected_cost: number
    profit_margin: number
}

export type AsesorDetailResponse = ComparedResponse<AsesorDetailBase>

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
    exam_type: string
    exam_counts: Record<string, number>
    total: number
}

export type DetalleAsesorReportBase = {
    rows: DetalleAsesorRow[]
    next_cursor: number | null
    has_more: boolean
}

export type DetalleAsesorReportResponse = {
    current: DetalleAsesorReportBase
}

export type PorPaisFilters = ComparisonFields & {
    date_from: string
    date_to: string
}

export type PorPaisSummaryRow = {
    country: string
    total_schools: number
    total_revenue: number
    uncategorized_revenue: number
    cambridge: number
    ielts: number
    michigan: number
    tea: number
    other: number
    total_books: number
    total_courses: number
    exam_revenue: number
    book_revenue: number
    course_revenue: number
}

export type PorPaisStatusRow = {
    country: string
    schools_ganados: number
    schools_perdidos: number
    schools_mantenidos: number
    exams_ganados: number
    exams_perdidos: number
    exams_mantenidos: number
    books_courses_ganados: number
    books_courses_perdidos: number
    books_courses_mantenidos: number
}

export type PorPaisReportBase = {
    summary_rows: PorPaisSummaryRow[]
    status_rows: PorPaisStatusRow[]
}

export type PorPaisReportResponse = ComparedResponse<PorPaisReportBase>

export type PorPaisDetailResponse = {
    country: string
    exam_counts: Record<string, number>
    comparison_exam_counts?: Record<string, number> | null
    total_books: number
    total_courses: number
    book_revenue: number
    course_revenue: number
    comparison_total_books?: number | null
    comparison_total_courses?: number | null
    comparison_book_revenue?: number | null
    comparison_course_revenue?: number | null
    exam_revenue: number
    comparison_exam_revenue?: number | null
}
