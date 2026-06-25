import { useState } from "react"
import {
    Users,
    FileText,
    BookOpen,
    GraduationCap,
    DollarSign,
    TrendingUp,
    Percent,
    PackageSearch,
    Landmark,
} from "lucide-react"
import { exportTotalSalesExcel, exportTotalSalesExcelAll, exportVentasTotalesPdf } from "@/api/reports"
import FilterBar from "@/components/filters/FilterBar"
import KpiCard from "@/components/ui/KpiCard"
import TrendLine from "@/components/charts/TrendLine"
import GeoBar from "@/components/charts/GeoBar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useTotalSalesData } from "@/hooks/useReports"
import { getDefaultReportFilters } from "@/lib/reportFilters"
import type { ReportFilters } from "@/types"

export default function VentasTotales() {
    const [filters, setFilters] = useState<ReportFilters>(getDefaultReportFilters())
    const [isExportingPdf, setIsExportingPdf] = useState(false)
    const [isExportingExcel, setIsExportingExcel] = useState(false)
    const [exportingExcelVariant, setExportingExcelVariant] = useState<"filtered" | "all" | null>(null)
    const [exportError, setExportError] = useState<string | null>(null)

    const { data, isLoading, isError } = useTotalSalesData(filters)

    const handleFiltersChange = (nextFilters: ReportFilters) => {
        setExportError(null)
        setFilters(nextFilters)
    }

    const handleExportExcel = async (variant: "filtered" | "all") => {
        if (!filters.date_from || !filters.date_to) {
            setExportError("Selecciona fecha inicial y final antes de exportar.")
            return
        }

        setExportError(null)
        setIsExportingExcel(true)
        setExportingExcelVariant(variant)
        try {
            if (variant === "filtered") {
                await exportTotalSalesExcel(filters)
            } else {
                await exportTotalSalesExcelAll(filters)
            }
        } catch {
            setExportError("No fue posible exportar el archivo. Intenta de nuevo.")
        } finally {
            setIsExportingExcel(false)
            setExportingExcelVariant(null)
        }
    }

    const handleExportPdf = async () => {
        if (!filters.date_from || !filters.date_to) {
            setExportError("Selecciona fecha inicial y final antes de exportar.")
            return
        }

        setExportError(null)
        setIsExportingPdf(true)
        try {
            await exportVentasTotalesPdf(filters)
        } catch {
            setExportError("No fue posible exportar el archivo. Intenta de nuevo.")
        } finally {
            setIsExportingPdf(false)
        }
    }

    return (
        <div className="flex flex-col gap-8 p-6">
            <FilterBar
                value={filters}
                onChange={handleFiltersChange}
                onExportPdf={() => void handleExportPdf()}
                onExportExcelWithFilters={() => void handleExportExcel("filtered")}
                onExportExcelWithoutFilters={() => void handleExportExcel("all")}
                isExportingPdf={isExportingPdf}
                isExportingExcel={isExportingExcel}
                exportingExcelVariant={exportingExcelVariant}
                exportError={exportError}
            />
            <Card className="rounded-[2rem] shadow-sm">
                <CardHeader className="pb-2">
                    <CardTitle className="text-4xl font-semibold tracking-tight text-slate-900">
                        Ventas Totales
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">Resumen general de ventas por período y región</p>
                </CardHeader>
                <CardContent className="space-y-6">
                    {isError && (
                        <div className="text-sm text-destructive">Error al cargar los datos. Intente de nuevo.</div>
                    )}

                    {isLoading ? (
                        <VentasTotalesSkeleton />
                    ) : data ? (
                        <>
                            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                                <KpiCard
                                    title="Total Clientes"
                                    icon={<Users className="size-6" />}
                                    value={data.current.total_clients}
                                    showComparison={Boolean(data.comparison)}
                                    comparisonValue={data.comparison?.deltas.total_clients?.comparison_value}
                                    comparisonPct={data.comparison?.deltas.total_clients?.pct_change}
                                />
                                <KpiCard
                                    title="Total Exámenes"
                                    icon={<FileText className="size-6" />}
                                    value={data.current.total_exams}
                                    showComparison={Boolean(data.comparison)}
                                    comparisonValue={data.comparison?.deltas.total_exams?.comparison_value}
                                    comparisonPct={data.comparison?.deltas.total_exams?.pct_change}
                                />
                                <KpiCard
                                    title="Ingreso por Exámenes"
                                    icon={<DollarSign className="size-6" />}
                                    value={data.current.exam_revenue}
                                    prefix="$"
                                    showComparison={Boolean(data.comparison)}
                                    comparisonValue={data.comparison?.deltas.exam_revenue?.comparison_value}
                                    comparisonPct={data.comparison?.deltas.exam_revenue?.pct_change}
                                />
                                <KpiCard
                                    title="Total Libros"
                                    icon={<BookOpen className="size-6" />}
                                    value={data.current.total_books}
                                />
                                <KpiCard
                                    title="Ingreso por Libros"
                                    icon={<BookOpen className="size-6" />}
                                    value={data.current.book_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Total Cursos"
                                    icon={<GraduationCap className="size-6" />}
                                    value={data.current.total_courses}
                                />
                                <KpiCard
                                    title="Ingreso por Cursos"
                                    icon={<GraduationCap className="size-6" />}
                                    value={data.current.course_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Otros"
                                    icon={<FileText className="size-6" />}
                                    value={data.current.total_otros}
                                />
                                <KpiCard
                                    title="Ingreso por Otros"
                                    icon={<DollarSign className="size-6" />}
                                    value={data.current.otros_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Ingreso Total"
                                    icon={<TrendingUp className="size-6" />}
                                    value={data.current.total_revenue}
                                    prefix="$"
                                    showComparison={Boolean(data.comparison)}
                                    comparisonValue={data.comparison?.deltas.total_revenue?.comparison_value}
                                    comparisonPct={data.comparison?.deltas.total_revenue?.pct_change}
                                />
                                <KpiCard
                                    title="Ingreso Esperado"
                                    icon={<Landmark className="size-6" />}
                                    value={data.current.expected_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Costo Esperado"
                                    icon={<PackageSearch className="size-6" />}
                                    value={data.current.expected_cost}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Ingreso Sin Categorizar"
                                    icon={<DollarSign className="size-6" />}
                                    value={data.current.uncategorized_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Ingreso Sitio Desconocido"
                                    icon={<FileText className="size-6" />}
                                    value={data.current.unknown_site_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Esperado Sitio Desconocido"
                                    icon={<FileText className="size-6" />}
                                    value={data.current.unknown_site_expected_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Margen de Utilidad"
                                    icon={<Percent className="size-6" />}
                                    value={data.current.profit_margin}
                                    suffix="%"
                                    decimals={1}
                                />
                            </div>

                            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                                <TrendLine
                                    data={data.current.trend_points}
                                    comparisonData={data.comparison?.data.trend_points}
                                />
                                <GeoBar
                                    data={data.current.geo_points}
                                    comparisonData={data.comparison?.data.geo_points}
                                />
                            </div>
                        </>
                    ) : null}
                </CardContent>
            </Card>
        </div>
    )
}

function VentasTotalesSkeleton() {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 15 }).map((_, index) => (
                    <Card key={index}>
                        <CardContent className="flex items-start justify-between pt-6">
                            <div className="flex flex-col gap-3">
                                <Skeleton className="h-4 w-28" />
                                <Skeleton className="h-9 w-36" />
                                <Skeleton className="h-3 w-24" />
                            </div>
                            <Skeleton className="size-12 rounded-xl" />
                        </CardContent>
                    </Card>
                ))}
            </div>
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                {Array.from({ length: 2 }).map((_, index) => (
                    <Card key={index}>
                        <CardHeader>
                            <Skeleton className="h-5 w-32" />
                        </CardHeader>
                        <CardContent>
                            <Skeleton className="h-64 w-full rounded-2xl" />
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    )
}
