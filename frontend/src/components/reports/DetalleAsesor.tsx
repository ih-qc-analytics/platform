import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAsesorDetail } from "@/hooks/useReports"
import type { AsesorFilters, BusinessStatusDetail } from "@/types"
import { cn, formatCurrency, formatInteger } from "@/lib/utils"

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
    wide?: boolean
}

type BreakdownTileProps = {
    title: string
    firstLabel: string
    firstValue: number
    secondLabel: string
    secondValue: number
    totalLabel: string
    totalValue: number
    tone: "blue" | "purple" | "amber" | "green" | "rose" | "indigo"
}

const tileToneClassNames = {
    blue: "border-blue-200 bg-blue-50",
    purple: "border-purple-200 bg-purple-50",
    amber: "border-amber-200 bg-amber-50",
    green: "border-emerald-200 bg-emerald-50",
    rose: "border-rose-200 bg-rose-50",
    indigo: "border-indigo-200 bg-indigo-100/80",
} as const

export default function DetalleAsesor({
    sellerId,
    sellerName,
    open,
    onOpenChange,
    filters,
}: DetalleAsesorProps) {
    const { data, isLoading, isError } = useAsesorDetail(sellerId, filters, open)

    const examEntries = Object.entries(data?.exam_breakdown ?? {})
    const statusEntries: Array<{
        title: string
        detail: BusinessStatusDetail
        tone: BreakdownTileProps["tone"]
    }> = data
        ? [
              { title: "Ganados", detail: data.ganados, tone: "green" },
              { title: "Perdidos", detail: data.perdidos, tone: "rose" },
              { title: "Mantenidos", detail: data.mantenidos, tone: "indigo" },
          ]
        : []

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" className="w-full overflow-y-auto p-0 sm:max-w-3xl lg:max-w-5xl">
                <SheetHeader className="border-b border-border px-7 py-6">
                    <SheetTitle className="text-4xl font-semibold tracking-tight text-slate-900">
                        {data?.seller_name ?? sellerName ?? "Detalle"}
                    </SheetTitle>
                </SheetHeader>

                <div className="flex flex-col gap-8 px-7 py-8">
                    {isLoading ? (
                        <DetalleSkeleton />
                    ) : isError ? (
                        <p className="text-sm text-destructive">No fue posible cargar el detalle.</p>
                    ) : data ? (
                        <>
                            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                <SummaryInfoCard label="País" value={joinValues(data.countries)} />
                                <SummaryInfoCard label="Sede" value={joinValues(data.zones)} />
                                <SummaryInfoCard label="Estado" value={joinValues(data.states)} />
                                <SummaryInfoCard label="Ciudad" value={joinValues(data.cities)} />
                                <SummaryInfoCard label="Total Colegios" value={formatInteger(data.total_schools)} />
                                <SummaryInfoCard label="Total Exámenes" value={formatInteger(data.total_exams)} />
                                <SummaryInfoCard label="Valor Total" value={formatCurrency(data.total_revenue)} wide />
                            </div>

                            <section className="flex flex-col gap-4">
                                <h2 className="text-2xl font-semibold uppercase tracking-wide text-slate-700">
                                    Tipos de exámenes
                                </h2>
                                <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                                    {examEntries.map(([label, detail], index) => (
                                        <BreakdownTile
                                            key={label}
                                            title={label}
                                            firstLabel="Exámenes"
                                            firstValue={detail.exams}
                                            secondLabel="Colegios"
                                            secondValue={detail.schools}
                                            totalLabel="Valor"
                                            totalValue={detail.revenue}
                                            tone={(["blue", "purple", "amber"] as const)[index % 3]}
                                        />
                                    ))}
                                </div>
                            </section>

                            <section className="flex flex-col gap-4">
                                <h2 className="text-2xl font-semibold uppercase tracking-wide text-slate-700">
                                    Estado de colegios
                                </h2>
                                <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                                    {statusEntries.map(({ title, detail, tone }) => (
                                        <BreakdownTile
                                            key={title}
                                            title={title}
                                            firstLabel="Colegios"
                                            firstValue={detail.schools}
                                            secondLabel="Exámenes"
                                            secondValue={detail.exams}
                                            totalLabel="Valor"
                                            totalValue={detail.revenue}
                                            tone={tone}
                                        />
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

function SummaryInfoCard({ label, value, wide = false }: SummaryInfoCardProps) {
    return (
        <Card className={cn("rounded-3xl shadow-none", wide && "md:col-span-2")}>
            <CardContent className="flex min-h-36 flex-col justify-between gap-6 p-6">
                <span className="text-sm font-medium text-slate-500">{label}</span>
                <span className="text-4xl font-semibold tracking-tight text-slate-900">{value || "-"}</span>
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
    totalLabel,
    totalValue,
    tone,
}: BreakdownTileProps) {
    return (
        <Card className={cn("rounded-3xl shadow-none", tileToneClassNames[tone])}>
            <CardContent className="flex h-full flex-col gap-8 p-6">
                <h3 className="text-2xl font-semibold text-slate-900">{title}</h3>
                <div className="flex flex-col gap-5">
                    <MetricRow label={firstLabel} value={formatInteger(firstValue)} />
                    <MetricRow label={secondLabel} value={formatInteger(secondValue)} />
                </div>
                <div className="border-t border-current/15 pt-4">
                    <MetricRow label={totalLabel} value={formatCurrency(totalValue)} />
                </div>
            </CardContent>
        </Card>
    )
}

function MetricRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex items-end justify-between gap-4">
            <span className="text-sm text-slate-600">{label}:</span>
            <span className="text-2xl font-semibold text-slate-900">{value}</span>
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
