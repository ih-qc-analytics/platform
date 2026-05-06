import { useMemo, useState } from "react"
import { ChevronRight } from "lucide-react"

import PorPaisDetail from "@/components/reports/PorPaisDetail"
import PorPaisFilterBar from "@/components/reports/PorPaisFilterBar"
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
import { usePorPaisReport } from "@/hooks/useReports"
import { cn, formatInteger } from "@/lib/utils"
import type { PorPaisFilters, PorPaisStatusRow, PorPaisSummaryRow } from "@/types"

export default function PorPais() {
    const currentYear = new Date().getFullYear()
    const [filters, setFilters] = useState<PorPaisFilters>({
        date_from: `${currentYear}-01-01`,
        date_to: `${currentYear}-12-31`,
    })
    const [selectedCountry, setSelectedCountry] = useState<string | null>(null)
    const requestFilters = useMemo(() => filters, [filters])
    const { data, isLoading, isError } = usePorPaisReport(requestFilters)

    const summaryRows = data?.summary_rows ?? []
    const statusRows = data?.status_rows ?? []

    return (
        <div className="flex flex-col gap-8 p-6">
            <PorPaisFilterBar
                filters={filters}
                onChange={setFilters}
                onExportPdf={() => console.log("export pdf")}
                onExportExcel={() => console.log("export excel")}
            />

            <Card className="rounded-[2rem] shadow-sm">
                <CardHeader className="pb-2">
                    <CardTitle className="text-4xl font-semibold tracking-tight text-slate-900">
                        Resultado por País
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                        Resumen por país y detalle por familia de exámenes.
                    </p>
                </CardHeader>
                <CardContent className="p-0">
                    {isError && (
                        <div className="px-6 py-10 text-sm text-destructive">
                            Error al cargar el resultado por país.
                        </div>
                    )}

                    {isLoading ? (
                        <PorPaisTableSkeleton columns={8} />
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
                                        <TableHeadCell className="min-w-24 text-right">Cambridge</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">IELTS</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">MET</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">TEA</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-right">Otros</TableHeadCell>
                                        <TableHeadCell className="w-10" />
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {summaryRows.map(row => (
                                        <ClickableCountryRow
                                            key={row.country}
                                            row={row}
                                            onSelect={() => setSelectedCountry(row.country)}
                                        />
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card className="rounded-[2rem] shadow-sm">
                <CardHeader className="pb-2">
                    <CardTitle className="text-2xl font-semibold tracking-tight text-slate-900">
                        Ganados, Perdidos y Mantenidos
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
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
                                        <TableHeadCell className="min-w-24 text-center">Colegios Ganados</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-center">Colegios Perdidos</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-center">Colegios Mantenidos</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-center">Exámenes Ganados</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-center">Exámenes Perdidos</TableHeadCell>
                                        <TableHeadCell className="min-w-24 text-center">Exámenes Mantenidos</TableHeadCell>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {statusRows.map(row => (
                                        <StatusRowView key={row.country} row={row} />
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </CardContent>
            </Card>

            <PorPaisDetail
                country={selectedCountry}
                open={selectedCountry !== null}
                onOpenChange={open => {
                    if (!open) setSelectedCountry(null)
                }}
                filters={filters}
            />
        </div>
    )
}

function ClickableCountryRow({
    row,
    onSelect,
}: {
    row: PorPaisSummaryRow
    onSelect: () => void
}) {
    return (
        <TableRow
            tabIndex={0}
            role="button"
            onClick={onSelect}
            onKeyDown={event => {
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
            <MetricCell value={row.total_schools} align="right" />
            <MetricCell value={row.cambridge} align="right" />
            <MetricCell value={row.ielts} align="right" />
            <MetricCell value={row.michigan} align="right" />
            <MetricCell value={row.tea} align="right" />
            <MetricCell value={row.other} align="right" />
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
            <MetricCell value={row.schools_ganados} />
            <MetricCell value={row.schools_perdidos} />
            <MetricCell value={row.schools_mantenidos} />
            <MetricCell value={row.exams_ganados} />
            <MetricCell value={row.exams_perdidos} />
            <MetricCell value={row.exams_mantenidos} />
        </TableRow>
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

function MetricCell({
    value,
    align = "center",
}: {
    value: number
    align?: "center" | "right"
}) {
    return (
        <TableBodyCell className={align === "right" ? "text-right" : "text-center"}>
            <span className="tabular-nums">{formatInteger(value)}</span>
        </TableBodyCell>
    )
}

function PorPaisTableSkeleton({ columns }: { columns: number }) {
    return (
        <div className="space-y-4 px-6 py-6">
            <div
                className="grid gap-4"
                style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
            >
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
