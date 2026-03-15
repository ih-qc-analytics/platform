import { BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { GeoPoint } from "@/types"

type GeoBarProps = {
    data: GeoPoint[]
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

export default function GeoBar({ data }: GeoBarProps) {
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
                <CardTitle className="text-sm font-medium">Ingresos por País</CardTitle>
            </CardHeader>
            <CardContent>
                <ChartContainer config={chartConfig} className="min-h-48 w-full">
                    <BarChart data={data} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" tickFormatter={formatRevenue} tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                        <YAxis type="category" dataKey="dimension" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} width={80} />
                        <ChartTooltip content={<ChartTooltipContent formatter={(val) => formatRevenue(val as number)} />} />
                        <Bar dataKey="revenue" fill="var(--color-revenue)" radius={[0, 4, 4, 0]} />
                    </BarChart>
                </ChartContainer>
            </CardContent>
        </Card>
    )
}