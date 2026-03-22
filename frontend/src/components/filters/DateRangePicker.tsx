type DateRangePickerProps = {
    dateFrom: string | undefined
    dateTo: string | undefined
    onDateFromChange: (value: string) => void
    onDateToChange: (value: string) => void
}

export default function DateRangePicker({ dateFrom, dateTo, onDateFromChange, onDateToChange }: DateRangePickerProps) {
    return (
        <>
            <div className="flex flex-col gap-1">
                <label className="text-sm text-muted-foreground">Fecha desde</label>
                <input
                    type="date"
                    value={dateFrom ?? ""}
                    onChange={e => onDateFromChange(e.target.value)}
                    className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
            </div>
            <div className="flex flex-col gap-1">
                <label className="text-sm text-muted-foreground">Fecha hasta</label>
                <input
                    type="date"
                    value={dateTo ?? ""}
                    onChange={e => onDateToChange(e.target.value)}
                    className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
            </div>
        </>
    )
}