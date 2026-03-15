import { useQuery } from "@tanstack/react-query"
import { ReportFilters } from "@/types"
import { fetchTotalSalesData } from "@/api/reports"
import { fetchFilterOptions } from "@/api/filters"

export const useTotalSalesData = (filters: ReportFilters) =>
    useQuery({
        queryKey: ["ventas-totales", JSON.stringify(filters)],
        queryFn: () => fetchTotalSalesData(filters),
    })

export const useFilterOptions = () =>
    useQuery({
        queryKey: ["filter-options"],
        queryFn: fetchFilterOptions,
        staleTime: Infinity,
        gcTime: Infinity,
    })