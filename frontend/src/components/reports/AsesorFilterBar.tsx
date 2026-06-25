import GeoFilters from "@/components/filters/GeoFilters"
import DateRangePicker from "@/components/filters/DateRangePicker"
import MultiSelectField, { cleanOptions } from "@/components/filters/MultiSelectField"
import ReportFilterBarShell from "@/components/filters/ReportFilterBarShell"
import type { AsesorFilters, FilterOptionsResponse } from "@/types"
import { useMemo } from "react"

type AsesorFilterBarProps = {
    filters: AsesorFilters
    options?: FilterOptionsResponse
    sellerOptions: string[]
    onFiltersChange: (filters: AsesorFilters) => void
    onExportPdf?: () => void
    onExportExcelWithFilters?: () => void
    onExportExcelWithoutFilters?: () => void
    isExportingPdf?: boolean
    isExportingExcel?: boolean
    exportingExcelVariant?: "filtered" | "all" | null
    exportError?: string | null
}

type FilterKey = "countries" | "zones" | "states" | "cities" | "sellers"

const GEO_FILTERS: Array<{ key: Exclude<FilterKey, "sellers">; label: string }> = [
    { key: "countries", label: "País" },
    { key: "zones", label: "Sede" },
    { key: "states", label: "Estado" },
    { key: "cities", label: "Ciudad" },
]

const triggerClassName = "min-w-40"

export default function AsesorFilterBar({
    filters,
    options,
    sellerOptions,
    onFiltersChange,
    onExportPdf,
    onExportExcelWithFilters,
    onExportExcelWithoutFilters,
    isExportingPdf,
    isExportingExcel,
    exportingExcelVariant,
    exportError,
}: AsesorFilterBarProps) {
    const cleanedSellerOptions = useMemo(() => cleanOptions(sellerOptions), [sellerOptions])

    const handleSelectChange = (key: FilterKey, value: string[]) => {
        const updated = {
            ...filters,
            [key]: value,
        }
        onFiltersChange(updated)
    }

    return (
        <div className="flex flex-col gap-6">
            <ReportFilterBarShell
                onClear={() =>
                    {
                        onFiltersChange({
                            date_from: `${new Date().getFullYear()}-01-01`,
                            date_to: new Date().toISOString().slice(0, 10),
                            countries: [],
                            zones: [],
                            states: [],
                            cities: [],
                            sellers: [],
                            show_comparison: false,
                            comparison_mode: "PREVIOUS_YEAR",
                        })
                    }
                }
                comparison={filters}
                onApplyComparison={next => onFiltersChange({ ...filters, ...next })}
                onExportPdf={onExportPdf}
                onExportExcelWithFilters={onExportExcelWithFilters}
                onExportExcelWithoutFilters={onExportExcelWithoutFilters}
                isExportingPdf={isExportingPdf}
                isExportingExcel={isExportingExcel}
                exportingExcelVariant={exportingExcelVariant}
                exportError={exportError}
            >
                <DateRangePicker
                    dateFrom={filters.date_from}
                    dateTo={filters.date_to}
                    onDateFromChange={value => onFiltersChange({ ...filters, date_from: value })}
                    onDateToChange={value => onFiltersChange({ ...filters, date_to: value })}
                />
                <GeoFilters
                    filters={filters}
                    options={options}
                    configs={GEO_FILTERS}
                    triggerClassName={triggerClassName}
                    onChange={handleSelectChange}
                />
                <MultiSelectField
                    label="Asesor"
                    values={filters.sellers ?? []}
                    options={cleanedSellerOptions}
                    triggerClassName={triggerClassName}
                    onChange={value => handleSelectChange("sellers", value)}
                />
            </ReportFilterBarShell>
        </div>
    )
}
