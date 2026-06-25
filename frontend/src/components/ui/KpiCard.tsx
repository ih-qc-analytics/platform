import { ReactNode } from "react"
import { Card, CardContent } from "@/components/ui/card"

type KpiCardProps = {
    title: string
    icon: ReactNode
    value: number
    prefix?: string
    suffix?: string
    decimals?: number
    showComparison?: boolean
    comparisonValue?: number | null
    comparisonPct?: number | null
    comparisonLabel?: string
}

const formatNumber = (value: number, decimals: number) =>
    value.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    })

export default function KpiCard({
    title,
    icon,
    value,
    prefix,
    suffix,
    decimals = 0,
    showComparison = false,
    comparisonValue,
    comparisonPct,
    comparisonLabel = "Periodo comparativo",
}: KpiCardProps) {
    const formatted = formatNumber(value, decimals)
    const comparisonFormatted =
        comparisonValue === null || comparisonValue === undefined ? null : formatNumber(comparisonValue, decimals)

    return (
        <Card>
            <CardContent className="flex items-start justify-between pt-6">
                <div className="flex flex-col gap-2">
                    <span className="text-sm font-medium text-muted-foreground">{title}</span>
                    <span className="text-3xl font-bold">
                        {prefix}
                        {formatted}
                        {suffix}
                    </span>
                    {showComparison && comparisonFormatted !== null ? (
                        <div className="flex flex-col gap-1">
                            <span className="text-xs text-muted-foreground">
                                {comparisonLabel}: {prefix}
                                {comparisonFormatted}
                                {suffix}
                            </span>
                            {comparisonPct !== null && comparisonPct !== undefined ? (
                                <span
                                    className={`text-sm font-medium ${comparisonPct >= 0 ? "text-success" : "text-destructive"}`}
                                >
                                    {comparisonPct >= 0 ? "+" : ""}
                                    {comparisonPct.toFixed(1)}%
                                </span>
                            ) : null}
                        </div>
                    ) : null}
                </div>
                <div className="flex items-center justify-center rounded-xl bg-primary/10 p-3 text-primary [&>svg]:size-5">
                    {icon}
                </div>
            </CardContent>
        </Card>
    )
}
