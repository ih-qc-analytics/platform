import FilterFieldShell from "@/components/filters/FilterFieldShell"

type DateRangePickerProps = {
    dateFrom: string | undefined
    dateTo: string | undefined
    onDateFromChange: (value: string) => void
    onDateToChange: (value: string) => void
}

export default function DateRangePicker({ dateFrom, dateTo, onDateFromChange, onDateToChange }: DateRangePickerProps) {
    return (
        <>
            <FilterFieldShell label="Fecha desde">
                <input
                    type="date"
                    value={dateFrom ?? ""}
                    onChange={e => onDateFromChange(e.target.value)}
                    className="h-14 rounded-2xl border border-transparent bg-muted/70 px-4 text-sm text-slate-700 shadow-none outline-none transition focus:border-primary/20 focus:ring-2 focus:ring-primary/20"
                />
            </FilterFieldShell>
            <FilterFieldShell label="Fecha hasta">
                <input
                    type="date"
                    value={dateTo ?? ""}
                    onChange={e => onDateToChange(e.target.value)}
                    className="h-14 rounded-2xl border border-transparent bg-muted/70 px-4 text-sm text-slate-700 shadow-none outline-none transition focus:border-primary/20 focus:ring-2 focus:ring-primary/20"
                />
            </FilterFieldShell>
        </>
    )
}
