import { useMemo, useState } from "react"
import { ChevronRight } from "lucide-react"

import { exportPorPaisExcel, exportPorPaisExcelAll, exportPorPaisPdf } from "@/api/reports"
import PorPaisDetail from "@/components/reports/PorPaisDetail"
import PorPaisFilterBar from "@/components/reports/PorPaisFilterBar"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { usePorPaisReport } from "@/hooks/useReports"
import { getDefaultPorPaisFilters } from "@/lib/reportFilters"
import { cn, formatCurrency, formatInteger, formatPercentChange, getPercentChange } from "@/lib/utils"
import type { PorPaisFilters, PorPaisStatusRow, PorPaisSummaryRow } from "@/types"

export default function PorPais() {
    const [filters, setFilters] = useState<PorPaisFilters>(getDefaultPorPaisFilters())
    const [selectedCountry, setSelectedCountry] = useState<string | null>(null)
    const [isExportingPdf, setIsExportingPdf] = useState(false)
    const [isExportingExcel, setIsExportingExcel] = useState(false)
    const [exportingExcelVariant, setExportingExcelVariant] = useState<"filtered" | "all" | null>(null)
    const [exportError, setExportError] = useState<string | null>(null)
    const requestFilters = useMemo(() => filters, [filters])
    const { data, isLoading, isError } = usePorPaisReport(requestFilters)

    const summaryRows = data?.current.summary_rows ?? []
    const statusRows = data?.current.status_rows ?? []
    const comparisonRowsByCountry = useMemo(
        () => new Map((data?.comparison?.data.summary_rows ?? []).map((row) => [row.country, row])),
        [data?.comparison?.data.summary_rows],
    )

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
                await exportPorPaisExcel(filters)
            } else {
                await exportPorPaisExcelAll(filters)
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
            await exportPorPaisPdf(filters)
        } catch {
            setExportError("No fue posible exportar el archivo. Intenta de nuevo.")
        } finally {
            setIsExportingPdf(false)
        }
    }

    return (
        <div className="flex flex-col gap-8 p-6">
            <PorPaisFilterBar
                filters={filters}
                onChange={(nextFilters) => {
                    setExportError(null)
                    setFilters(nextFilters)
                }}
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
                        Resultado por País
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">Resumen por país y detalle por familia de exámenes.</p>
                </CardHeader>
                <CardContent className="px-0 pb-4">
                    {isError && (
                        <div className="px-6 py-10 text-sm text-destructive">
                            Error al cargar el resultado por país.
                        </div>
                    )}

                    {isLoading ? (
                        <PorPaisTableSkeleton columns={12} />
                    ) : summaryRows.length === 0 ? (
                        <div className="px-6 py-10 text-sm text-muted-foreground">
                            No hay resultados para el período seleccionado.
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <Table className="min-w-max">
                                <TableHeader>
                                    <TableRow className="hover:bg-transparent">
                                        <TableHeadCell className="sticky left-0 z-10 min-w-36 bg-card text-left">
                                            País
                                        </TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">Colegios</TableHeadCell>
                                        <TableHeadCell className="min-w-32 text-right">Valor Total</TableHeadCell>
                                        <TableHeadCell className="min-w-32 text-right">Sin Categorizar</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">Cambridge</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">IELTS</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">MET</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">TEA</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">Otros</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">Libros</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">Cursos</TableHeadCell>
                                        <TableHeadCell className="w-10" />
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {summaryRows.map((row) => (
                                        <ClickableCountryRow
                                            key={row.country}
                                            row={row}
                                            comparisonRow={comparisonRowsByCountry.get(row.country)}
                                            showComparison={Boolean(filters.show_comparison && data?.comparison)}
                                            onSelect={() => setSelectedCountry(row.country)}
                                        />
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </CardContent>
            </Card>

            {Boolean(filters.show_comparison && data?.comparison) && (
                <Card className="rounded-[2rem] shadow-sm">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-2xl font-semibold tracking-tight text-slate-900">
                            Ganados, Perdidos y Mantenidos
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="px-0 pb-4">
                        {isLoading ? (
                            <PorPaisTableSkeleton columns={7} />
                        ) : statusRows.length === 0 ? (
                            <div className="px-6 py-10 text-sm text-muted-foreground">
                                No hay resultados de estado para el período seleccionado.
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <Table className="min-w-max">
                                    <TableHeader>
                                        <TableRow className="hover:bg-transparent">
                                            <TableHeadCell className="sticky left-0 z-10 min-w-36 bg-card text-left">
                                                País
                                            </TableHeadCell>
                                            <TableHeadCell className="min-w-24 text-center">
                                                Colegios Ganados
                                            </TableHeadCell>
                                            <TableHeadCell className="min-w-24 text-center">
                                                Colegios Perdidos
                                            </TableHeadCell>
                                            <TableHeadCell className="min-w-24 text-center">
                                                Colegios Mantenidos
                                            </TableHeadCell>
                                            <TableHeadCell className="min-w-24 text-center">
                                                Exámenes Ganados
                                            </TableHeadCell>
                                            <TableHeadCell className="min-w-24 text-center">
                                                Exámenes Perdidos
                                            </TableHeadCell>
                                            <TableHeadCell className="min-w-24 text-center">
                                                Exámenes Mantenidos
                                            </TableHeadCell>
                                            <TableHeadCell className="min-w-24 text-center">L+C Ganados</TableHeadCell>
                                            <TableHeadCell className="min-w-24 text-center">L+C Perdidos</TableHeadCell>
                                            <TableHeadCell className="min-w-24 text-center">
                                                L+C Mantenidos
                                            </TableHeadCell>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {statusRows.map((row) => (
                                            <StatusRowView key={row.country} row={row} />
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            <AsesorGlossaryNote />

            <PorPaisDetail
                country={selectedCountry}
                open={selectedCountry !== null}
                onOpenChange={(open) => {
                    if (!open) setSelectedCountry(null)
                }}
                filters={filters}
            />
        </div>
    )
}

function AsesorGlossaryNote() {
    return (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-5 py-4 text-xs text-slate-500 space-y-1">
            <p className="font-semibold text-slate-600 mb-2">Notas</p>
            <p>
                <span className="font-medium text-slate-700">Sin categorizar:</span> Pagos registrados sin ningún
                detalle de producto en el sistema — no existen líneas de venta asociadas. No es que el producto sea
                desconocido: es que no hay registro de qué se vendió. Se suman al ingreso total pero no aparecen en
                ningún desglose por tipo.
            </p>
        </div>
    )
}

function ClickableCountryRow({
    row,
    comparisonRow,
    showComparison,
    onSelect,
}: {
    row: PorPaisSummaryRow
    comparisonRow?: PorPaisSummaryRow
    showComparison: boolean
    onSelect: () => void
}) {
    return (
        <TableRow
            tabIndex={0}
            role="button"
            onClick={onSelect}
            onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault()
                    onSelect()
                }
            }}
            className="group cursor-pointer outline-none focus-visible:bg-muted/30"
        >
            <TableBodyCell className="sticky left-0 z-10 bg-card font-semibold text-slate-900 group-hover:bg-muted/30 group-focus-visible:bg-muted/30">
                {row.country}
            </TableBodyCell>
            <MetricCell
                value={row.total_schools}
                comparisonValue={comparisonRow?.total_schools}
                showComparison={showComparison}
                align="right"
            />
            <MetricCell
                value={row.total_revenue}
                comparisonValue={comparisonRow?.total_revenue}
                showComparison={showComparison}
                align="right"
                emphasize
                format={formatCurrency}
            />
            <MetricCell
                value={row.uncategorized_revenue}
                comparisonValue={comparisonRow?.uncategorized_revenue}
                showComparison={showComparison}
                align="right"
                format={formatCurrency}
            />
            <MetricCell
                value={row.cambridge}
                comparisonValue={comparisonRow?.cambridge}
                showComparison={showComparison}
                align="right"
                emphasize
            />
            <MetricCell
                value={row.ielts}
                comparisonValue={comparisonRow?.ielts}
                showComparison={showComparison}
                align="right"
                emphasize
            />
            <MetricCell
                value={row.michigan}
                comparisonValue={comparisonRow?.michigan}
                showComparison={showComparison}
                align="right"
                emphasize
            />
            <MetricCell
                value={row.tea}
                comparisonValue={comparisonRow?.tea}
                showComparison={showComparison}
                align="right"
                emphasize
            />
            <MetricCell
                value={row.other}
                comparisonValue={comparisonRow?.other}
                showComparison={showComparison}
                align="right"
                emphasize
            />
            <MetricCell
                value={row.total_books}
                comparisonValue={comparisonRow?.total_books}
                showComparison={showComparison}
                align="right"
            />
            <MetricCell
                value={row.total_courses}
                comparisonValue={comparisonRow?.total_courses}
                showComparison={showComparison}
                align="right"
            />
            <TableBodyCell className="w-12 text-right text-slate-400">
                <ChevronRight className="ml-auto size-5" />
            </TableBodyCell>
        </TableRow>
    )
}

function StatusRowView({ row }: { row: PorPaisStatusRow }) {
    return (
        <TableRow>
            <TableBodyCell className="sticky left-0 z-10 bg-card font-semibold text-slate-900">
                {row.country}
            </TableBodyCell>
            <StatusMetricCell value={row.schools_ganados} tone="success" />
            <StatusMetricCell value={row.schools_perdidos} tone="danger" />
            <StatusMetricCell value={row.schools_mantenidos} tone="info" />
            <StatusMetricCell value={row.exams_ganados} tone="success" />
            <StatusMetricCell value={row.exams_perdidos} tone="danger" />
            <StatusMetricCell value={row.exams_mantenidos} tone="info" />
            <StatusMetricCell value={row.books_courses_ganados} tone="success" />
            <StatusMetricCell value={row.books_courses_perdidos} tone="danger" />
            <StatusMetricCell value={row.books_courses_mantenidos} tone="info" />
        </TableRow>
    )
}

function TableHeadCell({ className, children }: { className?: string; children?: React.ReactNode }) {
    return (
        <TableHead
            className={cn(
                "border-b border-border px-3 py-3 text-xs font-semibold uppercase tracking-wide text-slate-700",
                className,
            )}
        >
            {children}
        </TableHead>
    )
}

function TableBodyCell({ className, children }: { className?: string; children: React.ReactNode }) {
    return (
        <TableCell className={cn("border-b border-border px-3 py-3 text-sm text-slate-700", className)}>
            {children}
        </TableCell>
    )
}

function MetricCell({
    value,
    comparisonValue,
    showComparison = false,
    align = "center",
    emphasize = false,
    format = formatInteger,
}: {
    value: number
    comparisonValue?: number
    showComparison?: boolean
    align?: "center" | "right"
    emphasize?: boolean
    format?: (value: number) => string
}) {
    const pct = showComparison && comparisonValue !== undefined ? getPercentChange(value, comparisonValue) : null

    return (
        <TableBodyCell className={align === "right" ? "text-right" : "text-center"}>
            <div className={cn("flex flex-col", align === "right" ? "items-end" : "items-center")}>
                <span className={cn("tabular-nums text-slate-700", emphasize && "font-semibold")}>{format(value)}</span>
                {showComparison && comparisonValue !== undefined ? (
                    <span className="text-[10px] text-muted-foreground">{format(comparisonValue)}</span>
                ) : null}
                {pct !== null ? (
                    <span className={cn("text-[10px] font-medium", pct >= 0 ? "text-emerald-600" : "text-rose-600")}>
                        {formatPercentChange(pct)}
                    </span>
                ) : null}
            </div>
        </TableBodyCell>
    )
}

function StatusMetricCell({ value, tone }: { value: number; tone: "success" | "danger" | "info" }) {
    return (
        <TableBodyCell>
            <div className="flex justify-center">
                <Badge variant={tone} className="min-w-14 px-2 py-0.5 text-xs font-semibold tabular-nums">
                    {formatInteger(value)}
                </Badge>
            </div>
        </TableBodyCell>
    )
}

function PorPaisTableSkeleton({ columns }: { columns: number }) {
    return (
        <div className="space-y-4 px-6 py-6">
            <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
                {Array.from({ length: columns }).map((_, index) => (
                    <Skeleton key={index} className="h-5 w-full" />
                ))}
            </div>
            {Array.from({ length: 3 }).map((_, rowIndex) => (
                <div
                    key={rowIndex}
                    className="grid gap-4 border-t border-border pt-4"
                    style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
                >
                    {Array.from({ length: columns }).map((_, colIndex) => (
                        <Skeleton key={colIndex} className="h-8 w-full" />
                    ))}
                </div>
            ))}
        </div>
    )
}
