import { FileDown, Loader2 } from "lucide-react"

import { exportAsesorDetailPdf } from "@/api/reports"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAsesorDetail } from "@/hooks/useReports"
import type { AsesorFilters, BusinessStatusDetail } from "@/types"
import { cn, formatCurrency, formatInteger, formatPercentChange, getPercentChange } from "@/lib/utils"
import { ASESOR_EXAM_CATEGORIES } from "@/components/reports/asesorCategories"
import { useState } from "react"

type DetalleAsesorProps = {
    sellerId: number | null
    sellerName?: string
    open: boolean
    onOpenChange: (open: boolean) => void
    filters: AsesorFilters
}

type SummaryInfoCardProps = {
    label: string
    value: string
    comparisonValue?: string
    comparisonPct?: number | null
    showComparison?: boolean
    wide?: boolean
}

type BreakdownTileProps = {
    title: string
    firstLabel: string
    firstValue: number
    secondLabel: string
    secondValue: number
    thirdLabel?: string
    thirdValue?: number
    fourthLabel?: string
    fourthValue?: number
    totalLabel: string
    totalValue: number
    tone: "blue" | "purple" | "amber" | "green" | "rose" | "indigo"
    showComparison?: boolean
    comparisonFirstValue?: number
    comparisonSecondValue?: number
    comparisonTotalValue?: number
}

const tileToneClassNames = {
    blue: "border-blue-200 bg-blue-50",
    purple: "border-purple-200 bg-purple-50",
    amber: "border-amber-200 bg-amber-50",
    green: "border-emerald-200 bg-emerald-50",
    rose: "border-rose-200 bg-rose-50",
    indigo: "border-indigo-200 bg-indigo-100/80",
} as const

