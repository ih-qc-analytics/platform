import { useMemo } from "react"

import SingleSelectField, { cleanOptions } from "@/components/filters/SingleSelectField"
import type { FilterOptionsResponse } from "@/types"

export type GeoFilterKey = "countries" | "zones" | "states" | "cities"

type GeoFilterConfig = {
    key: GeoFilterKey
    label: string
}

type GeoFiltersProps<TFilters extends Partial<Record<GeoFilterKey, string[]>>> = {
    filters: TFilters
    options?: FilterOptionsResponse
    configs: GeoFilterConfig[]
    triggerClassName?: string
    onChange: (key: GeoFilterKey, value: string) => void
}

export default function GeoFilters<TFilters extends Partial<Record<GeoFilterKey, string[]>>>({
    filters,
    options,
    configs,
    triggerClassName = "",
    onChange,
}: GeoFiltersProps<TFilters>) {
    const optionMap = useMemo(
        () => ({
            countries: cleanOptions(options?.countries ?? []),
            zones: cleanOptions(options?.zones ?? []),
            states: cleanOptions(options?.states ?? []),
            cities: cleanOptions(options?.cities ?? []),
        }),
        [options],
    )

    return (
        <>
            {configs.map(({ key, label }) => (
                <SingleSelectField
                    key={key}
                    label={label}
                    value={filters[key]?.[0] ?? "all"}
                    options={optionMap[key]}
                    triggerClassName={triggerClassName}
                    onChange={value => onChange(key, value)}
                />
            ))}
        </>
    )
}
