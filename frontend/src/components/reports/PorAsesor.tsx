import { useEffect, useMemo, useState } from "react"
import { ChevronRight } from "lucide-react"

import AsesorFilterBar from "@/components/reports/AsesorFilterBar"
import DetalleAsesor from "@/components/reports/DetalleAsesor"
import ReportPagination from "@/components/reports/ReportPagination"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { useAsesorReport, useFilterOptions, useSellerOptions } from "@/hooks/useReports"
import type { AsesorFilters, AsesorRow } from "@/types"
import { cn, formatCurrency, formatInteger, formatPercentChange, getPercentChange } from "@/lib/utils"

const PAGE_SIZE = 8

export default function PorAsesor() {
    const currentYear = new Date().getFullYear()
    const yearOptions = [currentYear - 2, currentYear - 1, currentYear]

    const [filters, setFilters] = useState<AsesorFilters>({
        year: currentYear,
        countries: [],
        zones: [],
        states: [],
        cities: [],
        sellers: [],
    })
    const [showComparison, setShowComparison] = useState(false)
    const [page, setPage] = useState(0)
    const [pageCursors, setPageCursors] = useState<Array<string | null>>([null])
    const [selectedRow, setSelectedRow] = useState<AsesorRow | null>(null)
    const currentCursor = pageCursors[page] ?? null

    const { data: filterOptions } = useFilterOptions()
    const { data: sellerOptionsResponse } = useSellerOptions()
    const requestFilters = useMemo(
        () => ({
            ...filters,
            limit: PAGE_SIZE,
            cursor: currentCursor,
        }),
        [currentCursor, filters],
    )
    const { data, isLoading, isError } = useAsesorReport(requestFilters)
    const visibleSellerNames = useMemo(
        () => (data?.rows ?? []).map(row => row.seller_name),
        [data?.rows],
    )
    const { data: comparisonData } = useAsesorReport(
        {
            ...filters,
            year: filters.year - 1,
            sellers: visibleSellerNames,
            limit: PAGE_SIZE,
            cursor: null,
        },
        showComparison && filters.year > 0 && visibleSellerNames.length > 0,
    )

    const sellerOptions = sellerOptionsResponse?.sellers ?? []

    useEffect(() => {
        if (filters.sellers?.[0] && !sellerOptions.includes(filters.sellers[0])) {
            setFilters(current => ({ ...current, sellers: [] }))
        }
    }, [filters.sellers, sellerOptions])

    useEffect(() => {
        setPage(0)
        setPageCursors([null])
    }, [filters, showComparison])

    const comparisonRowsBySeller = useMemo(
        () => new Map((comparisonData?.rows ?? []).map(row => [row.seller_id, row])),
        [comparisonData?.rows],
    )

    const examColumns = useMemo(() => {
        const totals = new Map<string, number>()
        for (const row of data?.rows ?? []) {
            for (const [label, value] of Object.entries(row.exam_breakdown)) {
                totals.set(label, (totals.get(label) ?? 0) + value)
            }
        }
        for (const row of comparisonData?.rows ?? []) {
            for (const [label, value] of Object.entries(row.exam_breakdown)) {
                totals.set(label, (totals.get(label) ?? 0) + value)
            }
        }
        return [...totals.entries()]
            .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
            .map(([label]) => label)
    }, [comparisonData?.rows, data?.rows])

    const rows = data?.rows ?? []

    return (
        <div className="flex flex-col gap-8 p-6">
            <AsesorFilterBar
                filters={filters}
                options={filterOptions}
                sellerOptions={sellerOptions}
                yearOptions={yearOptions}
                showComparison={showComparison}
                onFiltersChange={setFilters}
                onToggleComparison={setShowComparison}
                onExportPdf={() => console.log("export pdf")}
                onExportExcel={() => console.log("export excel")}
            />

            <Card className="rounded-[2rem] shadow-sm">
                <CardHeader className="pb-2">
                    <CardTitle className="text-4xl font-semibold tracking-tight text-slate-900">
                        Resultados por Asesor - {filters.year}
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
                        <div className="px-6 py-10 text-sm text-muted-foreground">No hay resultados para los filtros seleccionados.</div>
                    ) : (
                        <>
                            <Table className="min-w-full">
                                    <TableHeader>
                                        <TableRow className="hover:bg-transparent">
                                            <TableHeadCell className="sticky left-0 z-10 min-w-60 bg-card text-left">
                                                Asesor
                                            </TableHeadCell>
                                            {examColumns.map(label => (
                                                <TableHeadCell key={label} className="min-w-32 text-right">
                                                    {label}
                                                </TableHeadCell>
                                            ))}
                                            <TableHeadCell className="min-w-28 text-center">Ganados</TableHeadCell>
                                            <TableHeadCell className="min-w-28 text-center">Perdidos</TableHeadCell>
                                            <TableHeadCell className="min-w-32 text-center">Mantenidos</TableHeadCell>
                                            <TableHeadCell className="min-w-40 text-right">Valor Total</TableHeadCell>
                                            <TableHeadCell className="w-12" />
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {rows.map(row => {
                                            const previousRow = comparisonRowsBySeller.get(row.seller_id)

                                            return (
                                                <TableRow
                                                    key={row.seller_id}
                                                    tabIndex={0}
                                                    role="button"
                                                    onClick={() => setSelectedRow(row)}
                                                    onKeyDown={event => {
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
                                                    {examColumns.map(label => (
                                                        <TableMetricCell
                                                            key={`${row.seller_id}-${label}`}
                                                            value={row.exam_breakdown[label] ?? 0}
                                                            previousValue={previousRow?.exam_breakdown[label]}
                                                            align="right"
                                                            showComparison={showComparison}
                                                        />
                                                    ))}
                                                    <TableBadgeCell
                                                        value={row.ganados}
                                                        previousValue={previousRow?.ganados}
                                                        tone="success"
                                                        showComparison={showComparison}
                                                    />
                                                    <TableBadgeCell
                                                        value={row.perdidos}
                                                        previousValue={previousRow?.perdidos}
                                                        tone="danger"
                                                        showComparison={showComparison}
                                                    />
                                                    <TableBadgeCell
                                                        value={row.mantenidos}
                                                        previousValue={previousRow?.mantenidos}
                                                        tone="info"
                                                        showComparison={showComparison}
                                                    />
                                                    <TableMetricCell
                                                        value={row.total_revenue}
                                                        previousValue={previousRow?.total_revenue}
                                                        format={formatCurrency}
                                                        align="right"
                                                        emphasize
                                                        showComparison={showComparison}
                                                    />
                                                    <TableBodyCell className="w-12 text-right text-slate-400">
                                                        <ChevronRight className="ml-auto size-5" />
                                                    </TableBodyCell>
                                                </TableRow>
                                            )
                                        })}
                                    </TableBody>
                            </Table>

                            <ReportPagination
                                page={page}
                                currentCount={rows.length}
                                hasMore={data?.has_more ?? false}
                                onPrevious={() => setPage(current => Math.max(0, current - 1))}
                                onNext={() => {
                                    if (!data?.has_more || !data.next_cursor) return
                                    setPageCursors(current => {
                                        if (current[page + 1] === data.next_cursor) return current
                                        const next = current.slice(0, page + 1)
                                        next.push(data.next_cursor)
                                        return next
                                    })
                                    setPage(current => current + 1)
                                }}
                            />
                        </>
                    )}
                </CardContent>
            </Card>

            <DetalleAsesor
                open={selectedRow !== null}
                onOpenChange={open => {
                    if (!open) setSelectedRow(null)
                }}
                sellerId={selectedRow?.seller_id ?? null}
                sellerName={selectedRow?.seller_name}
                filters={filters}
            />
        </div>
    )
}

