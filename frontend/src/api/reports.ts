import { ReportFilters, TotalSalesResponse } from "@/types"
import config from "../config"


export const fetchTotalSalesData = async (filters: ReportFilters): Promise<TotalSalesResponse> => {
    const params = new URLSearchParams()
    if (filters.date_from) params.append("date_from", filters.date_from)
    if (filters.date_to) params.append("date_to", filters.date_to)
    filters.countries?.forEach(c => params.append("countries", c))
    filters.zones?.forEach(z => params.append("zones", z))
    filters.states?.forEach(s => params.append("states", s))
    filters.cities?.forEach(c => params.append("cities", c))


    console.log("filters:", filters)
    console.log("params:", params.toString())

    
    const res = await fetch(`${config.apiUrl}/reports/ventas-totales?${params.toString()}`)
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}