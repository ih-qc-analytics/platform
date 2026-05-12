import {
    AsesorDetailPDFPayload,
    AsesorDetail,
    AsesorFilters,
    DetalleAsesorPDFPayload,
    AsesorReportResponse,
    DetalleAsesorFilters,
    DetalleAsesorReportResponse,
    PorPaisDetailPDFPayload,
    PorAsesorPDFPayload,
    PorPaisDetailResponse,
    PorPaisPDFPayload,
    PorPaisFilters,
    PorPaisReportResponse,
    VentasTotalesPDFPayload,
    ReportFilters,
    TotalSalesResponse,
} from "@/types"
import config from "../config"

const EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

const parseFilename = (contentDisposition: string | null, fallback: string) => {
    const match = contentDisposition?.match(/filename="?([^"]+)"?/)
    return match?.[1] ?? fallback
}

const downloadBlob = (blob: Blob, filename: string) => {
    const objectUrl = window.URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = objectUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.URL.revokeObjectURL(objectUrl)
}

const exportExcel = async <TFilters>(path: string, filters: TFilters, fallbackFilename: string) => {
    const res = await fetch(`${config.apiUrl}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)

    const blob = await res.blob()
    const contentType = res.headers.get("content-type")
    if (contentType && !contentType.includes(EXCEL_CONTENT_TYPE)) {
        throw new Error("Unexpected file type returned by server")
    }

    downloadBlob(blob, parseFilename(res.headers.get("content-disposition"), fallbackFilename))
}

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

export const exportTotalSalesExcel = async (filters: ReportFilters) =>
    exportExcel("/reports/ventas-totales/export/excel", filters, "ventas-totales.xlsx")

export const exportTotalSalesExcelAll = async (filters: ReportFilters) =>
    exportExcel("/reports/ventas-totales/export/excel/all", filters, "ventas-totales-all.xlsx")

export const fetchVentasTotalesPdfPayload = async (
    filters: ReportFilters,
): Promise<VentasTotalesPDFPayload> => {
    const res = await fetch(`${config.apiUrl}/reports/ventas-totales/export/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const fetchPorAsesorPdfPayload = async (
    filters: AsesorFilters,
): Promise<PorAsesorPDFPayload> => {
    const res = await fetch(`${config.apiUrl}/reports/por-asesor/export/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const fetchAsesorDetailPdfPayload = async (
    sellerId: number,
    filters: AsesorFilters,
): Promise<AsesorDetailPDFPayload> => {
    const res = await fetch(`${config.apiUrl}/reports/por-asesor/${sellerId}/export/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const fetchDetalleAsesorPdfPayload = async (
    filters: DetalleAsesorFilters,
): Promise<DetalleAsesorPDFPayload> => {
    const res = await fetch(`${config.apiUrl}/reports/detalle-asesor/export/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const fetchPorPaisPdfPayload = async (
    filters: PorPaisFilters,
): Promise<PorPaisPDFPayload> => {
    const res = await fetch(`${config.apiUrl}/reports/por-pais/export/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const fetchPorPaisDetailPdfPayload = async (
    country: string,
    filters: PorPaisFilters,
): Promise<PorPaisDetailPDFPayload> => {
    const res = await fetch(`${config.apiUrl}/reports/por-pais/${country}/export/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
    })
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return res.json()
}

export const exportAsesorExcel = async (filters: AsesorFilters) =>
    exportExcel("/reports/por-asesor/export/excel", filters, "por-asesor.xlsx")

export const exportAsesorExcelAll = async (filters: AsesorFilters) =>
    exportExcel("/reports/por-asesor/export/excel/all", filters, "por-asesor-all.xlsx")

export const exportDetalleAsesorExcel = async (filters: DetalleAsesorFilters) =>
    exportExcel("/reports/detalle-asesor/export/excel", filters, "detalle-asesor.xlsx")

export const exportDetalleAsesorExcelAll = async (filters: DetalleAsesorFilters) =>
    exportExcel("/reports/detalle-asesor/export/excel/all", filters, "detalle-asesor-all.xlsx")

export const exportPorPaisExcel = async (filters: PorPaisFilters) =>
    exportExcel("/reports/por-pais/export/excel", filters, "por-pais.xlsx")

export const exportPorPaisExcelAll = async (filters: PorPaisFilters) =>
    exportExcel("/reports/por-pais/export/excel/all", filters, "por-pais-all.xlsx")
