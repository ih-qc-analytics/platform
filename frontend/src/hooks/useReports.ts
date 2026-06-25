import { useQuery } from "@tanstack/react-query"
import { AsesorFilters, DetalleAsesorFilters, PorPaisFilters, ReportFilters } from "@/types"
import {
    fetchAsesorDetail,
    fetchAsesorReport,
    fetchDetalleAsesorReport,
    fetchPorPaisDetail,
    fetchPorPaisReport,
    fetchTotalSalesData,
} from "@/api/reports"
import { fetchFilterOptions, fetchSellerOptions } from "@/api/filters"
import { useBaseCurrency } from "@/lib/reportPreferences"

export const useTotalSalesData = (filters: ReportFilters) => {
    const baseCurrency = useBaseCurrency()
    return useQuery({
        queryKey: ["ventas-totales", baseCurrency, JSON.stringify(filters)],
        queryFn: () => fetchTotalSalesData(filters),
    })
}

export const useAsesorReport = (filters: AsesorFilters, enabled = true) => {
    const baseCurrency = useBaseCurrency()
    return useQuery({
        queryKey: ["por-asesor", baseCurrency, JSON.stringify(filters)],
        queryFn: () => fetchAsesorReport(filters),
        enabled,
    })
}

export const useAsesorDetail = (sellerId: number | null, filters: AsesorFilters, enabled = true) => {
    const baseCurrency = useBaseCurrency()
    return useQuery({
        queryKey: ["por-asesor-detail", baseCurrency, sellerId, JSON.stringify(filters)],
        queryFn: () => fetchAsesorDetail(sellerId as number, filters),
        enabled: enabled && sellerId !== null,
    })
}

export const useDetalleAsesorReport = (filters: DetalleAsesorFilters, enabled = true) => {
    const baseCurrency = useBaseCurrency()
    return useQuery({
        queryKey: ["detalle-asesor", baseCurrency, JSON.stringify(filters)],
        queryFn: () => fetchDetalleAsesorReport(filters),
        enabled,
    })
}

export const usePorPaisReport = (filters: PorPaisFilters, enabled = true) => {
    const baseCurrency = useBaseCurrency()
    return useQuery({
        queryKey: ["por-pais", baseCurrency, JSON.stringify(filters)],
        queryFn: () => fetchPorPaisReport(filters),
        enabled,
    })
}

export const usePorPaisDetail = (country: string | null, filters: PorPaisFilters, enabled = true) => {
    const baseCurrency = useBaseCurrency()
    return useQuery({
        queryKey: ["por-pais-detail", baseCurrency, country, JSON.stringify(filters)],
        queryFn: () => fetchPorPaisDetail(country as string, filters),
        enabled: enabled && country !== null,
    })
}

export const useFilterOptions = () => {
    const baseCurrency = useBaseCurrency()
    return useQuery({
        queryKey: ["filter-options", baseCurrency],
        queryFn: fetchFilterOptions,
        staleTime: Infinity,
        gcTime: Infinity,
    })
}

export const useSellerOptions = () => {
    const baseCurrency = useBaseCurrency()
    return useQuery({
        queryKey: ["seller-options", baseCurrency],
        queryFn: fetchSellerOptions,
        staleTime: Infinity,
        gcTime: Infinity,
    })
}
