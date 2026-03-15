import { ReactNode } from "react"
import { Card, CardContent } from "@/components/ui/card"

type KpiCardProps = {
    title: string
    icon: ReactNode
    value: string | number
    prefix?: string        // "$" para dinero
    suffix?: string        // "%" para porcentajes
    growth?: number        // para los Kpi's que aplican 
}

export default function KpiCard(props: KpiCardProps) {
    return (
        <Card>
            <CardContent className="flex justify-between items-start pt-6">
                <div className="flex flex-col gap-2">
                    <span className="text-muted-foreground text-sm font-medium">{props.title}</span>
                    <span className="text-3xl font-bold">
                        {props.prefix}
                        {typeof props.value === 'number' ? props.value.toLocaleString() : props.value}
                        {props.suffix}
                    </span>
                    {props.growth !== undefined && (
                        <span className={`text-sm font-medium ${props.growth >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                            {props.growth >= 0 ? '+' : ''}{props.growth.toFixed(1)}% vs año anterior
                        </span>
                    )}
                </div>
                <div className="bg-primary/10 p-3 rounded-xl text-primary flex items-center justify-center">
                    {props.icon}
                </div>
            </CardContent>
        </Card>
    )
}