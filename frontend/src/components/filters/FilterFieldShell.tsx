import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

type FilterFieldShellProps = {
    label: string
    children: ReactNode
    className?: string
}

export default function FilterFieldShell({ label, children, className }: FilterFieldShellProps) {
    return (
        <div className={cn("flex flex-col gap-2", className)}>
            <label className="px-1 text-sm font-medium text-slate-600">{label}</label>
            {children}
        </div>
    )
}
