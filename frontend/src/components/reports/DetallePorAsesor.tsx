import { useEffect, useMemo, useState } from "react"
import { Search } from "lucide-react"

import { exportDetalleAsesorExcel, exportDetalleAsesorExcelAll, exportDetalleAsesorPdf } from "@/api/reports"
import FilterBar from "@/components/filters/FilterBar"
import { DETALLE_ASESOR_EXAM_TYPES, EXAM_TYPE_LABELS } from "@/components/constants/detalleAsesorExamTypes"
import ReportPagination from "@/components/reports/ReportPagination"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import useCursorPagination from "@/hooks/useCursorPagination"
import { useDetalleAsesorReport } from "@/hooks/useReports"
import { getDefaultReportFilters } from "@/lib/reportFilters"
import { cn, formatInteger } from "@/lib/utils"
import type { DetalleAsesorFilters, ReportFilters } from "@/types"

const PAGE_SIZE = 8

export default function DetallePorAsesor() {
    const [filters, setFilters] = useState<ReportFilters>(getDefaultReportFilters())
    const [searchInput, setSearchInput] = useState("")
    const [search, setSearch] = useState("")
    const [isExportingPdf, setIsExportingPdf] = useState(false)
    const [isExportingExcel, setIsExportingExcel] = useState(false)
    const [exportingExcelVariant, setExportingExcelVariant] = useState<"filtered" | "all" | null>(null)
    const [exportError, setExportError] = useState<string | null>(null)
    const { page, currentCursor, reset, goPrevious, goNext } = useCursorPagination<number>()

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            reset()
            setSearch(searchInput.trim())
        }, 300)

        return () => window.clearTimeout(timeoutId)
    }, [reset, searchInput])

    const requestFilters = useMemo<DetalleAsesorFilters>(
        () => ({
            ...filters,
            search: search || undefined,
            cursor: currentCursor,
            page_size: PAGE_SIZE,
        }),
        [currentCursor, filters, search],
    )

    const { data, isLoading, isError } = useDetalleAsesorReport(requestFilters)
    const rows = data?.current.rows ?? []

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
                await exportDetalleAsesorExcel(requestFilters)
            } else {
                await exportDetalleAsesorExcelAll({
                    ...filters,
                    search: search || undefined,
                })
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
            await exportDetalleAsesorPdf({ ...filters, search: search || undefined })
        } catch {
            setExportError("No fue posible exportar el archivo. Intenta de nuevo.")
        } finally {
            setIsExportingPdf(false)
        }
    }

    return (
        <div className="flex flex-col gap-8 p-6">
            <FilterBar
                hideComparison
                value={filters}
                onChange={nextFilters => {
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

            <div className="max-w-xl">
                <label htmlFor="detalle-asesor-search" className="mb-2 block text-sm font-medium text-slate-700">
                    Buscar asesor o escuela
                </label>
                <div className="relative">
                    <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        id="detalle-asesor-search"
                        value={searchInput}
                        onChange={event => setSearchInput(event.target.value)}
                        placeholder="Escribe un nombre de asesor o escuela"
                        className="h-14 rounded-2xl border-border bg-card pl-11 pr-4 text-sm shadow-sm"
                    />
                </div>
            </div>

            <Card className="rounded-[2rem] shadow-sm">
                <CardHeader className="flex flex-col gap-3 pb-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-1">
                        <CardTitle className="text-4xl font-semibold tracking-tight text-slate-900">
                            Detalle por Asesor
                        </CardTitle>
                        <p className="text-sm text-muted-foreground">
                            Desglose por asesor, escuela y fecha de examen.
                        </p>
                    </div>
                    <p className="text-sm font-medium text-slate-500">
                        {rows.length} registros encontrados
                    </p>
                </CardHeader>
                <CardContent className="p-0">
                    {isError && (
                        <div className="px-6 py-10 text-sm text-destructive">
                            Error al cargar el detalle por asesor.
                        </div>
                    )}

                    {isLoading ? (
                        <DetalleTableSkeleton />
                    ) : rows.length === 0 ? (
                        <div className="px-6 py-10 text-sm text-muted-foreground">
                            No hay resultados para los filtros seleccionados.
                        </div>
                    ) : (
                        <>
                            <div className="overflow-x-auto">
                                <Table className="w-full">
                                    <TableHeader>
                                        <TableRow className="hover:bg-transparent">
                                            <DetalleHeadCell className="text-left">Asesor</DetalleHeadCell>
                                            <DetalleHeadCell className="text-left">Escuela</DetalleHeadCell>
                                            <DetalleHeadCell className="text-left">Fecha</DetalleHeadCell>
                                            {EXAM_TYPE_LABELS.map(examType => (
                                                <DetalleHeadCell key={examType} className="text-center">
                                                    {examType}
                                                </DetalleHeadCell>
                                            ))}
                                            <DetalleHeadCell className="text-center">Total</DetalleHeadCell>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {rows.map(row => (
                                            <TableRow key={row.id}>
                                                <DetalleBodyCell className="font-semibold text-slate-900">
                                                    {row.seller_name}
                                                </DetalleBodyCell>
                                                <DetalleBodyCell>{row.school_name}</DetalleBodyCell>
                                                <DetalleBodyCell>{formatExamDate(row.exam_date)}</DetalleBodyCell>
                                                {DETALLE_ASESOR_EXAM_TYPES.map(examType => (
                                                    <DetalleBodyCell key={`${row.id}-${examType}`} className="text-center tabular-nums">
                                                        {formatInteger(row.exam_counts[examType] ?? 0)}
                                                    </DetalleBodyCell>
                                                ))}
                                                <DetalleBodyCell className="text-center font-semibold text-slate-900 tabular-nums">
                                                    {formatInteger(row.total)}
                                                </DetalleBodyCell>
                                            </TableRow>
                                        ))}
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
        </div>
    )
}

function DetalleHeadCell({
    className,
    children,
}: {
    className?: string
    children: React.ReactNode
}) {
    return (
        <TableHead
            className={cn(
                "px-2 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-700 whitespace-normal break-words align-bottom",
                className,
            )}
        >
            {children}
        </TableHead>
    )
}

function DetalleBodyCell({
    className,
    children,
}: {
    className?: string
    children: React.ReactNode
}) {
    return (
        <TableCell className={cn("px-2 py-2 text-xs leading-tight text-slate-700 whitespace-normal break-words", className)}>
            {children}
        </TableCell>
    )
}

function DetalleTableSkeleton() {
    const columnCount = 4 + DETALLE_ASESOR_EXAM_TYPES.length

    return (
        <div className="space-y-4 px-6 py-6">
            <div
                className="grid gap-3"
                style={{ gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))` }}
            >
                {Array.from({ length: columnCount }).map((_, index) => (
                    <Skeleton key={index} className="h-5 w-full" />
                ))}
            </div>
            {Array.from({ length: 6 }).map((_, rowIndex) => (
                <div
                    key={rowIndex}
                    className="grid gap-3 border-t border-border pt-4"
                    style={{ gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))` }}
                >
                    {Array.from({ length: columnCount }).map((_, colIndex) => (
                        <Skeleton key={colIndex} className="h-8 w-full" />
                    ))}
                </div>
            ))}
        </div>
    )
}

function formatExamDate(value: string) {
    if (!value) return "-"

    const parsed = new Date(`${value}T12:00:00`)
    if (Number.isNaN(parsed.getTime())) return value

    return new Intl.DateTimeFormat("es-MX", {
        day: "numeric",
        month: "short",
        year: "numeric",
    }).format(parsed)
}
