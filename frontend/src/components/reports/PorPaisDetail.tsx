import { useMemo, useState } from "react"
import { FileDown, Loader2 } from "lucide-react"

import { exportPorPaisDetailPdf } from "@/api/reports"
import { DETALLE_ASESOR_EXAM_TYPES } from "@/components/reports/detalleAsesorExamTypes"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { usePorPaisDetail } from "@/hooks/useReports"
import { formatInteger } from "@/lib/utils"
import type { PorPaisFilters } from "@/types"

type PorPaisDetailProps = {
    country: string | null
    open: boolean
    onOpenChange: (open: boolean) => void
    filters: PorPaisFilters
}

const FAMILY_EXAM_TYPES = {
    Cambridge: DETALLE_ASESOR_EXAM_TYPES.filter((name) => !["IELTS", "MET", "MET Go!", "TEA", "Other"].includes(name)),
    IELTS: ["IELTS"],
    MET: ["MET", "MET Go!"],
    TEA: ["TEA"],
    Otros: ["Other"],
    Total: DETALLE_ASESOR_EXAM_TYPES,
} as const

export default function PorPaisDetail({ country, open, onOpenChange, filters }: PorPaisDetailProps) {
    const [isExportingPdf, setIsExportingPdf] = useState(false)
    const [exportError, setExportError] = useState<string | null>(null)
    const { data, isLoading, isError } = usePorPaisDetail(country, filters, open)

    const categoryTiles = useMemo(
        () => [
            {
                title: "Cambridge",
                value: FAMILY_EXAM_TYPES.Cambridge.reduce(
                    (sum, examType) => sum + (data?.exam_counts[examType] ?? 0),
                    0,
                ),
            },
            {
                title: "IELTS",
                value: FAMILY_EXAM_TYPES.IELTS.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
            },
            {
                title: "MET",
                value: FAMILY_EXAM_TYPES.MET.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
            },
            {
                title: "TEA",
                value: FAMILY_EXAM_TYPES.TEA.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
            },
            {
                title: "Otros",
                value: FAMILY_EXAM_TYPES.Otros.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
            },
            {
                title: "Total",
                value: FAMILY_EXAM_TYPES.Total.reduce((sum, examType) => sum + (data?.exam_counts[examType] ?? 0), 0),
            },
        ],
        [data?.exam_counts],
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
                                    {categoryTiles.map((tile) => (
                                        <Card key={tile.title} className="rounded-2xl shadow-none">
                                            <CardContent className="flex min-h-28 flex-col justify-between gap-4 p-4">
                                                <span className="text-sm font-medium text-slate-600">{tile.title}</span>
                                                <span className="text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">
                                                    {formatInteger(tile.value)}
                                                </span>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </section>

                            <section className="flex flex-col gap-3">
                                <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">
                                    Desglose por examen
                                </h2>
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                    {DETALLE_ASESOR_EXAM_TYPES.map((examType) => (
                                        <Card key={examType} className="rounded-2xl shadow-none">
                                            <CardContent className="flex items-center justify-between gap-4 p-4">
                                                <span className="text-sm font-medium text-slate-700">{examType}</span>
                                                <span className="text-lg font-semibold text-slate-900 tabular-nums">
                                                    {formatInteger(data.exam_counts[examType] ?? 0)}
                                                </span>
                                            </CardContent>
                                        </Card>
                                    ))}
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
