import {
    AsesorDetailResponse,
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

import { apiRequest, apiResponse } from "./client"
import { downloadPdfBlob } from "@/lib/exportPdf"

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
    const response = await apiResponse(path, {
        method: "POST",
        body: filters,
    })
    const blob = await response.blob()
    const contentType = blob.type
    if (contentType && !contentType.includes(EXCEL_CONTENT_TYPE)) {
        throw new Error("Unexpected file type returned by server")
    }
    downloadBlob(blob, parseFilename(response.headers.get("content-disposition"), fallbackFilename))
}

export const fetchTotalSalesData = async (filters: ReportFilters): Promise<TotalSalesResponse> =>
    apiRequest<TotalSalesResponse>("/reports/ventas-totales", {
        method: "POST",
        body: filters,
    })

export const fetchAsesorReport = async (filters: AsesorFilters): Promise<AsesorReportResponse> =>
    apiRequest<AsesorReportResponse>("/reports/por-asesor", {
        method: "POST",
        body: filters,
    })

export const fetchAsesorDetail = async (sellerId: number, filters: AsesorFilters): Promise<AsesorDetailResponse> =>
    apiRequest<AsesorDetailResponse>(`/reports/por-asesor/${sellerId}`, {
        method: "POST",
        body: filters,
    })

export const fetchDetalleAsesorReport = async (filters: DetalleAsesorFilters): Promise<DetalleAsesorReportResponse> =>
    apiRequest<DetalleAsesorReportResponse>("/reports/detalle-asesor", {
        method: "POST",
        body: filters,
    })

export const fetchPorPaisReport = async (filters: PorPaisFilters): Promise<PorPaisReportResponse> =>
    apiRequest<PorPaisReportResponse>("/reports/por-pais", {
        method: "POST",
        body: filters,
    })

export const fetchPorPaisDetail = async (country: string, filters: PorPaisFilters): Promise<PorPaisDetailResponse> =>
    apiRequest<PorPaisDetailResponse>(`/reports/por-pais/${country}`, {
        method: "POST",
        body: filters,
    })

export const exportTotalSalesExcel = async (filters: ReportFilters) =>
    exportExcel("/reports/ventas-totales/export/excel", filters, "ventas-totales.xlsx")

export const exportTotalSalesExcelAll = async (filters: ReportFilters) =>
    exportExcel("/reports/ventas-totales/export/excel/all", filters, "ventas-totales-all.xlsx")

const exportPdf = async <TFilters>(path: string, filters: TFilters, fallbackFilename: string) => {
    const response = await apiResponse(path, { method: "POST", body: filters })
    const blob = await response.blob()
    await downloadPdfBlob(blob, fallbackFilename, response.headers.get("content-disposition"))
}

export const exportVentasTotalesPdf = (filters: ReportFilters) =>
    exportPdf("/reports/ventas-totales/export/pdf", filters, "ventas-totales.pdf")

export const exportPorAsesorPdf = (filters: AsesorFilters) =>
    exportPdf("/reports/por-asesor/export/pdf", filters, "por-asesor.pdf")

export const exportAsesorDetailPdf = (sellerId: number, filters: AsesorFilters) =>
    exportPdf(`/reports/por-asesor/${sellerId}/export/pdf`, filters, "detalle-asesor.pdf")

export const exportDetalleAsesorPdf = (filters: DetalleAsesorFilters) =>
    exportPdf("/reports/detalle-asesor/export/pdf", filters, "detalle-asesor.pdf")

export const exportPorPaisPdf = (filters: PorPaisFilters) =>
    exportPdf("/reports/por-pais/export/pdf", filters, "por-pais.pdf")

export const exportPorPaisDetailPdf = (country: string, filters: PorPaisFilters) =>
    exportPdf(`/reports/por-pais/${country}/export/pdf`, filters, "detalle-por-pais.pdf")

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
