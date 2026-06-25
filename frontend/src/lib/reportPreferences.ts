import { useSyncExternalStore } from "react"

import type { BaseCurrency } from "@/types"

const STORAGE_KEY = "qc_analytics_base_currency"

const listeners = new Set<() => void>()

const isBaseCurrency = (value: string | null): value is BaseCurrency => value === "MXN" || value === "USD"

const readStoredBaseCurrency = (): BaseCurrency => {
    if (typeof window === "undefined") return "MXN"
    const storedValue = window.localStorage.getItem(STORAGE_KEY)
    return isBaseCurrency(storedValue) ? storedValue : "MXN"
}

let currentBaseCurrency: BaseCurrency = readStoredBaseCurrency()

const emitChange = () => {
    listeners.forEach((listener) => listener())
}

export const getStoredBaseCurrency = (): BaseCurrency => {
    if (typeof window !== "undefined") {
        currentBaseCurrency = readStoredBaseCurrency()
    }
    return currentBaseCurrency
}

export const setStoredBaseCurrency = (currency: BaseCurrency) => {
    currentBaseCurrency = currency
    if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, currency)
    }
    emitChange()
}

const subscribe = (listener: () => void) => {
    listeners.add(listener)
    return () => listeners.delete(listener)
}

export const useBaseCurrency = (): BaseCurrency => useSyncExternalStore(subscribe, getStoredBaseCurrency, () => "MXN")
