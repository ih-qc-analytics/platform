import config from "../config"
import type { FilterOptionsResponse } from "../types"

export const fetchFilterOptions = async (): Promise<FilterOptionsResponse> => {
    const res = await fetch(`${config.apiUrl}/filters/options`)
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}