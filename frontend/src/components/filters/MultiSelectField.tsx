import { ChevronDown, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuCheckboxItem,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import FilterFieldShell from "@/components/filters/FilterFieldShell"
import { FILTER_BUTTON_CLASS, FILTER_CONTROL_CLASS, FILTER_FIELD_WIDTH_CLASS } from "@/components/filters/controlStyles"
import { cn } from "@/lib/utils"

type MultiSelectFieldProps = {
    label: string
    values: string[]
    options: string[]
    onChange: (values: string[]) => void
    triggerClassName?: string
}

export default function MultiSelectField({
    label,
    values,
    options,
    onChange,
    triggerClassName = "",
}: MultiSelectFieldProps) {
    const cleanedOptions = cleanOptions(options)
    const selected = values.filter((value) => cleanedOptions.includes(value))

    const toggleValue = (value: string) => {
        if (selected.includes(value)) {
            onChange(selected.filter((item) => item !== value))
            return
        }
        onChange([...selected, value])
    }

    const triggerLabel =
        selected.length === 0 ? label : selected.length === 1 ? selected[0] : `${selected.length} seleccionados`

    return (
        <FilterFieldShell label={label} className={cn(FILTER_FIELD_WIDTH_CLASS, triggerClassName)}>
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button
                        variant="outline"
                        className={cn(FILTER_BUTTON_CLASS, FILTER_CONTROL_CLASS, "justify-between text-left")}
                    >
                        <span className="truncate">{triggerLabel}</span>
                        <ChevronDown className="size-4 text-slate-500" />
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="min-w-64 rounded-2xl p-2">
                    <DropdownMenuLabel className="px-3 py-2 text-xs uppercase tracking-wide text-slate-500">
                        {label}
                    </DropdownMenuLabel>
                    <DropdownMenuItem
                        className="rounded-xl px-3 py-2 text-sm"
                        onClick={() => onChange([])}
                        disabled={selected.length === 0}
                    >
                        <X className="size-4" />
                        Limpiar selección
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    {cleanedOptions.map((option) => (
                        <DropdownMenuCheckboxItem
                            key={option}
                            className="rounded-xl py-2 pl-8 pr-3"
                            checked={selected.includes(option)}
                            onCheckedChange={() => toggleValue(option)}
                        >
                            {option}
                        </DropdownMenuCheckboxItem>
                    ))}
                </DropdownMenuContent>
            </DropdownMenu>
        </FilterFieldShell>
    )
}

// eslint-disable-next-line react-refresh/only-export-components
export function cleanOptions(options: string[]) {
    return [...new Set(options.map((option) => option.trim()).filter(Boolean))]
}
