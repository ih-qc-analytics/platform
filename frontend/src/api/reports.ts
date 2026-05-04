import { AsesorDetail, AsesorFilters, AsesorReportResponse, ReportFilters, TotalSalesResponse } from "@/types"
import config from "../config"

export const fetchTotalSalesData = async (filters: ReportFilters): Promise<TotalSalesResponse> => {
    const res = await fetch(`${config.apiUrl}/reports/ventas-totales`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const fetchAsesorReport = async (filters: AsesorFilters): Promise<AsesorReportResponse> => {
    const res = await fetch(`${config.apiUrl}/reports/por-asesor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const fetchAsesorDetail = async (
    sellerId: number,
    filters: AsesorFilters,
): Promise<AsesorDetail> => {
    const res = await fetch(`${config.apiUrl}/reports/por-asesor/${sellerId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}
