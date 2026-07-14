import { useMemo, useState } from "react"
import { FileDown, Loader2 } from "lucide-react"

import { exportPorPaisDetailPdf } from "@/api/reports"
import { DETALLE_ASESOR_EXAM_TYPES } from "@/components/reports/detalleAsesorExamTypes"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { usePorPaisDetail } from "@/hooks/useReports"
import { cn, formatCurrency, formatInteger, formatPercentChange, getPercentChange } from "@/lib/utils"
import type { PorPaisFilters } from "@/types"

type PorPaisDetailProps = {
    country: string | null
    open: boolean
    onOpenChange: (open: boolean) => void
    filters: PorPaisFilters
}

const FAMILY_EXAM_TYPES = {
    Cambridge: DETALLE_ASESOR_EXAM_TYPES.filter((name) => !["IELTS", "MET", "MET Go!", "TEA", "Otros"].includes(name)),
    IELTS: ["IELTS"],
    MET: ["MET", "MET Go!"],
    TEA: ["TEA"],
    Otros: ["Otros"],
    Total: DETALLE_ASESOR_EXAM_TYPES,
} as const

export default function PorPaisDetail({ country, open, onOpenChange, filters }: PorPaisDetailProps) {
    const [isExportingPdf, setIsExportingPdf] = useState(false)
    const [exportError, setExportError] = useState<string | null>(null)
    const { data, isLoading, isError } = usePorPaisDetail(country, filters, open)

    const showComparison = Boolean(filters.show_comparison && data?.comparison_exam_counts)

    const categoryTiles = useMemo(
        () => [
            {
                title: "Cambridge",
                value: FAMILY_EXAM_TYPES.Cambridge.reduce(
                    (sum, examType) => sum + (data?.exam_counts[examType] ?? 0),
                    0,
                ),
                comparisonValue: FAMILY_EXAM_TYPES.Cambridge.reduce(
                    (sum, examType) => sum + (data?.comparison_exam_counts?.[examType] ?? 0),
                    0,
                ),
            },
            {
                title: "IELTS",
                value: FAMILY_EXAM_TYPES.IELTS.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
                comparisonValue: FAMILY_EXAM_TYPES.IELTS.reduce(
                    (sum, examType) => sum + (data?.comparison_exam_counts?.[examType] ?? 0),
                    0,
                ),
            },
            {
                title: "MET",
                value: FAMILY_EXAM_TYPES.MET.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
                comparisonValue: FAMILY_EXAM_TYPES.MET.reduce(
                    (sum, examType) => sum + (data?.comparison_exam_counts?.[examType] ?? 0),
                    0,
                ),
            },
            {
                title: "TEA",
                value: FAMILY_EXAM_TYPES.TEA.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
                comparisonValue: FAMILY_EXAM_TYPES.TEA.reduce(
                    (sum, examType) => sum + (data?.comparison_exam_counts?.[examType] ?? 0),
                    0,
                ),
            },
            {
                title: "Otros",
                value: FAMILY_EXAM_TYPES.Otros.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
                comparisonValue: FAMILY_EXAM_TYPES.Otros.reduce(
                    (sum, examType) => sum + (data?.comparison_exam_counts?.[examType] ?? 0),
                    0,
                ),
            },
            {
                title: "Total",
                value: FAMILY_EXAM_TYPES.Total.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
                comparisonValue: FAMILY_EXAM_TYPES.Total.reduce(
                    (sum, examType) => sum + (data?.comparison_exam_counts?.[examType] ?? 0),
                    0,
                ),
            },
        ],
        [data?.exam_counts, data?.comparison_exam_counts],
    )

    const handleExportPdf = async () => {
        if (!country) return

        setExportError(null)
        setIsExportingPdf(true)
        try {
            await exportPorPaisDetailPdf(country, filters)
        } catch {
            setExportError("No fue posible exportar el archivo. Intenta de nuevo.")
        } finally {
            setIsExportingPdf(false)
        }
    }

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" className="w-full overflow-y-auto p-0 sm:max-w-3xl">
                <SheetHeader className="border-b border-border px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                        <SheetTitle className="text-2xl font-semibold tracking-tight text-slate-900">
                            {data?.country ?? country ?? "Detalle"}
                        </SheetTitle>
                        <Button
                            onClick={() => void handleExportPdf()}
                            variant="outline"
                            className="shrink-0 rounded-2xl"
                            disabled={!country || isLoading || isExportingPdf}
                        >
                            {isExportingPdf ? (
                                <Loader2 className="size-4 animate-spin" />
                            ) : (
                                <FileDown className="size-4" />
                            )}
                            {isExportingPdf ? "Generando PDF..." : "Exportar PDF"}
                        </Button>
                    </div>
                </SheetHeader>

                <div className="flex flex-col gap-5 px-5 py-5">
                    {exportError ? <p className="text-sm text-destructive">{exportError}</p> : null}
                    {isLoading ? (
                        <DetailSkeleton />
                    ) : isError ? (
                        <p className="text-sm text-destructive">No fue posible cargar el detalle por país.</p>
                    ) : data ? (
                        <>
                            <section className="flex flex-col gap-3">
                                <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">
                                    Familias de exámenes
                                </h2>
                                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6">
                                    {categoryTiles.map((tile) => {
                                        const pct = showComparison
                                            ? getPercentChange(tile.value, tile.comparisonValue)
                                            : null
                                        return (
                                            <Card key={tile.title} className="rounded-2xl shadow-none">
                                                <CardContent className="flex min-h-28 flex-col justify-between gap-2 p-4">
                                                    <span className="text-sm font-medium text-slate-600">
                                                        {tile.title}
                                                    </span>
                                                    <span className="text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">
                                                        {formatInteger(tile.value)}
                                                    </span>
                                                    {showComparison && (
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-xs text-muted-foreground">
                                                                {formatInteger(tile.comparisonValue)}
                                                            </span>
                                                            {pct !== null && (
                                                                <span
                                                                    className={cn(
                                                                        "text-xs font-medium",
                                                                        pct >= 0 ? "text-emerald-600" : "text-rose-600",
                                                                    )}
                                                                >
                                                                    {formatPercentChange(pct)}
                                                                </span>
                                                            )}
                                                        </div>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        )
                                    })}
                                </div>
                            </section>

                            <section className="flex flex-col gap-3">
                                <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">
                                    Ingresos por producto
                                </h2>
                                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                                    <Card className="rounded-2xl shadow-none">
                                        <CardContent className="flex min-h-20 flex-col justify-between gap-2 p-4">
                                            <span className="text-xs font-medium text-slate-500">Ing. Exámenes</span>
                                            <span className="text-xl font-semibold tracking-tight text-slate-900">
                                                {formatCurrency(data.exam_revenue)}
                                            </span>
                                            {showComparison &&
                                                data.comparison_exam_revenue !== null &&
                                                data.comparison_exam_revenue !== undefined &&
                                                (() => {
                                                    const pct = getPercentChange(
                                                        data.exam_revenue,
                                                        data.comparison_exam_revenue,
                                                    )
                                                    return (
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-xs text-muted-foreground">
                                                                {formatCurrency(data.comparison_exam_revenue)}
                                                            </span>
                                                            {pct !== null && (
                                                                <span
                                                                    className={cn(
                                                                        "text-xs font-medium",
                                                                        pct >= 0 ? "text-emerald-600" : "text-rose-600",
                                                                    )}
                                                                >
                                                                    {formatPercentChange(pct)}
                                                                </span>
                                                            )}
                                                        </div>
                                                    )
                                                })()}
                                        </CardContent>
                                    </Card>
                                    <Card className="rounded-2xl shadow-none">
                                        <CardContent className="flex min-h-20 flex-col justify-between gap-2 p-4">
                                            <span className="text-xs font-medium text-slate-500">Libros</span>
                                            <span className="text-xl font-semibold tracking-tight text-slate-900">
                                                {formatInteger(data.total_books)}
                                            </span>
                                            {showComparison &&
                                                data.comparison_total_books !== null &&
                                                data.comparison_total_books !== undefined &&
                                                (() => {
                                                    const pct = getPercentChange(
                                                        data.total_books,
                                                        data.comparison_total_books,
                                                    )
                                                    return (
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-xs text-muted-foreground">
                                                                {formatInteger(data.comparison_total_books)}
                                                            </span>
                                                            {pct !== null && (
                                                                <span
                                                                    className={cn(
                                                                        "text-xs font-medium",
                                                                        pct >= 0 ? "text-emerald-600" : "text-rose-600",
                                                                    )}
                                                                >
                                                                    {formatPercentChange(pct)}
                                                                </span>
                                                            )}
                                                        </div>
                                                    )
                                                })()}
                                        </CardContent>
                                    </Card>
                                    <Card className="rounded-2xl shadow-none">
                                        <CardContent className="flex min-h-20 flex-col justify-between gap-2 p-4">
                                            <span className="text-xs font-medium text-slate-500">Ing. Libros</span>
                                            <span className="text-xl font-semibold tracking-tight text-slate-900">
                                                {formatCurrency(data.book_revenue)}
                                            </span>
                                            {showComparison &&
                                                data.comparison_book_revenue !== null &&
                                                data.comparison_book_revenue !== undefined &&
                                                (() => {
                                                    const pct = getPercentChange(
                                                        data.book_revenue,
                                                        data.comparison_book_revenue,
                                                    )
                                                    return (
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-xs text-muted-foreground">
                                                                {formatCurrency(data.comparison_book_revenue)}
                                                            </span>
                                                            {pct !== null && (
                                                                <span
                                                                    className={cn(
                                                                        "text-xs font-medium",
                                                                        pct >= 0 ? "text-emerald-600" : "text-rose-600",
                                                                    )}
                                                                >
                                                                    {formatPercentChange(pct)}
                                                                </span>
                                                            )}
                                                        </div>
                                                    )
                                                })()}
                                        </CardContent>
                                    </Card>
                                    <Card className="rounded-2xl shadow-none">
                                        <CardContent className="flex min-h-20 flex-col justify-between gap-2 p-4">
                                            <span className="text-xs font-medium text-slate-500">Cursos</span>
                                            <span className="text-xl font-semibold tracking-tight text-slate-900">
                                                {formatInteger(data.total_courses)}
                                            </span>
                                            {showComparison &&
                                                data.comparison_total_courses !== null &&
                                                data.comparison_total_courses !== undefined &&
                                                (() => {
                                                    const pct = getPercentChange(
                                                        data.total_courses,
                                                        data.comparison_total_courses,
                                                    )
                                                    return (
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-xs text-muted-foreground">
                                                                {formatInteger(data.comparison_total_courses)}
                                                            </span>
                                                            {pct !== null && (
                                                                <span
                                                                    className={cn(
                                                                        "text-xs font-medium",
                                                                        pct >= 0 ? "text-emerald-600" : "text-rose-600",
                                                                    )}
                                                                >
                                                                    {formatPercentChange(pct)}
                                                                </span>
                                                            )}
                                                        </div>
                                                    )
                                                })()}
                                        </CardContent>
                                    </Card>
                                    <Card className="rounded-2xl shadow-none">
                                        <CardContent className="flex min-h-20 flex-col justify-between gap-2 p-4">
                                            <span className="text-xs font-medium text-slate-500">Ing. Cursos</span>
                                            <span className="text-xl font-semibold tracking-tight text-slate-900">
                                                {formatCurrency(data.course_revenue)}
                                            </span>
                                            {showComparison &&
                                                data.comparison_course_revenue !== null &&
                                                data.comparison_course_revenue !== undefined &&
                                                (() => {
                                                    const pct = getPercentChange(
                                                        data.course_revenue,
                                                        data.comparison_course_revenue,
                                                    )
                                                    return (
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-xs text-muted-foreground">
                                                                {formatCurrency(data.comparison_course_revenue)}
                                                            </span>
                                                            {pct !== null && (
                                                                <span
                                                                    className={cn(
                                                                        "text-xs font-medium",
                                                                        pct >= 0 ? "text-emerald-600" : "text-rose-600",
                                                                    )}
                                                                >
                                                                    {formatPercentChange(pct)}
                                                                </span>
                                                            )}
                                                        </div>
                                                    )
                                                })()}
                                        </CardContent>
                                    </Card>
                                </div>
                            </section>

                            <section className="flex flex-col gap-3">
                                <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">
                                    Desglose por examen
                                </h2>
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                    {DETALLE_ASESOR_EXAM_TYPES.map((examType) => {
                                        const current = data.exam_counts[examType] ?? 0
                                        const comparison = data.comparison_exam_counts?.[examType] ?? 0
                                        const pct = showComparison ? getPercentChange(current, comparison) : null
                                        return (
                                            <Card key={examType} className="rounded-2xl shadow-none">
                                                <CardContent className="flex items-center justify-between gap-4 p-4">
                                                    <span className="text-sm font-medium text-slate-700">
                                                        {examType}
                                                    </span>
                                                    <div className="flex flex-col items-end">
                                                        <span className="text-lg font-semibold text-slate-900 tabular-nums">
                                                            {formatInteger(current)}
                                                        </span>
                                                        {showComparison && (
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-xs text-muted-foreground">
                                                                    {formatInteger(comparison)}
                                                                </span>
                                                                {pct !== null && (
                                                                    <span
                                                                        className={cn(
                                                                            "text-xs font-medium",
                                                                            pct >= 0
                                                                                ? "text-emerald-600"
                                                                                : "text-rose-600",
                                                                        )}
                                                                    >
                                                                        {formatPercentChange(pct)}
                                                                    </span>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        )
                                    })}
                                </div>
                            </section>
                        </>
                    ) : null}
                </div>
            </SheetContent>
        </Sheet>
    )
}

function DetailSkeleton() {
    return (
        <div className="flex flex-col gap-5">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6">
                {Array.from({ length: 6 }).map((_, index) => (
                    <Card key={index} className="rounded-2xl shadow-none">
                        <CardContent className="flex min-h-28 flex-col justify-between gap-4 p-4">
                            <Skeleton className="h-4 w-16" />
                            <Skeleton className="h-8 w-20" />
                        </CardContent>
                    </Card>
                ))}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {Array.from({ length: 10 }).map((_, index) => (
                    <Card key={index} className="rounded-2xl shadow-none">
                        <CardContent className="flex items-center justify-between gap-4 p-4">
                            <Skeleton className="h-4 w-36" />
                            <Skeleton className="h-6 w-12" />
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    )
}
