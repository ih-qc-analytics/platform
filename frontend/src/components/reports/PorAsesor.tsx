import { useMemo, useState } from "react"
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
import useCursorPagination from "@/hooks/useCursorPagination"
import type { AsesorFilters, AsesorRow } from "@/types"
import { cn, formatCurrency, formatInteger, formatPercentChange, getPercentChange } from "@/lib/utils"
import { TABLE_DISPLAY_GROUPS } from "@/components/reports/asesorCategories"

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
    const [selectedRow, setSelectedRow] = useState<AsesorRow | null>(null)
    const { page, currentCursor, reset, goPrevious, goNext } = useCursorPagination<string>()

    const { data: filterOptions } = useFilterOptions()
    const { data: sellerOptionsResponse } = useSellerOptions()
    const sellerOptions = useMemo(() => sellerOptionsResponse?.sellers ?? [], [sellerOptionsResponse?.sellers])
    const normalizedFilters = useMemo(
        () =>
            filters.sellers?.[0] && !sellerOptions.includes(filters.sellers[0])
                ? { ...filters, sellers: [] }
                : filters,
        [filters, sellerOptions],
    )
    const requestFilters = useMemo(
        () => ({
            ...normalizedFilters,
            limit: PAGE_SIZE,
            cursor: currentCursor,
        }),
        [currentCursor, normalizedFilters],
    )
    const { data, isLoading, isError } = useAsesorReport(requestFilters)
    const visibleSellerNames = useMemo(
        () => (data?.rows ?? []).map(row => row.seller_name),
        [data?.rows],
    )
    const { data: comparisonData } = useAsesorReport(
        {
            ...normalizedFilters,
            year: normalizedFilters.year - 1,
            sellers: visibleSellerNames,
            limit: PAGE_SIZE,
            cursor: null,
        },
        showComparison && normalizedFilters.year > 0 && visibleSellerNames.length > 0,
    )

    const comparisonRowsBySeller = useMemo(
        () => new Map((comparisonData?.rows ?? []).map(row => [row.seller_id, row])),
        [comparisonData?.rows],
    )

    const rows = data?.rows ?? []

    return (
        <div className="flex flex-col gap-8 p-6">
            <AsesorFilterBar
                filters={normalizedFilters}
                options={filterOptions}
                sellerOptions={sellerOptions}
                yearOptions={yearOptions}
                showComparison={showComparison}
                onFiltersChange={nextFilters => {
                    reset()
                    setFilters(nextFilters)
                }}
                onToggleComparison={value => {
                    reset()
                    setShowComparison(value)
                }}
                onExportPdf={() => console.log("export pdf")}
                onExportExcel={() => console.log("export excel")}
            />

            <Card className="rounded-[2rem] shadow-sm">
                <CardHeader className="pb-2">
                    <CardTitle className="text-4xl font-semibold tracking-tight text-slate-900">
                        Resultados por Asesor - {normalizedFilters.year}
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
                            <div className="overflow-x-auto">
                                <Table className="min-w-max">
                                    <TableHeader>
                                        <TableRow className="hover:bg-transparent">
                                            <TableHeadCell className="sticky left-0 z-10 min-w-44 whitespace-nowrap bg-card text-left">
                                                Asesor
                                            </TableHeadCell>
                                            {TABLE_DISPLAY_GROUPS.map(group => (
                                                <TableHeadCell key={group.label} className="min-w-28 whitespace-nowrap text-right">
                                                    {group.label}
                                                </TableHeadCell>
                                            ))}
                                            <TableHeadCell className="min-w-24 whitespace-nowrap text-center">Ganados</TableHeadCell>
                                            <TableHeadCell className="min-w-24 whitespace-nowrap text-center">Perdidos</TableHeadCell>
                                            <TableHeadCell className="min-w-28 whitespace-nowrap text-center">Mantenidos</TableHeadCell>
                                            <TableHeadCell className="min-w-36 whitespace-nowrap text-right">Valor Total</TableHeadCell>
                                            <TableHeadCell className="w-10" />
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
                                                    {TABLE_DISPLAY_GROUPS.map(group => {
                                                        const value = group.categories.reduce(
                                                            (sum, cat) => sum + (row.exam_breakdown[cat] ?? 0),
                                                            0,
                                                        )
                                                        const previousValue = previousRow
                                                            ? group.categories.reduce(
                                                                  (sum, cat) => sum + (previousRow.exam_breakdown[cat] ?? 0),
                                                                  0,
                                                              )
                                                            : undefined
                                                        return (
                                                            <TableMetricCell
                                                                key={`${row.seller_id}-${group.label}`}
                                                                value={value}
                                                                previousValue={previousValue}
                                                                align="right"
                                                                showComparison={showComparison}
                                                            />
                                                        )
                                                    })}
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
                            </div>

                            <ReportPagination
                                page={page}
                                currentCount={rows.length}
                                hasMore={data?.has_more ?? false}
                                onPrevious={goPrevious}
                                onNext={() => goNext(data?.next_cursor)}
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
                filters={normalizedFilters}
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
        <TableHead className={cn("px-3 py-3 text-xs font-semibold uppercase tracking-wide text-slate-700", className)}>
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
    return <TableCell className={cn("px-3 py-3 text-sm text-slate-700", className)}>{children}</TableCell>
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
                <span className={cn("text-sm", emphasize && "font-semibold text-slate-900")}>{format(value)}</span>
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
