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
    const selected = values.filter(value => cleanedOptions.includes(value))

    const toggleValue = (value: string) => {
        if (selected.includes(value)) {
            onChange(selected.filter(item => item !== value))
            return
        }
        onChange([...selected, value])
    }

    const triggerLabel =
        selected.length === 0
            ? label
            : selected.length === 1
              ? selected[0]
              : `${selected.length} seleccionados`

    return (
        <FilterFieldShell label={label}>
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button
                        variant="outline"
                        className={cn(
                            "h-14 min-w-40 justify-between rounded-2xl border-transparent bg-muted/70 px-5 text-left text-base font-medium text-slate-700 shadow-none hover:bg-muted",
                            triggerClassName,
                        )}
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
                    {cleanedOptions.map(option => (
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

export function cleanOptions(options: string[]) {
    return [...new Set(options.map(option => option.trim()).filter(Boolean))]
}
