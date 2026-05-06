import {
    AsesorDetail,
    AsesorFilters,
    AsesorReportResponse,
    DetalleAsesorFilters,
    DetalleAsesorReportResponse,
    PorPaisDetailResponse,
    PorPaisFilters,
    PorPaisReportResponse,
    ReportFilters,
    TotalSalesResponse,
} from "@/types"
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

export const fetchDetalleAsesorReport = async (
    filters: DetalleAsesorFilters,
): Promise<DetalleAsesorReportResponse> => {
    const res = await fetch(`${config.apiUrl}/reports/detalle-asesor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const fetchPorPaisReport = async (filters: PorPaisFilters): Promise<PorPaisReportResponse> => {
    const res = await fetch(`${config.apiUrl}/reports/por-pais`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const fetchPorPaisDetail = async (
    country: string,
    filters: PorPaisFilters,
): Promise<PorPaisDetailResponse> => {
    const res = await fetch(`${config.apiUrl}/reports/por-pais/${country}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}
