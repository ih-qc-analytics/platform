import type { PorPaisFilters, ReportFilters } from "@/types"

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
})

export const getDefaultPorPaisFilters = (): PorPaisFilters => getRollingYearDateRange()