function TableHeadCell({
    className,
    children,
}: {
    className?: string
    children?: React.ReactNode
}) {
    return (
        <TableHead className={cn("px-6 py-5 text-sm font-semibold uppercase tracking-wide text-slate-700", className)}>
            {children}
        </TableHead>
    )
}

function TableBodyCell({
    className,
    children,
}: {
    className?: string
    children: React.ReactNode
}) {
    return <TableCell className={cn("px-6 py-5 text-base text-slate-700", className)}>{children}</TableCell>
}

function TableMetricCell({
    value,
    previousValue,
    format = formatInteger,
    align = "center",
    emphasize = false,
    showComparison,
}: {
    value: number
    previousValue?: number
    format?: (value: number) => string
    align?: "left" | "center" | "right"
    emphasize?: boolean
    showComparison: boolean
}) {
    const comparison = getPercentChange(value, previousValue)
    const alignmentClassName =
        align === "right" ? "items-end text-right" : align === "left" ? "items-start text-left" : "items-center text-center"

    return (
        <TableBodyCell>
            <div className={cn("flex flex-col gap-1", alignmentClassName)}>
                <span className={cn("text-2xl", emphasize && "font-semibold text-slate-900")}>{format(value)}</span>
                {showComparison && (
                    <ComparisonText value={comparison} />
                )}
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
    const badgeVariant =
        tone === "success"
            ? "success"
            : tone === "danger"
              ? "danger"
              : "info"

    return (
        <TableBodyCell>
            <div className="flex flex-col items-center gap-2">
                <Badge variant={badgeVariant} className="min-w-12 px-3 py-1 text-xl font-semibold">
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
            <div className="grid grid-cols-6 gap-4">
                {Array.from({ length: 6 }).map((_, index) => (
                    <Skeleton key={index} className="h-5 w-full" />
                ))}
            </div>
            {Array.from({ length: 6 }).map((_, rowIndex) => (
                <div key={rowIndex} className="grid grid-cols-6 gap-4 border-t border-border pt-4">
                    {Array.from({ length: 6 }).map((_, colIndex) => (
                        <Skeleton key={colIndex} className="h-8 w-full" />
                    ))}
                </div>
            ))}
        </div>
    )
}

function ComparisonText({ value, center = false }: { value: number | null; center?: boolean }) {
    if (value === null) {
        return (
            <span className={cn("text-xs text-muted-foreground", center && "text-center")}>
                Sin base
            </span>
        )
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
