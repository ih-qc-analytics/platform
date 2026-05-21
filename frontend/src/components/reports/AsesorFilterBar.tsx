import GeoFilters from "@/components/filters/GeoFilters"
import MultiSelectField, { cleanOptions } from "@/components/filters/MultiSelectField"
import ReportFilterBarShell from "@/components/filters/ReportFilterBarShell"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import type { AsesorFilters, FilterOptionsResponse } from "@/types"
import { cn } from "@/lib/utils"
import { useMemo } from "react"

type AsesorFilterBarProps = {
    filters: AsesorFilters
    options?: FilterOptionsResponse
    sellerOptions: string[]
    yearOptions: number[]
    showComparison: boolean
    onFiltersChange: (filters: AsesorFilters) => void
    onToggleComparison: (value: boolean) => void
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
    yearOptions,
    showComparison,
    onFiltersChange,
    onToggleComparison,
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
                        onToggleComparison(false)
                        onFiltersChange({
                            year: new Date().getFullYear(),
                            countries: [],
                            zones: [],
                            states: [],
                            cities: [],
                            sellers: [],
                        })
                    }
                }
                onExportPdf={onExportPdf}
                onExportExcelWithFilters={onExportExcelWithFilters}
                onExportExcelWithoutFilters={onExportExcelWithoutFilters}
                isExportingPdf={isExportingPdf}
                isExportingExcel={isExportingExcel}
                exportingExcelVariant={exportingExcelVariant}
                exportError={exportError}
            >
                <div className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
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
                </div>
            </ReportFilterBarShell>

            <div className="rounded-3xl border border-border bg-card px-6 py-5 shadow-sm">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex flex-wrap gap-3">
                        {yearOptions.map(year => {
                            const isActive = filters.year === year
                            return (
                                <Button
                                    key={year}
                                    variant={isActive ? "default" : "outline"}
                                    className={cn(
                                        "min-w-28 rounded-2xl px-6 py-6 text-lg shadow-none",
                                        isActive
                                            ? "bg-slate-950 text-white hover:bg-slate-900"
                                            : "bg-background text-foreground hover:bg-muted",
                                    )}
                                    onClick={() => onFiltersChange({ ...filters, year })}
                                >
                                    {year}
                                </Button>
                            )
                        })}
                    </div>

                    <div className="flex items-center gap-4 self-start lg:self-center">
                        <Switch
                            checked={showComparison}
                            onCheckedChange={onToggleComparison}
                            aria-label="Mostrar comparación año anterior"
                        />
                        <span className="text-base font-medium text-slate-700">
                            Mostrar comparación año anterior
                        </span>
                    </div>
                </div>
            </div>
        </div>
    )
}
