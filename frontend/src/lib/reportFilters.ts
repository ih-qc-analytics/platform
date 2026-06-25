import type { AsesorFilters, ComparisonMode, PorPaisFilters, ReportFilters } from "@/types"

const toIsoDate = (value: Date) => value.toISOString().slice(0, 10)

export const getRollingYearDateRange = (): { date_from: string; date_to: string } => {
    const today = new Date()
    const start = new Date(today)
    start.setFullYear(today.getFullYear() - 1)
    return {
        date_from: toIsoDate(start),
        date_to: toIsoDate(today),
    }
}

export const getDefaultReportFilters = (): ReportFilters => ({
    ...getRollingYearDateRange(),
    countries: [],
    zones: [],
    states: [],
    cities: [],
    show_comparison: false,
    comparison_mode: "PREVIOUS_YEAR",
})

export const getDefaultPorPaisFilters = (): PorPaisFilters => getRollingYearDateRange()

export const getCurrentYearDateRange = (): { date_from: string; date_to: string } => {
    const today = new Date()
    return {
        date_from: `${today.getFullYear()}-01-01`,
        date_to: toIsoDate(today),
    }
}

export const getDefaultAsesorFilters = (): AsesorFilters => ({
    ...getCurrentYearDateRange(),
    countries: [],
    zones: [],
    states: [],
    cities: [],
    sellers: [],
    show_comparison: false,
    comparison_mode: "PREVIOUS_YEAR" satisfies ComparisonMode,
})
