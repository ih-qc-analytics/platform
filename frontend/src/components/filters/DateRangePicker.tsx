import FilterFieldShell from "@/components/filters/FilterFieldShell"
import { FILTER_CONTROL_CLASS, FILTER_FIELD_WIDTH_CLASS } from "@/components/filters/controlStyles"

type DateRangePickerProps = {
    dateFrom: string | undefined
    dateTo: string | undefined
    onDateFromChange: (value: string) => void
    onDateToChange: (value: string) => void
}

export default function DateRangePicker({ dateFrom, dateTo, onDateFromChange, onDateToChange }: DateRangePickerProps) {
    return (
        <>
            <FilterFieldShell label="Fecha desde" className={FILTER_FIELD_WIDTH_CLASS}>
                <input
                    type="date"
                    value={dateFrom ?? ""}
                    onChange={(e) => onDateFromChange(e.target.value)}
                    className={FILTER_CONTROL_CLASS}
                />
            </FilterFieldShell>
            <FilterFieldShell label="Fecha hasta" className={FILTER_FIELD_WIDTH_CLASS}>
                <input
                    type="date"
                    value={dateTo ?? ""}
                    onChange={(e) => onDateToChange(e.target.value)}
                    className={FILTER_CONTROL_CLASS}
                />
            </FilterFieldShell>
        </>
    )
}
