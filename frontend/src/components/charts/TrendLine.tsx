import { LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { TrendPoint } from "@/types"
import { formatRevenue } from "@/lib/utils"

const LINE_STROKE_WIDTH = 2
const Y_AXIS_WIDTH = 60

type TrendLineProps = {
    data: TrendPoint[]
}

const chartConfig = {
    revenue: {
        label: "Ingresos",
        color: "hsl(var(--chart-1))",
    },
} satisfies ChartConfig

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
                        <XAxis dataKey="month" tickLine={false} axisLine={false} />
                        <YAxis tickFormatter={formatRevenue} tickLine={false} axisLine={false} width={Y_AXIS_WIDTH} />
                        <ChartTooltip content={<ChartTooltipContent formatter={(val) => formatRevenue(val as number)} />} />
                        <Line type="monotone" dataKey="revenue" stroke="var(--color-revenue)" strokeWidth={LINE_STROKE_WIDTH} dot={false} />
                    </LineChart>
                </ChartContainer>
            </CardContent>
        </Card>
    )
}