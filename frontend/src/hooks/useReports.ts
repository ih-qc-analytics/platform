import { useQuery } from "@tanstack/react-query"
import { AsesorFilters, ReportFilters } from "@/types"
import { fetchAsesorDetail, fetchAsesorReport, fetchTotalSalesData } from "@/api/reports"
import { fetchFilterOptions, fetchSellerOptions } from "@/api/filters"

export const useTotalSalesData = (filters: ReportFilters) =>
    useQuery({
        queryKey: ["ventas-totales", JSON.stringify(filters)],
        queryFn: () => fetchTotalSalesData(filters),
    })

export const useAsesorReport = (filters: AsesorFilters, enabled = true) =>
    useQuery({
        queryKey: ["por-asesor", JSON.stringify(filters)],
        queryFn: () => fetchAsesorReport(filters),
        enabled,
    })

export const useAsesorDetail = (
    sellerId: number | null,
    filters: AsesorFilters,
    enabled = true,
) =>
    useQuery({
        queryKey: ["por-asesor-detail", sellerId, JSON.stringify(filters)],
        queryFn: () => fetchAsesorDetail(sellerId as number, filters),
        enabled: enabled && sellerId !== null,
    })

export const useFilterOptions = () =>
    useQuery({
        queryKey: ["filter-options"],
        queryFn: fetchFilterOptions,
        staleTime: Infinity,
        gcTime: Infinity,
    })

export const useSellerOptions = () =>
    useQuery({
        queryKey: ["seller-options"],
        queryFn: fetchSellerOptions,
        staleTime: Infinity,
        gcTime: Infinity,
    })
