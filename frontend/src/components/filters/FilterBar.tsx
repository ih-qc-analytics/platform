import { useState } from "react"
import GeoFilters from "@/components/filters/GeoFilters"
import { Input } from "@/components/ui/input"
import { useFilterOptions } from "@/hooks/useReports"
import type { ReportFilters } from "@/types"
import DateRangePicker from "./DateRangePicker"
import ExportButtons from "./ExportButtons"

type FilterBarProps = {
    onChange: (filters: ReportFilters) => void
    onExportPdf?: () => void
    onExportExcel?: () => void
}

export default function FilterBar(props: FilterBarProps) {
    const { data: options, isLoading } = useFilterOptions()
    const [selected, setSelected] = useState<ReportFilters>({
        countries: [],
        zones: [],
        states: [],
        cities: [],
        date_from: undefined,
        date_to: undefined,
    })

    const handleSelectChange = (key: string, value: string) => {
        const updated = { ...selected, [key]: value === "all" ? [] : [value] }
        setSelected(updated)
        props.onChange(updated)
    }

    const handleDateFromChange = (value: string) => {
        const updated = { ...selected, date_from: value || undefined }
        setSelected(updated)
        props.onChange(updated)
    }

    const handleDateToChange = (value: string) => {
        const updated = { ...selected, date_to: value || undefined }
        setSelected(updated)
        props.onChange(updated)
    }

    if (isLoading) return <div className="text-sm text-muted-foreground">Cargando filtros...</div>

    return (
        <div className="flex flex-wrap items-end gap-4 w-full">
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
    )
}
