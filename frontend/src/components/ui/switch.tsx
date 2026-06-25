import * as React from "react"

import { cn } from "@/lib/utils"

type SwitchProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> & {
    checked?: boolean
    onCheckedChange?: (checked: boolean) => void
}

const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
    ({ className, checked = false, onCheckedChange, ...props }, ref) => (
        <button
            ref={ref}
            type="button"
            role="switch"
            aria-checked={checked}
            data-state={checked ? "checked" : "unchecked"}
            className={cn(
                "peer inline-flex h-8 w-14 shrink-0 items-center rounded-full border border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
                checked ? "bg-slate-900" : "bg-slate-300",
                className,
            )}
            onClick={() => onCheckedChange?.(!checked)}
            {...props}
        >
            <span
                className={cn(
                    "pointer-events-none block size-6 rounded-full bg-white shadow-sm ring-0 transition-transform",
                    checked ? "translate-x-7" : "translate-x-1",
                )}
            />
        </button>
    ),
)
Switch.displayName = "Switch"

export { Switch }
