import { useState } from "react"
import GeoFilters from "@/components/filters/GeoFilters"
import { useFilterOptions } from "@/hooks/useReports"
import type { ReportFilters } from "@/types"
import DateRangePicker from "./DateRangePicker"
import ExportButtons from "./ExportButtons"

type FilterBarProps = {
    value?: ReportFilters
    onChange: (filters: ReportFilters) => void
    onExportPdf?: () => void
    onExportExcel?: () => void
}

export default function FilterBar(props: FilterBarProps) {
    const { data: options, isLoading } = useFilterOptions()
    const [internalSelected, setInternalSelected] = useState<ReportFilters>({
        countries: [],
        zones: [],
        states: [],
        cities: [],
        date_from: undefined,
        date_to: undefined,
    })
    const selected = props.value ?? internalSelected

    const commitChange = (updated: ReportFilters) => {
        if (props.value === undefined) {
            setInternalSelected(updated)
        }
        props.onChange(updated)
    }

    const handleSelectChange = (key: string, value: string) => {
        const updated = { ...selected, [key]: value === "all" ? [] : [value] }
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

    if (isLoading) return <div className="text-sm text-muted-foreground">Cargando filtros...</div>

    return (
        <div className="overflow-x-auto">
            <div className="flex flex-nowrap items-end gap-4">
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
                    triggerClassName="min-w-32"
                    onChange={handleSelectChange}
                />
                <ExportButtons onExportPdf={props.onExportPdf} onExportExcel={props.onExportExcel} />
            </div>
        </div>
    )
}
