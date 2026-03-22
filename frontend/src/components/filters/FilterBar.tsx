import { useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useFilterOptions } from "@/hooks/useReports"
import type { ReportFilters } from "@/types"
import DateRangePicker from "./DateRangePicker"
import ExportButtons from "./ExportButtons"

type FilterBarProps = {
    onChange: (filters: ReportFilters) => void
    onExportPdf?: () => void
    onExportExcel?: () => void
}

const FILTER_CONFIG = [
    { label: "País", key: "countries", optionsKey: "countries" },
    { label: "Sede", key: "zones", optionsKey: "zones" },
    { label: "Estado", key: "states", optionsKey: "states" },
    { label: "Ciudad", key: "cities", optionsKey: "cities" },
] as const

const cleanOptions = (options: string[]): string[] =>
    [...new Set(options.map(o => o.trim()).filter(o => o.length > 0))]

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

            {FILTER_CONFIG.map(f => {
                const opts = cleanOptions(options?.[f.optionsKey] ?? [])
                const currentValue = (selected[f.key as keyof ReportFilters] as string[])?.[0] ?? "all"

                return (
                    <div key={f.key} className="flex flex-col gap-1 min-w-32">
                        <label className="text-sm text-muted-foreground">{f.label}</label>
                        <Select value={currentValue} onValueChange={val => handleSelectChange(f.key, val)}>
                            <SelectTrigger>
                                <SelectValue placeholder="Todos" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">Todos</SelectItem>
                                {opts.map(opt => (
                                    <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                )
            })}
            <ExportButtons onExportPdf={props.onExportPdf} onExportExcel={props.onExportExcel} />
        </div>
    )
}