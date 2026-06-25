import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

import type { BaseCurrency } from "@/types"
import { getStoredBaseCurrency } from "@/lib/reportPreferences"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const currencySymbol = (currency: BaseCurrency) => (currency === "USD" ? "US$" : "$")

export const formatRevenue = (value: number, currency: BaseCurrency = getStoredBaseCurrency()) => {
    if (value >= 1_000_000) return `${currencySymbol(currency)}${(value / 1_000_000).toFixed(1)}M`
    if (value >= 1_000) return `${currencySymbol(currency)}${(value / 1_000).toFixed(1)}K`
    return `${currencySymbol(currency)}${value}`
}

export const formatCurrency = (
    value: number,
    currency: BaseCurrency = getStoredBaseCurrency(),
) =>
    new Intl.NumberFormat(currency === "USD" ? "en-US" : "es-MX", {
        style: "currency",
        currency,
        maximumFractionDigits: 0,
    }).format(value)

export const formatInteger = (value: number) =>
    new Intl.NumberFormat("es-MX", {
        maximumFractionDigits: 0,
    }).format(value)

export const getPercentChange = (current: number, previous: number | undefined) => {
    if (previous === undefined || previous === null) return null
    if (previous === 0) return null
    return ((current - previous) / previous) * 100
}

export const formatPercentChange = (value: number | null) => {
    if (value === null) return "Sin base"
    const prefix = value > 0 ? "+" : ""
    return `${prefix}${value.toFixed(1)}%`
}
