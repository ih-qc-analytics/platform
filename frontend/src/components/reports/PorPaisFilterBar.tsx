import DateRangePicker from "@/components/filters/DateRangePicker"
import ExportButtons from "@/components/filters/ExportButtons"
import { Card, CardContent } from "@/components/ui/card"
import type { PorPaisFilters } from "@/types"

type PorPaisFilterBarProps = {
    filters: PorPaisFilters
    onChange: (filters: PorPaisFilters) => void
    onExportPdf?: () => void
    onExportExcel?: () => void
}

export default function PorPaisFilterBar({
    filters,
    onChange,
    onExportPdf,
    onExportExcel,
}: PorPaisFilterBarProps) {
    return (
        <Card className="rounded-[2rem] shadow-sm">
            <CardContent className="flex flex-col gap-5 p-6 lg:flex-row lg:items-end lg:justify-between">
                <div className="flex flex-col gap-2">
                    <span className="text-sm font-medium text-slate-700">Período</span>
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
                        <DateRangePicker
                            dateFrom={filters.date_from}
                            dateTo={filters.date_to}
                            onDateFromChange={value => onChange({ ...filters, date_from: value })}
                            onDateToChange={value => onChange({ ...filters, date_to: value })}
                        />
                    </div>
                </div>
                <ExportButtons onExportPdf={onExportPdf} onExportExcel={onExportExcel} />
            </CardContent>
        </Card>
    )
}
