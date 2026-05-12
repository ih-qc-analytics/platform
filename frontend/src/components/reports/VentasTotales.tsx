import { useState } from "react"
import { Users, FileText, BookOpen, GraduationCap, DollarSign, TrendingUp, Percent, Calendar } from "lucide-react"
import VentasTotalesPDF from "@/components/pdf/VentasTotalesPDF"
import { exportTotalSalesExcel, exportTotalSalesExcelAll, fetchVentasTotalesPdfPayload } from "@/api/reports"
import FilterBar from "@/components/filters/FilterBar"
import KpiCard from "@/components/ui/KpiCard"
import TrendLine from "@/components/charts/TrendLine"
import GeoBar from "@/components/charts/GeoBar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useTotalSalesData } from "@/hooks/useReports"
import { downloadPdf } from "@/lib/exportPdf"
import type { ReportFilters } from "@/types"

export default function VentasTotales() {
    const [filters, setFilters] = useState<ReportFilters>({
        countries: [],
        zones: [],
        states: [],
        cities: [],
    })
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
            const payload = await fetchVentasTotalesPdfPayload(filters)
            await downloadPdf(<VentasTotalesPDF data={payload} />, "ventas-totales.pdf")
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
                        <div className="text-sm text-muted-foreground">Cargando...</div>
                    ) : data ? (
                        <>
                            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                                <KpiCard
                                    title="Total Clientes"
                                    icon={<Users className="size-6" />}
                                    value={data.total_clients}
                                />
                                <KpiCard
                                    title="Total Exámenes"
                                    icon={<FileText className="size-6" />}
                                    value={data.total_exams}
                                />
                                <KpiCard
                                    title="Ingreso por Exámenes"
                                    icon={<DollarSign className="size-6" />}
                                    value={data.exam_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Total Libros"
                                    icon={<BookOpen className="size-6" />}
                                    value={data.total_books}
                                />
                                <KpiCard
                                    title="Ingreso por Libros"
                                    icon={<BookOpen className="size-6" />}
                                    value={data.book_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Total Cursos"
                                    icon={<GraduationCap className="size-6" />}
                                    value={data.total_courses}
                                />
                                <KpiCard
                                    title="Ingreso por Cursos"
                                    icon={<GraduationCap className="size-6" />}
                                    value={data.course_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Otros"
                                    icon={<FileText className="size-6" />}
                                    value={(data as typeof data & { total_otros: number }).total_otros}
                                />
                                <KpiCard
                                    title="Ingreso por Otros"
                                    icon={<DollarSign className="size-6" />}
                                    value={(data as typeof data & { otros_revenue: number }).otros_revenue}
                                    prefix="$"
                                />
                                <KpiCard
                                    title="Ingreso Total"
                                    icon={<TrendingUp className="size-6" />}
                                    value={data.total_revenue}
                                    prefix="$"
                                    growth={data.growth_pct ?? undefined}
                                />
                                <KpiCard
                                    title="Margen de Utilidad"
                                    icon={<Percent className="size-6" />}
                                    value={data.profit_margin}
                                    suffix="%"
                                    decimals={1}
                                />
                                {data.prior_year_revenue > 0 && (
                                    <KpiCard
                                        title="Ingreso Año Anterior"
                                        icon={<Calendar className="size-6" />}
                                        value={data.prior_year_revenue}
                                        prefix="$"
                                    />
                                )}
                            </div>

                            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                                <TrendLine data={data.trend_points} />
                                <GeoBar data={data.geo_points} />
                            </div>
                        </>
                    ) : null}
                </CardContent>
            </Card>
        </div>
    )
}
