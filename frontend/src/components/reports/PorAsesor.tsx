import { useMemo, useState } from "react"
import { ChevronDown, ChevronRight, ChevronUp, ChevronsUpDown } from "lucide-react"

import { exportAsesorExcel, exportAsesorExcelAll, exportPorAsesorPdf } from "@/api/reports"
import AsesorFilterBar from "@/components/reports/AsesorFilterBar"
import DetalleAsesor from "@/components/reports/DetalleAsesor"
import ReportPagination from "@/components/reports/ReportPagination"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAsesorReport, useFilterOptions, useSellerOptions } from "@/hooks/useReports"
import useCursorPagination from "@/hooks/useCursorPagination"
import type { AsesorFilters, AsesorRow, AsesorSortColumn, AsesorSortDir } from "@/types"
import { cn, formatCurrency, formatInteger, formatPercentChange, getPercentChange } from "@/lib/utils"
import { TABLE_DISPLAY_GROUPS } from "@/components/reports/asesorCategories"
import { getDefaultAsesorFilters } from "@/lib/reportFilters"

const PAGE_SIZE = 8

export default function PorAsesor() {
    const [filters, setFilters] = useState<AsesorFilters>(getDefaultAsesorFilters())
    const [selectedRow, setSelectedRow] = useState<AsesorRow | null>(null)
    const [isExportingPdf, setIsExportingPdf] = useState(false)
    const [isExportingExcel, setIsExportingExcel] = useState(false)
    const [exportingExcelVariant, setExportingExcelVariant] = useState<"filtered" | "all" | null>(null)
    const [exportError, setExportError] = useState<string | null>(null)
    const [sortBy, setSortBy] = useState<AsesorSortColumn>("total_revenue")
    const [sortDir, setSortDir] = useState<AsesorSortDir>("desc")
    const { page, currentCursor, reset, goPrevious, goNext } = useCursorPagination<string>()

    const handleSort = (column: AsesorSortColumn) => {
        if (sortBy === column) {
            setSortDir((d) => (d === "desc" ? "asc" : "desc"))
        } else {
            setSortBy(column)
            setSortDir("desc")
        }
        reset()
    }

    const { data: filterOptions } = useFilterOptions()
    const { data: sellerOptionsResponse } = useSellerOptions()
    const sellerOptions = useMemo(() => sellerOptionsResponse?.sellers ?? [], [sellerOptionsResponse?.sellers])
    const normalizedFilters = useMemo(
        () => ({
            ...filters,
            sellers: (filters.sellers ?? []).filter((seller) => sellerOptions.includes(seller)),
        }),
        [filters, sellerOptions],
    )
    const requestFilters = useMemo(
        () => ({
            ...normalizedFilters,
            limit: PAGE_SIZE,
            cursor: currentCursor,
            sort_by: sortBy,
            sort_dir: sortDir,
        }),
        [currentCursor, normalizedFilters, sortBy, sortDir],
    )
    const { data, isLoading, isError } = useAsesorReport(requestFilters)
    const showComparisonValues = Boolean(filters.show_comparison && data?.comparison)
    const comparisonRowsBySeller = useMemo(
        () => new Map((data?.comparison?.data.rows ?? []).map((row) => [row.seller_id, row])),
        [data?.comparison?.data.rows],
    )

    const rows = data?.current.rows ?? []

    const handleExportExcel = async (variant: "filtered" | "all") => {
        setExportError(null)
        setIsExportingExcel(true)
        setExportingExcelVariant(variant)
        try {
            if (variant === "filtered") {
                await exportAsesorExcel(requestFilters)
            } else {
                await exportAsesorExcelAll({ ...normalizedFilters, sort_by: sortBy, sort_dir: sortDir })
            }
        } catch {
            setExportError("No fue posible exportar el archivo. Intenta de nuevo.")
        } finally {
            setIsExportingExcel(false)
            setExportingExcelVariant(null)
        }
    }

    const handleExportPdf = async () => {
        setExportError(null)
        setIsExportingPdf(true)
        try {
            await exportPorAsesorPdf({ ...normalizedFilters, sort_by: sortBy, sort_dir: sortDir })
        } catch {
            setExportError("No fue posible exportar el archivo. Intenta de nuevo.")
        } finally {
            setIsExportingPdf(false)
        }
    }

    return (
        <div className="flex flex-col gap-8 p-6">
            <AsesorFilterBar
                filters={normalizedFilters}
                options={filterOptions}
                sellerOptions={sellerOptions}
                onFiltersChange={(nextFilters) => {
                    reset()
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
                <CardHeader className="pb-6">
                    <CardTitle className="text-4xl font-semibold tracking-tight text-slate-900">
                        Resultados por Asesor
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    {isError && (
                        <div className="px-6 py-10 text-sm text-destructive">
                            Error al cargar los resultados por asesor.
                        </div>
                    )}

                    {isLoading ? (
                        <SummaryTableSkeleton />
                    ) : rows.length === 0 ? (
                        <div className="px-6 py-10 text-sm text-muted-foreground">
                            No hay resultados para los filtros seleccionados.
                        </div>
                    ) : (
                        <>
                            <div className="overflow-x-auto">
                                <Table className="min-w-max">
                                    <TableHeader>
                                        <TableRow className="hover:bg-transparent">
                                            <SortableTableHeadCell
                                                sortKey="seller_name"
                                                currentSortBy={sortBy}
                                                currentSortDir={sortDir}
                                                onSort={handleSort}
                                                className="sticky left-0 z-10 min-w-44 whitespace-nowrap bg-card text-left"
                                            >
                                                Asesor
                                            </SortableTableHeadCell>
                                            {TABLE_DISPLAY_GROUPS.map((group) => (
                                                <TableHeadCell
                                                    key={group.label}
                                                    className="min-w-28 whitespace-nowrap text-right"
                                                >
                                                    {group.label}
                                                </TableHeadCell>
                                            ))}
                                            <TableHeadCell className="min-w-24 whitespace-nowrap text-right">
                                                Libros
                                            </TableHeadCell>
                                            <TableHeadCell className="min-w-24 whitespace-nowrap text-right">
                                                Cursos
                                            </TableHeadCell>
                                            {showComparisonValues && (
                                                <>
                                                    <TableHeadCell className="min-w-28 whitespace-nowrap text-center">
                                                        Col. Ganados
                                                    </TableHeadCell>
                                                    <TableHeadCell className="min-w-28 whitespace-nowrap text-center">
                                                        Col. Perdidos
                                                    </TableHeadCell>
                                                    <TableHeadCell className="min-w-28 whitespace-nowrap text-center">
                                                        Col. Mantenidos
                                                    </TableHeadCell>
                                                    <TableHeadCell className="min-w-24 whitespace-nowrap text-center">
                                                        E. Ganados
                                                    </TableHeadCell>
                                                    <TableHeadCell className="min-w-24 whitespace-nowrap text-center">
                                                        E. Perdidos
                                                    </TableHeadCell>
                                                    <TableHeadCell className="min-w-28 whitespace-nowrap text-center">
                                                        E. Mantenidos
                                                    </TableHeadCell>
                                                    <TableHeadCell className="min-w-24 whitespace-nowrap text-center">
                                                        L+C Ganados
                                                    </TableHeadCell>
                                                    <TableHeadCell className="min-w-24 whitespace-nowrap text-center">
                                                        L+C Perdidos
                                                    </TableHeadCell>
                                                    <TableHeadCell className="min-w-28 whitespace-nowrap text-center">
                                                        L+C Mantenidos
                                                    </TableHeadCell>
                                                </>
                                            )}
                                            <TableHeadCell className="min-w-36 whitespace-nowrap text-right">
                                                Sin Categorizar
                                            </TableHeadCell>
                                            <SortableTableHeadCell
                                                sortKey="total_revenue"
                                                currentSortBy={sortBy}
                                                currentSortDir={sortDir}
                                                onSort={handleSort}
                                                className="min-w-36 whitespace-nowrap text-right"
                                            >
                                                Valor Total
                                            </SortableTableHeadCell>
                                            <SortableTableHeadCell
                                                sortKey="allocated_revenue"
                                                currentSortBy={sortBy}
                                                currentSortDir={sortDir}
                                                onSort={handleSort}
                                                className="min-w-36 whitespace-nowrap text-right"
                                            >
                                                Ing. Asignado
                                            </SortableTableHeadCell>
                                            <SortableTableHeadCell
                                                sortKey="expected_revenue"
                                                currentSortBy={sortBy}
                                                currentSortDir={sortDir}
                                                onSort={handleSort}
                                                className="min-w-36 whitespace-nowrap text-right"
                                            >
                                                Ing. Esperado
                                            </SortableTableHeadCell>
                                            <SortableTableHeadCell
                                                sortKey="expected_cost"
                                                currentSortBy={sortBy}
                                                currentSortDir={sortDir}
                                                onSort={handleSort}
                                                className="min-w-32 whitespace-nowrap text-right"
                                            >
                                                Costo Esperado
                                            </SortableTableHeadCell>
                                            <SortableTableHeadCell
                                                sortKey="profit_margin"
                                                currentSortBy={sortBy}
                                                currentSortDir={sortDir}
                                                onSort={handleSort}
                                                className="min-w-24 whitespace-nowrap text-right"
                                            >
                                                Margen
                                            </SortableTableHeadCell>
                                            <TableHeadCell className="w-10" />
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {rows.map((row) => {
                                            const previousRow = comparisonRowsBySeller.get(row.seller_id)

                                            return (
                                                <TableRow
                                                    key={row.seller_id}
                                                    tabIndex={0}
                                                    role="button"
                                                    onClick={() => setSelectedRow(row)}
                                                    onKeyDown={(event) => {
                                                        if (event.key === "Enter" || event.key === " ") {
                                                            event.preventDefault()
                                                            setSelectedRow(row)
                                                        }
                                                    }}
                                                    className="group cursor-pointer outline-none focus-visible:bg-muted/30"
                                                >
                                                    <TableBodyCell className="sticky left-0 z-10 bg-card font-semibold text-slate-900 group-hover:bg-muted/30 group-focus-visible:bg-muted/30">
                                                        {row.seller_name}
                                                    </TableBodyCell>
                                                    {TABLE_DISPLAY_GROUPS.map((group) => {
                                                        const value = group.categories.reduce(
                                                            (sum, cat) => sum + (row.exam_breakdown[cat] ?? 0),
                                                            0,
                                                        )
                                                        const previousValue = previousRow
                                                            ? group.categories.reduce(
                                                                  (sum, cat) =>
                                                                      sum + (previousRow.exam_breakdown[cat] ?? 0),
                                                                  0,
                                                              )
                                                            : undefined
                                                        return (
                                                            <TableMetricCell
                                                                key={`${row.seller_id}-${group.label}`}
                                                                value={value}
                                                                previousValue={previousValue}
                                                                align="right"
                                                                showComparison={showComparisonValues}
                                                            />
                                                        )
                                                    })}
                                                    <TableMetricCell
                                                        key={`${row.seller_id}-libros`}
                                                        value={row.total_books}
                                                        previousValue={previousRow?.total_books}
                                                        align="right"
                                                        showComparison={showComparisonValues}
                                                    />
                                                    <TableMetricCell
                                                        key={`${row.seller_id}-cursos`}
                                                        value={row.total_courses}
                                                        previousValue={previousRow?.total_courses}
                                                        align="right"
                                                        showComparison={showComparisonValues}
                                                    />
                                                    {showComparisonValues && (
                                                        <>
                                                            <TableBadgeCell
                                                                value={row.ganados}
                                                                tone="success"
                                                                showComparison={false}
                                                            />
                                                            <TableBadgeCell
                                                                value={row.perdidos}
                                                                tone="danger"
                                                                showComparison={false}
                                                            />
                                                            <TableBadgeCell
                                                                value={row.mantenidos}
                                                                tone="info"
                                                                showComparison={false}
                                                            />
                                                            <TableBadgeCell
                                                                value={row.exams_ganados}
                                                                tone="success"
                                                                showComparison={false}
                                                            />
                                                            <TableBadgeCell
                                                                value={row.exams_perdidos}
                                                                tone="danger"
                                                                showComparison={false}
                                                            />
                                                            <TableBadgeCell
                                                                value={row.exams_mantenidos}
                                                                tone="info"
                                                                showComparison={false}
                                                            />
                                                            <TableBadgeCell
                                                                value={row.books_courses_ganados}
                                                                tone="success"
                                                                showComparison={false}
                                                            />
                                                            <TableBadgeCell
                                                                value={row.books_courses_perdidos}
                                                                tone="danger"
                                                                showComparison={false}
                                                            />
                                                            <TableBadgeCell
                                                                value={row.books_courses_mantenidos}
                                                                tone="info"
                                                                showComparison={false}
                                                            />
                                                        </>
                                                    )}
                                                    <TableMetricCell
                                                        value={row.uncategorized_revenue}
                                                        previousValue={previousRow?.uncategorized_revenue}
                                                        format={formatCurrency}
                                                        align="right"
                                                        showComparison={showComparisonValues}
                                                    />
                                                    <TableMetricCell
                                                        value={row.total_revenue}
                                                        previousValue={previousRow?.total_revenue}
                                                        format={formatCurrency}
                                                        align="right"
                                                        emphasize
                                                        showComparison={showComparisonValues}
                                                    />
                                                    <TableMetricCell
                                                        value={row.allocated_revenue}
                                                        previousValue={previousRow?.allocated_revenue}
                                                        format={formatCurrency}
                                                        align="right"
                                                        showComparison={showComparisonValues}
                                                    />
                                                    <TableMetricCell
                                                        value={row.expected_revenue}
                                                        previousValue={previousRow?.expected_revenue}
                                                        format={formatCurrency}
                                                        align="right"
                                                        showComparison={showComparisonValues}
                                                    />
                                                    <TableMetricCell
                                                        value={row.expected_cost}
                                                        previousValue={previousRow?.expected_cost}
                                                        format={formatCurrency}
                                                        align="right"
                                                        showComparison={showComparisonValues}
                                                    />
                                                    <TableMetricCell
                                                        value={row.profit_margin}
                                                        previousValue={previousRow?.profit_margin}
                                                        format={(v) => `${v.toFixed(1)}%`}
                                                        align="right"
                                                        showComparison={showComparisonValues}
                                                        useSubtraction
                                                    />
                                                    <TableBodyCell className="w-12 text-right text-slate-400">
                                                        <ChevronRight className="ml-auto size-5" />
                                                    </TableBodyCell>
                                                </TableRow>
                                            )
                                        })}
                                    </TableBody>
                                </Table>
                            </div>

                            <ReportPagination
                                page={page}
                                currentCount={rows.length}
                                hasMore={data?.current.has_more ?? false}
                                onPrevious={goPrevious}
                                onNext={() => goNext(data?.current.next_cursor)}
                            />
                        </>
                    )}
                </CardContent>
            </Card>

            <AsesorGlossaryNote />

            <DetalleAsesor
                open={selectedRow !== null}
                onOpenChange={(open) => {
                    if (!open) setSelectedRow(null)
                }}
                sellerId={selectedRow?.seller_id ?? null}
                sellerName={selectedRow?.seller_name}
                filters={normalizedFilters}
            />
        </div>
    )
}

function AsesorGlossaryNote() {
    const [open, setOpen] = useState(false)
    return (
        <div className="rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-500">
            <button
                onClick={() => setOpen((o) => !o)}
                className="flex w-full items-center justify-between px-5 py-4 font-semibold text-slate-600"
            >
                <span>Notas</span>
                {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            {open && (
                <div className="px-5 pb-4 space-y-1">
                    <p>
                        <span className="font-medium text-slate-700">Sin categorizar:</span> Diferencia entre el Valor
                        Total cobrado y el Ingreso Asignado a productos. En condiciones normales es cero — cada peso
                        cobrado queda distribuido entre los productos del carrito. Un valor distinto de cero indica un
                        problema de calidad en los datos fuente:
                    </p>
                    <ul className="list-disc list-inside space-y-1 pl-2">
                        <li>
                            <span className="font-medium text-slate-700">Positivo</span> (cobrado &gt; asignado): el
                            pago fue registrado en el sistema pero sus asignaciones por producto cayeron fuera del
                            período consultado. Ocurre cuando la fecha del pago y la fecha de sus asignaciones son
                            inconsistentes en la base de datos de QC — típicamente en pagos de Colombia donde la fecha
                            de pago no fue capturada correctamente.
                        </li>
                        <li>
                            <span className="font-medium text-slate-700">Negativo</span> (asignado &gt; cobrado): los
                            montos registrados por estudiante en la base de datos de QC superan el monto total del pago.
                            Indica un error de captura — se asignaron más recursos a estudiantes de los que realmente se
                            cobraron. Requiere corrección en la base de datos de QC.
                        </li>
                    </ul>
                    <p>
                        <span className="font-medium text-slate-700">Ingreso Asignado:</span> Suma de los pagos
                        recibidos que tienen detalle de producto en el sistema. Es un subconjunto del Valor Total — la
                        diferencia entre ambos es el ingreso sin categorizar.
                    </p>
                    <p>
                        <span className="font-medium text-slate-700">Ingreso Esperado:</span> Suma de los montos
                        facturados (independientemente de si se han cobrado). Refleja el valor contractual acordado con
                        los colegios. La diferencia entre el Ingreso Esperado y el Ingreso Asignado representa pagos
                        pendientes de cobro.
                    </p>
                    <p>
                        <span className="font-medium text-slate-700">Margen de Utilidad:</span> Calculado como (Ingreso
                        Asignado − Costo Esperado) / Ingreso Asignado × 100. Se calcula sobre el ingreso asignado (no el
                        total) porque el costo esperado solo cubre los productos con detalle de línea.
                    </p>
                </div>
            )}
        </div>
    )
}

function TableHeadCell({ className, children }: { className?: string; children?: React.ReactNode }) {
    return (
        <TableHead className={cn("px-3 py-3 text-xs font-semibold uppercase tracking-wide text-slate-700", className)}>
            {children}
        </TableHead>
    )
}

function SortableTableHeadCell({
    sortKey,
    currentSortBy,
    currentSortDir,
    onSort,
    className,
    children,
}: {
    sortKey: AsesorSortColumn
    currentSortBy: AsesorSortColumn
    currentSortDir: AsesorSortDir
    onSort: (key: AsesorSortColumn) => void
    className?: string
    children: React.ReactNode
}) {
    const isActive = currentSortBy === sortKey
    const Icon = isActive ? (currentSortDir === "desc" ? ChevronDown : ChevronUp) : ChevronsUpDown
    return (
        <TableHead
            className={cn(
                "cursor-pointer select-none px-3 py-3 text-xs font-semibold uppercase tracking-wide text-slate-700 hover:text-slate-900",
                className,
            )}
            onClick={() => onSort(sortKey)}
        >
            <span className="inline-flex items-center gap-1">
                {children}
                <Icon className={cn("size-3.5 shrink-0", isActive ? "text-slate-900" : "text-slate-400")} />
            </span>
        </TableHead>
    )
}

function TableBodyCell({ className, children }: { className?: string; children: React.ReactNode }) {
    return <TableCell className={cn("px-3 py-3 text-sm text-slate-700", className)}>{children}</TableCell>
}

function TableMetricCell({
    value,
    previousValue,
    format = formatInteger,
    align = "center",
    emphasize = false,
    showComparison,
    useSubtraction = false,
}: {
    value: number
    previousValue?: number
    format?: (value: number) => string
    align?: "left" | "center" | "right"
    emphasize?: boolean
    showComparison: boolean
    useSubtraction?: boolean
}) {
    const comparison = useSubtraction
        ? previousValue !== undefined && previousValue !== null
            ? value - previousValue
            : null
        : getPercentChange(value, previousValue)
    const alignmentClassName =
        align === "right"
            ? "items-end text-right"
            : align === "left"
              ? "items-start text-left"
              : "items-center text-center"

    return (
        <TableBodyCell>
            <div className={cn("flex flex-col gap-0.5", alignmentClassName)}>
                <span className={cn("text-sm tabular-nums", emphasize && "font-semibold text-slate-900")}>
                    {format(value)}
                </span>
                {showComparison && previousValue !== undefined && (
                    <span className="text-[10px] text-muted-foreground tabular-nums">{format(previousValue)}</span>
                )}
                {showComparison && <ComparisonText value={comparison} />}
            </div>
        </TableBodyCell>
    )
}

function TableBadgeCell({
    value,
    previousValue,
    tone,
    showComparison,
}: {
    value: number
    previousValue?: number
    tone: "success" | "danger" | "info"
    showComparison: boolean
}) {
    const comparison = getPercentChange(value, previousValue)
    const badgeVariant = tone === "success" ? "success" : tone === "danger" ? "danger" : "info"

    return (
        <TableBodyCell>
            <div className="flex flex-col items-center gap-2">
                <Badge variant={badgeVariant} className="min-w-10 px-2 py-0.5 text-xs font-semibold">
                    {formatInteger(value)}
                </Badge>
                {showComparison && <ComparisonText value={comparison} center />}
            </div>
        </TableBodyCell>
    )
}

function SummaryTableSkeleton() {
    return (
        <div className="space-y-4 px-6 py-6">
            <div className="grid grid-cols-8 gap-4">
                {Array.from({ length: 8 }).map((_, index) => (
                    <Skeleton key={index} className="h-5 w-full" />
                ))}
            </div>
            {Array.from({ length: 6 }).map((_, rowIndex) => (
                <div key={rowIndex} className="grid grid-cols-8 gap-4 border-t border-border pt-4">
                    {Array.from({ length: 8 }).map((_, colIndex) => (
                        <Skeleton key={colIndex} className="h-8 w-full" />
                    ))}
                </div>
            ))}
        </div>
    )
}

function ComparisonText({ value, center = false }: { value: number | null; center?: boolean }) {
    if (value === null) {
        return null
    }

    return (
        <span
            className={cn(
                "text-xs font-medium",
                value >= 0 ? "text-emerald-600" : "text-rose-600",
                center && "text-center",
            )}
        >
            {formatPercentChange(value)}
        </span>
    )
}
