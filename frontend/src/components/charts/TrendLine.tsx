import { LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { TrendPoint } from "@/types"

type TrendLineProps = {
    data: TrendPoint[]
}

const chartConfig = {
    revenue: {
        label: "Ingresos",
        color: "hsl(var(--chart-1))",
    },
} satisfies ChartConfig

const formatRevenue = (value: number) => {
    if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
    if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`
    return `$${value}`
}

export default function TrendLine({ data }: TrendLineProps) {
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
                    <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                        <YAxis tickFormatter={formatRevenue} tickLine={false} axisLine={false} tick={{ fontSize: 12 }} width={60} />
                        <ChartTooltip content={<ChartTooltipContent formatter={(val) => formatRevenue(val as number)} />} />
                        <Line type="monotone" dataKey="revenue" stroke="var(--color-revenue)" strokeWidth={2} dot={false} />
                    </LineChart>
                </ChartContainer>
            </CardContent>
        </Card>
    )
}