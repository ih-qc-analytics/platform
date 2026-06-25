import { LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { TrendPoint } from "@/types"
import { formatRevenue } from "@/lib/utils"
import { useMemo } from "react"

const LINE_STROKE_WIDTH = 2
const Y_AXIS_WIDTH = 60

type TrendLineProps = {
    data: TrendPoint[]
    comparisonData?: TrendPoint[]
}

const chartConfig = {
    revenue: {
        label: "Ingresos",
        color: "hsl(var(--chart-1))",
    },
} satisfies ChartConfig

export default function TrendLine({ data, comparisonData }: TrendLineProps) {
    const chartData = useMemo(() => {
        const comparisonByMonth = new Map((comparisonData ?? []).map(point => [point.month, point.revenue]))
        return data.map(point => ({
            month: point.month,
            revenue: point.revenue,
            comparison_revenue: comparisonByMonth.get(point.month) ?? null,
        }))
    }, [comparisonData, data])

    if (!data.length) return (
        <Card>
            <CardContent className="flex items-center justify-center min-h-48">
                <p className="text-sm text-muted-foreground">Sin datos para el período seleccionado</p>
            </CardContent>
        </Card>
    )

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-sm font-medium">Ingresos por Mes</CardTitle>
            </CardHeader>
            <CardContent>
                <ChartContainer config={chartConfig} className="min-h-48 w-full">
                    <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="month" tickLine={false} axisLine={false} />
                        <YAxis tickFormatter={(value) => formatRevenue(value as number)} tickLine={false} axisLine={false} width={Y_AXIS_WIDTH} />
                        <ChartTooltip content={<ChartTooltipContent formatter={(val) => formatRevenue(val as number)} />} />
                        <Line type="monotone" dataKey="revenue" stroke="var(--color-revenue)" strokeWidth={LINE_STROKE_WIDTH} dot={false} />
                        {comparisonData?.length ? (
                            <Line
                                type="monotone"
                                dataKey="comparison_revenue"
                                stroke="hsl(var(--chart-2))"
                                strokeWidth={LINE_STROKE_WIDTH}
                                dot={false}
                                strokeDasharray="4 4"
                            />
                        ) : null}
                    </LineChart>
                </ChartContainer>
            </CardContent>
        </Card>
    )
}
