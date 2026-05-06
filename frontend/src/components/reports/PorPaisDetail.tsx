import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { usePorPaisDetail } from "@/hooks/useReports"
import { cn, formatInteger } from "@/lib/utils"
import type { PorPaisFilters } from "@/types"
import { DETALLE_ASESOR_EXAM_TYPES } from "@/components/reports/detalleAsesorExamTypes"

type PorPaisDetailProps = {
    country: string | null
    open: boolean
    onOpenChange: (open: boolean) => void
    filters: PorPaisFilters
}

export default function PorPaisDetail({
    country,
    open,
    onOpenChange,
    filters,
}: PorPaisDetailProps) {
    const { data, isLoading, isError } = usePorPaisDetail(country, filters, open)

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" className="w-full overflow-y-auto p-0 sm:max-w-2xl">
                <SheetHeader className="border-b border-border px-5 py-4">
                    <SheetTitle className="text-2xl font-semibold tracking-tight text-slate-900">
                        {data?.country ?? country ?? "Detalle"}
                    </SheetTitle>
                </SheetHeader>

                <div className="px-5 py-5">
                    {isLoading ? (
                        <DetailSkeleton />
                    ) : isError ? (
                        <p className="text-sm text-destructive">No fue posible cargar el detalle por país.</p>
                    ) : data ? (
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                            {DETALLE_ASESOR_EXAM_TYPES.map(examType => (
                                <Card key={examType} className="rounded-2xl shadow-none">
                                    <CardContent className="flex items-center justify-between gap-4 p-4">
                                        <span className="text-sm font-medium text-slate-700">{examType}</span>
                                        <span className={cn("text-lg font-semibold text-slate-900", "tabular-nums")}>
                                            {formatInteger(data.exam_counts[examType] ?? 0)}
                                        </span>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : null}
                </div>
            </SheetContent>
        </Sheet>
    )
}

function DetailSkeleton() {
    return (
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
    )
}
