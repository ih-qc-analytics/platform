import { ReactNode } from "react"
import { Card, CardContent } from "@/components/ui/card"

type KpiCardProps = {
    title: string
    icon: ReactNode
    value: number
    prefix?: string
    suffix?: string
    decimals?: number      
    growth?: number
}

export default function KpiCard({ title, icon, value, prefix, suffix, decimals = 0, growth }: KpiCardProps) {
    const formatted = value.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    })

    return (
        <Card>
            <CardContent className="flex justify-between items-start pt-6">
                <div className="flex flex-col gap-2">
                    <span className="text-muted-foreground text-sm font-medium">{title}</span>
                    <span className="text-3xl font-bold">
                        {prefix}{formatted}{suffix}
                    </span>
                    {growth !== undefined && (
                        <span className={`text-sm font-medium ${growth >= 0 ? "text-success" : "text-destructive"}`}>
                            {growth >= 0 ? "+" : ""}{growth.toFixed(1)}% vs año anterior
                        </span>
                    )}
                </div>
                <div className="bg-primary/10 p-3 rounded-xl text-primary flex items-center justify-center [&>svg]:size-5">
                    {icon}
                </div>
            </CardContent>
        </Card>
    )
}