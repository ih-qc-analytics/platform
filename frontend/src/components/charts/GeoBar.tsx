import { BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { GeoPoint } from "@/types"
import { formatRevenue } from "@/lib/utils"
import { useMemo } from "react"

type GeoBarProps = {
    data: GeoPoint[]
    comparisonData?: GeoPoint[]
}

const chartConfig = {
    revenue: {
        label: "Actual",
        color: "hsl(var(--chart-1))",
    },
    comparison_revenue: {
        label: "Comparativo",
        color: "hsl(var(--chart-2))",
    },
} satisfies ChartConfig

export default function GeoBar({ data, comparisonData }: GeoBarProps) {
    const chartData = useMemo(() => {
        const comparisonByDimension = new Map((comparisonData ?? []).map((point) => [point.dimension, point.revenue]))
        return data.map((point) => ({
            dimension: point.dimension,
            revenue: point.revenue,
            comparison_revenue: comparisonByDimension.get(point.dimension) ?? null,
        }))
    }, [comparisonData, data])

    if (!data.length)
        return (
            <Card>
                <CardContent className="flex items-center justify-center min-h-48">
                    <p className="text-sm text-muted-foreground">Sin datos para el período seleccionado</p>
                </CardContent>
            </Card>
        )

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-sm font-medium">Ingresos por País</CardTitle>
            </CardHeader>
            <CardContent>
                <ChartContainer config={chartConfig} className="min-h-48 w-full">
                    <BarChart data={chartData} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis
                            type="number"
                            tickFormatter={(value) => formatRevenue(value as number)}
                            tickLine={false}
                            axisLine={false}
                        />
                        <YAxis type="category" dataKey="dimension" tickLine={false} axisLine={false} width={80} />
                        {comparisonData?.length ? (
                            <ChartLegend content={<ChartLegendContent />} />
                        ) : null}
                        <ChartTooltip
                            content={<ChartTooltipContent formatter={(val) => formatRevenue(val as number)} />}
                        />
                        <Bar dataKey="revenue" fill="var(--color-revenue)" radius={[0, 4, 4, 0]} />
                        {comparisonData?.length ? (
                            <Bar
                                dataKey="comparison_revenue"
                                fill="var(--color-comparison_revenue)"
                                radius={[0, 4, 4, 0]}
                            />
                        ) : null}
                    </BarChart>
                </ChartContainer>
            </CardContent>
        </Card>
    )
}