export default function DetalleAsesor({ sellerId, sellerName, open, onOpenChange, filters }: DetalleAsesorProps) {
    const [isExportingPdf, setIsExportingPdf] = useState(false)
    const [exportError, setExportError] = useState<string | null>(null)
    const { data, isLoading, isError } = useAsesorDetail(sellerId, filters, open)
    const detail = data?.current
    const comparisonDetail = data?.comparison?.data
    const showComparison = Boolean(filters.show_comparison && comparisonDetail)

    const statusEntries: Array<{
        title: string
        detail: BusinessStatusDetail
        tone: BreakdownTileProps["tone"]
    }> = detail
        ? [
              { title: "Ganados", detail: detail.ganados, tone: "green" },
              { title: "Perdidos", detail: detail.perdidos, tone: "rose" },
              { title: "Mantenidos", detail: detail.mantenidos, tone: "indigo" },
          ]
        : []

    const handleExportPdf = async () => {
        if (!sellerId) return

        setExportError(null)
        setIsExportingPdf(true)
        try {
            await exportAsesorDetailPdf(sellerId, filters)
        } catch {
            setExportError("No fue posible exportar el archivo. Intenta de nuevo.")
        } finally {
            setIsExportingPdf(false)
        }
    }

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" className="w-full overflow-y-auto p-0 sm:max-w-3xl lg:max-w-5xl">
                <SheetHeader className="border-b border-border px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                        <SheetTitle className="text-2xl font-semibold tracking-tight text-slate-900">
                            {detail?.seller_name ?? sellerName ?? "Detalle"}
                        </SheetTitle>
                        <Button
                            onClick={() => void handleExportPdf()}
                            variant="outline"
                            className="shrink-0 rounded-2xl"
                            disabled={!sellerId || isLoading || isExportingPdf}
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
                        <DetalleSkeleton />
                    ) : isError ? (
                        <p className="text-sm text-destructive">No fue posible cargar el detalle.</p>
                    ) : detail ? (
                        <>
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                <SummaryInfoCard label="País" value={joinValues(detail.countries)} />
                                <SummaryInfoCard label="Sede" value={joinValues(detail.zones)} />
                                <SummaryInfoCard label="Estado" value={joinValues(detail.states)} />
                                <SummaryInfoCard label="Ciudad" value={joinValues(detail.cities)} />
                                <SummaryInfoCard
                                    label="Total Colegios"
                                    value={formatInteger(detail.total_schools)}
                                    comparisonValue={
                                        comparisonDetail ? formatInteger(comparisonDetail.total_schools) : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(detail.total_schools, comparisonDetail?.total_schools)
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Total Exámenes"
                                    value={formatInteger(detail.total_exams)}
                                    comparisonValue={
                                        comparisonDetail ? formatInteger(comparisonDetail.total_exams) : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(detail.total_exams, comparisonDetail?.total_exams)
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Libros"
                                    value={formatInteger(detail.total_books)}
                                    comparisonValue={
                                        comparisonDetail ? formatInteger(comparisonDetail.total_books) : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(detail.total_books, comparisonDetail?.total_books)
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Cursos"
                                    value={formatInteger(detail.total_courses)}
                                    comparisonValue={
                                        comparisonDetail ? formatInteger(comparisonDetail.total_courses) : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(detail.total_courses, comparisonDetail?.total_courses)
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Ing. Exámenes"
                                    value={formatCurrency(
                                        Object.values(detail.exam_breakdown).reduce((sum, cat) => sum + cat.revenue, 0),
                                    )}
                                    comparisonValue={
                                        comparisonDetail
                                            ? formatCurrency(
                                                  Object.values(comparisonDetail.exam_breakdown).reduce(
                                                      (sum, cat) => sum + cat.revenue,
                                                      0,
                                                  ),
                                              )
                                            : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(
                                                  Object.values(detail.exam_breakdown).reduce(
                                                      (sum, cat) => sum + cat.revenue,
                                                      0,
                                                  ),
                                                  comparisonDetail
                                                      ? Object.values(comparisonDetail.exam_breakdown).reduce(
                                                            (sum, cat) => sum + cat.revenue,
                                                            0,
                                                        )
                                                      : undefined,
                                              )
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Ing. Libros"
                                    value={formatCurrency(detail.book_revenue)}
                                    comparisonValue={
                                        comparisonDetail ? formatCurrency(comparisonDetail.book_revenue) : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(detail.book_revenue, comparisonDetail?.book_revenue)
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Ing. Cursos"
                                    value={formatCurrency(detail.course_revenue)}
                                    comparisonValue={
                                        comparisonDetail ? formatCurrency(comparisonDetail.course_revenue) : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(detail.course_revenue, comparisonDetail?.course_revenue)
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Sin Categorizar"
                                    value={formatCurrency(detail.uncategorized_revenue)}
                                    comparisonValue={
                                        comparisonDetail
                                            ? formatCurrency(comparisonDetail.uncategorized_revenue)
                                            : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(
                                                  detail.uncategorized_revenue,
                                                  comparisonDetail?.uncategorized_revenue,
                                              )
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Valor Total"
                                    value={formatCurrency(detail.total_revenue)}
                                    comparisonValue={
                                        comparisonDetail ? formatCurrency(comparisonDetail.total_revenue) : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(detail.total_revenue, comparisonDetail?.total_revenue)
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                    wide
                                />
                                <SummaryInfoCard
                                    label="Ing. Asignado"
                                    value={formatCurrency(detail.allocated_revenue)}
                                    comparisonValue={
                                        comparisonDetail
                                            ? formatCurrency(comparisonDetail.allocated_revenue)
                                            : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(
                                                  detail.allocated_revenue,
                                                  comparisonDetail?.allocated_revenue,
                                              )
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Ing. Esperado"
                                    value={formatCurrency(detail.expected_revenue)}
                                    comparisonValue={
                                        comparisonDetail ? formatCurrency(comparisonDetail.expected_revenue) : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(
                                                  detail.expected_revenue,
                                                  comparisonDetail?.expected_revenue,
                                              )
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Costo Esperado"
                                    value={formatCurrency(detail.expected_cost)}
                                    comparisonValue={
                                        comparisonDetail ? formatCurrency(comparisonDetail.expected_cost) : undefined
                                    }
                                    comparisonPct={
                                        showComparison
                                            ? getPercentChange(detail.expected_cost, comparisonDetail?.expected_cost)
                                            : undefined
                                    }
                                    showComparison={showComparison}
                                />
                                <SummaryInfoCard
                                    label="Margen de Utilidad"
                                    value={`${detail.profit_margin.toFixed(1)}%`}
                                    showComparison={false}
                                />
                            </div>

                            <section className="flex flex-col gap-3">
                                <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">
                                    Categorías de exámenes
                                </h2>
                                <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
                                    {ASESOR_EXAM_CATEGORIES.map((label, index) => {
                                        const categoryDetail = detail?.exam_breakdown[label] ?? {
                                            exams: 0,
                                            schools: 0,
                                            revenue: 0,
                                        }
                                        const comparisonCategoryDetail = comparisonDetail?.exam_breakdown[label]

                                        return (
                                            <BreakdownTile
                                                key={label}
                                                title={label}
                                                firstLabel="Exámenes"
                                                firstValue={categoryDetail.exams}
                                                secondLabel="Colegios"
                                                secondValue={categoryDetail.schools}
                                                totalLabel="Valor"
                                                totalValue={categoryDetail.revenue}
                                                tone={(["blue", "purple", "amber"] as const)[index % 3]}
                                                showComparison={showComparison}
                                                comparisonFirstValue={comparisonCategoryDetail?.exams}
                                                comparisonSecondValue={comparisonCategoryDetail?.schools}
                                                comparisonTotalValue={comparisonCategoryDetail?.revenue}
                                            />
                                        )
                                    })}
                                </div>
                            </section>

                            {showComparison && (
                                <section className="flex flex-col gap-3">
                                    <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">
                                        Estado de colegios
                                    </h2>
                                    <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
                                        {statusEntries.map(({ title, detail, tone }) => (
                                            <BreakdownTile
                                                key={title}
                                                title={title}
                                                firstLabel="Colegios"
                                                firstValue={detail.schools}
                                                secondLabel="Exámenes"
                                                secondValue={detail.exams}
                                                thirdLabel="Libros"
                                                thirdValue={detail.books}
                                                fourthLabel="Cursos"
                                                fourthValue={detail.courses}
                                                totalLabel="Valor"
                                                totalValue={detail.revenue}
                                                tone={tone}
                                            />
                                        ))}
                                    </div>
                                </section>
                            )}
                        </>
                    ) : null}
                </div>
            </SheetContent>
        </Sheet>
    )
}

function SummaryInfoCard({
    label,
    value,
    comparisonValue,
    comparisonPct,
    showComparison = false,
    wide = false,
}: SummaryInfoCardProps) {
    return (
        <Card className={cn("rounded-2xl shadow-none", wide && "md:col-span-2")}>
            <CardContent className="flex min-h-20 flex-col justify-between gap-3 p-4">
                <span className="text-xs font-medium text-slate-500">{label}</span>
                <span className="text-xl font-semibold tracking-tight text-slate-900">{value || "-"}</span>
                {showComparison && comparisonValue ? (
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">{comparisonValue}</span>
                        {comparisonPct !== undefined && comparisonPct !== null && (
                            <span
                                className={cn(
                                    "text-xs font-medium",
                                    comparisonPct >= 0 ? "text-emerald-600" : "text-rose-600",
                                )}
                            >
                                {formatPercentChange(comparisonPct)}
                            </span>
                        )}
                    </div>
                ) : null}
            </CardContent>
        </Card>
    )
}

function BreakdownTile({
    title,
    firstLabel,
    firstValue,
    secondLabel,
    secondValue,
    thirdLabel,
    thirdValue,
    fourthLabel,
    fourthValue,
    totalLabel,
    totalValue,
    tone,
    showComparison = false,
    comparisonFirstValue,
    comparisonSecondValue,
    comparisonTotalValue,
}: BreakdownTileProps) {
    return (
        <Card className={cn("rounded-2xl shadow-none", tileToneClassNames[tone])}>
            <CardContent className="flex h-full flex-col gap-4 p-4">
                <h3 className="text-base font-semibold text-slate-900">{title}</h3>
                <div className="flex flex-col gap-2">
                    <MetricRow label={firstLabel} value={formatInteger(firstValue)} />
                    {showComparison && comparisonFirstValue !== undefined && (() => {
                        const pct = getPercentChange(firstValue, comparisonFirstValue)
                        return (
                            <div className="flex items-center justify-end gap-2">
                                <span className="text-xs text-muted-foreground">{formatInteger(comparisonFirstValue)}</span>
                                {pct !== null && (
                                    <span className={cn("text-xs font-medium", pct >= 0 ? "text-emerald-600" : "text-rose-600")}>
                                        {formatPercentChange(pct)}
                                    </span>
                                )}
                            </div>
                        )
                    })()}
                    <MetricRow label={secondLabel} value={formatInteger(secondValue)} />
                    {showComparison && comparisonSecondValue !== undefined && (() => {
                        const pct = getPercentChange(secondValue, comparisonSecondValue)
                        return (
                            <div className="flex items-center justify-end gap-2">
                                <span className="text-xs text-muted-foreground">{formatInteger(comparisonSecondValue)}</span>
                                {pct !== null && (
                                    <span className={cn("text-xs font-medium", pct >= 0 ? "text-emerald-600" : "text-rose-600")}>
                                        {formatPercentChange(pct)}
                                    </span>
                                )}
                            </div>
                        )
                    })()}
                    {thirdLabel !== undefined && thirdValue !== undefined && (
                        <MetricRow label={thirdLabel} value={formatInteger(thirdValue)} />
                    )}
                    {fourthLabel !== undefined && fourthValue !== undefined && (
                        <MetricRow label={fourthLabel} value={formatInteger(fourthValue)} />
                    )}
                </div>
                <div className="border-t border-current/15 pt-4">
                    <MetricRow label={totalLabel} value={formatCurrency(totalValue)} />
                    {showComparison && comparisonTotalValue !== undefined && (() => {
                        const pct = getPercentChange(totalValue, comparisonTotalValue)
                        return (
                            <div className="flex items-center justify-end gap-2">
                                <span className="text-xs text-muted-foreground">{formatCurrency(comparisonTotalValue)}</span>
                                {pct !== null && (
                                    <span className={cn("text-xs font-medium", pct >= 0 ? "text-emerald-600" : "text-rose-600")}>
                                        {formatPercentChange(pct)}
                                    </span>
                                )}
                            </div>
                        )
                    })()}
                </div>
            </CardContent>
        </Card>
    )
}

function MetricRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex items-end justify-between gap-4">
            <span className="text-xs text-slate-600">{label}:</span>
            <span className="text-base font-semibold text-slate-900">{value}</span>
        </div>
    )
}

function joinValues(values: string[]) {
    return values.length > 0 ? values.join(", ") : "-"
}

function DetalleSkeleton() {
    return (
        <div className="flex flex-col gap-8">
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                {Array.from({ length: 6 }).map((_, index) => (
                    <Card key={index} className={cn("rounded-3xl shadow-none", index === 5 && "md:col-span-2")}>
                        <CardContent className="flex min-h-36 flex-col justify-between gap-6 p-6">
                            <Skeleton className="h-4 w-20" />
                            <Skeleton className="h-10 w-40" />
                        </CardContent>
                    </Card>
                ))}
            </div>
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                {Array.from({ length: 3 }).map((_, index) => (
                    <Card key={index} className="rounded-3xl shadow-none">
                        <CardContent className="flex h-full flex-col gap-8 p-6">
                            <Skeleton className="h-8 w-28" />
                            <div className="flex flex-col gap-5">
                                <Skeleton className="h-8 w-full" />
                                <Skeleton className="h-8 w-full" />
                            </div>
                            <Skeleton className="h-8 w-full" />
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    )
}
