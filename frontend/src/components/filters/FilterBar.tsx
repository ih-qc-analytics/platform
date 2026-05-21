import { useState } from "react"
import GeoFilters from "@/components/filters/GeoFilters"
import ReportFilterBarShell from "@/components/filters/ReportFilterBarShell"
import { useFilterOptions } from "@/hooks/useReports"
import { getDefaultReportFilters } from "@/lib/reportFilters"
import type { ReportFilters } from "@/types"
import DateRangePicker from "./DateRangePicker"

type FilterBarProps = {
    value?: ReportFilters
    onChange: (filters: ReportFilters) => void
    onExportPdf?: () => void
    onExportExcelWithFilters?: () => void
    onExportExcelWithoutFilters?: () => void
    isExportingPdf?: boolean
    isExportingExcel?: boolean
    exportingExcelVariant?: "filtered" | "all" | null
    exportError?: string | null
}

export default function FilterBar(props: FilterBarProps) {
    const { data: options, isLoading } = useFilterOptions()
    const [internalSelected, setInternalSelected] = useState<ReportFilters>(getDefaultReportFilters())
    const selected = props.value ?? internalSelected

    const commitChange = (updated: ReportFilters) => {
        if (props.value === undefined) {
            setInternalSelected(updated)
        }
        props.onChange(updated)
    }

    const handleSelectChange = (key: string, value: string[]) => {
        const updated = { ...selected, [key]: value }
        commitChange(updated)
    }

    const handleDateFromChange = (value: string) => {
        const updated = { ...selected, date_from: value || undefined }
        commitChange(updated)
    }

    const handleDateToChange = (value: string) => {
        const updated = { ...selected, date_to: value || undefined }
        commitChange(updated)
    }

    if (isLoading) return null

    return (
        <ReportFilterBarShell
            onClear={() => commitChange(getDefaultReportFilters())}
            onExportPdf={props.onExportPdf}
            onExportExcelWithFilters={props.onExportExcelWithFilters}
            onExportExcelWithoutFilters={props.onExportExcelWithoutFilters}
            isExportingPdf={props.isExportingPdf}
            isExportingExcel={props.isExportingExcel}
            exportingExcelVariant={props.exportingExcelVariant}
            exportError={props.exportError}
        >
            <DateRangePicker
                dateFrom={selected.date_from}
                dateTo={selected.date_to}
                onDateFromChange={handleDateFromChange}
                onDateToChange={handleDateToChange}
            />

            <GeoFilters
                filters={selected}
                options={options}
                configs={[
                    { key: "countries", label: "País" },
                    { key: "zones", label: "Sede" },
                    { key: "states", label: "Estado" },
                    { key: "cities", label: "Ciudad" },
                ]}
                triggerClassName="min-w-40"
                onChange={handleSelectChange}
            />
        </ReportFilterBarShell>
    )
}
