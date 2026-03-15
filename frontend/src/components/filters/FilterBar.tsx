import { useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useFilterOptions } from "@/hooks/useReports"
import type { ReportFilters } from "@/types"
import { Download } from "lucide-react"

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

    const handleDateChange = (key: "date_from" | "date_to", value: string) => {
        const updated = { ...selected, [key]: value || undefined }
        setSelected(updated)
        props.onChange(updated)
    }

    if (isLoading) return <div className="text-sm text-muted-foreground">Cargando filtros...</div>

    return (
        <div className="flex flex-wrap items-end gap-4 w-full">
            <div className="flex flex-col gap-1">
                <label className="text-sm text-muted-foreground">Fecha desde</label>
                <input
                    type="date"
                    value={selected.date_from ?? ""}
                    onChange={e => handleDateChange("date_from", e.target.value)}
                    className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
            </div>

            <div className="flex flex-col gap-1">
                <label className="text-sm text-muted-foreground">Fecha hasta</label>
                <input
                    type="date"
                    value={selected.date_to ?? ""}
                    onChange={e => handleDateChange("date_to", e.target.value)}
                    className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
            </div>

            {FILTER_CONFIG.map(f => {
                const opts = cleanOptions(options?.[f.optionsKey] ?? [])
                const currentValue = (selected as any)[f.key]?.[0] ?? "all"

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

            <div className="flex gap-2 ml-auto">
                <button
                    onClick={props.onExportPdf}
                    className="flex items-center gap-2 px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
                >
                    <Download size={16} />
                    Exportar PDF
                </button>
                <button
                    onClick={props.onExportExcel}
                    className="flex items-center gap-2 px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
                >
                    <Download size={16} />
                    Exportar Excel
                </button>
            </div>
        </div>
    )
}