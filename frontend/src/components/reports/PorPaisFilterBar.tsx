import DateRangePicker from "@/components/filters/DateRangePicker"
import ReportFilterBarShell from "@/components/filters/ReportFilterBarShell"
import { getDefaultPorPaisFilters } from "@/lib/reportFilters"
import type { PorPaisFilters } from "@/types"

type PorPaisFilterBarProps = {
    filters: PorPaisFilters
    onChange: (filters: PorPaisFilters) => void
    onExportPdf?: () => void
    onExportExcelWithFilters?: () => void
    onExportExcelWithoutFilters?: () => void
    isExportingPdf?: boolean
    isExportingExcel?: boolean
    exportingExcelVariant?: "filtered" | "all" | null
    exportError?: string | null
}

export default function PorPaisFilterBar({
    filters,
    onChange,
    onExportPdf,
    onExportExcelWithFilters,
    onExportExcelWithoutFilters,
    isExportingPdf,
    isExportingExcel,
    exportingExcelVariant,
    exportError,
}: PorPaisFilterBarProps) {
    return (
        <ReportFilterBarShell
            onClear={() => onChange(getDefaultPorPaisFilters())}
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
                onDateFromChange={value => onChange({ ...filters, date_from: value })}
                onDateToChange={value => onChange({ ...filters, date_to: value })}
            />
        </ReportFilterBarShell>
    )
}
