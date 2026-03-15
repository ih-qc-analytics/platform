import { useState } from "react"
import { Users, FileText, BookOpen, GraduationCap, DollarSign, TrendingUp, Percent, Calendar } from "lucide-react"
import FilterBar from "@/components/filters/FilterBar"
import KpiCard from "@/components/ui/KpiCard"
import TrendLine from "@/components/charts/TrendLine"
import GeoBar from "@/components/charts/GeoBar"
import { useTotalSalesData } from "@/hooks/useReports"
import type { ReportFilters } from "@/types"

export default function VentasTotales() {
    const [filters, setFilters] = useState<ReportFilters>({
        countries: [],
        zones: [],
        states: [],
        cities: [],
    })

    const { data, isLoading, isError } = useTotalSalesData(filters)

    return (
        <div className="flex flex-col gap-6 p-6">
            <div className="flex flex-col gap-1">
                <h1 className="text-2xl font-bold">Ventas Totales</h1>
                <p className="text-sm text-muted-foreground">Resumen general de ventas por período y región</p>
            </div>

            <FilterBar
                onChange={setFilters}
                onExportPdf={() => console.log("export pdf")}
                onExportExcel={() => console.log("export excel")}
            />

            {isError && (
                <div className="text-sm text-red-500">Error al cargar los datos. Intente de nuevo.</div>
            )}

            {isLoading ? (
                <div className="text-sm text-muted-foreground">Cargando...</div>
            ) : data ? (
                <>
                    <div className="grid grid-cols-3 gap-4">
                        <KpiCard
                            title="Total Clientes"
                            icon={<Users size={24} />}
                            value={data.total_clients}
                        />
                        <KpiCard
                            title="Total Exámenes"
                            icon={<FileText size={24} />}
                            value={data.total_exams}
                        />
                        <KpiCard
                            title="Ingreso por Exámenes"
                            icon={<DollarSign size={24} />}
                            value={data.exam_revenue}
                            prefix="$"
                        />
                        <KpiCard
                            title="Ingreso por Libros"
                            icon={<BookOpen size={24} />}
                            value={data.book_revenue}
                            prefix="$"
                        />
                        <KpiCard
                            title="Ingreso por Cursos"
                            icon={<GraduationCap size={24} />}
                            value={data.course_revenue}
                            prefix="$"
                        />
                        <KpiCard
                            title="Ingreso Total"
                            icon={<TrendingUp size={24} />}
                            value={data.total_revenue}
                            prefix="$"
                            growth={data.growth_pct || undefined}
                        />
                        <KpiCard
                            title="Margen de Utilidad"
                            icon={<Percent size={24} />}
                            value={data.profit_margin.toFixed(1)}
                            suffix="%"
                        />
                        {data.prior_year_revenue > 0 && (
                            <KpiCard
                                title="Ingreso Año Anterior"
                                icon={<Calendar size={24} />}
                                value={data.prior_year_revenue}
                                prefix="$"
                            />
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <TrendLine data={data.trend_points} />
                        <GeoBar data={data.geo_points} />
                    </div>
                </>
            ) : null}
        </div>
    )
}