import { NavLink } from "react-router-dom"
import { BarChart2, Globe, Settings2, TableProperties, Users } from "lucide-react"
import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarHeader,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { useBaseCurrency, setStoredBaseCurrency } from "@/lib/reportPreferences"
import type { BaseCurrency } from "@/types"
import { useState } from "react"

const NAV_ITEMS = [
    { path: "/ventas-totales", label: "Ventas Totales", icon: <BarChart2 className="size-4" /> },
    { path: "/por-asesor", label: "Resultados por Asesor", icon: <Users className="size-4" /> },
    { path: "/detalle-asesor", label: "Detalle por Asesor", icon: <TableProperties className="size-4" /> },
    { path: "/por-pais", label: "Resultado por País", icon: <Globe className="size-4" /> },
]

export default function AppSidebar() {
    const baseCurrency = useBaseCurrency()
    const [isPreferencesOpen, setIsPreferencesOpen] = useState(false)
    const [draftCurrency, setDraftCurrency] = useState<BaseCurrency>(baseCurrency)

    return (
        <>
            <Sidebar>
                <SidebarHeader className="border-b border-sidebar-border px-4 py-4">
                    <div className="flex items-center gap-3">
                        <BarChart2 className="size-6 shrink-0" />
                        <span className="font-bold text-base tracking-wide">QC Analytics</span>
                    </div>
                </SidebarHeader>
                <SidebarContent className="p-2">
                    <SidebarMenu className="gap-1">
                        {NAV_ITEMS.map((item) => (
                            <SidebarMenuItem key={item.path}>
                                <NavLink to={item.path}>
                                    {({ isActive }) => (
                                        <SidebarMenuButton isActive={isActive} size="lg">
                                            {item.icon}
                                            <span>{item.label}</span>
                                        </SidebarMenuButton>
                                    )}
                                </NavLink>
                            </SidebarMenuItem>
                        ))}
                    </SidebarMenu>
                </SidebarContent>
                <SidebarFooter className="border-t border-sidebar-border px-3 py-4">
                    <div className="rounded-xl border border-sidebar-border/70 bg-sidebar-accent/40 px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-sidebar-foreground/60">
                            Base currency
                        </p>
                        <p className="mt-1 text-sm font-semibold text-sidebar-foreground">{baseCurrency}</p>
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        className="h-11 w-full justify-start rounded-xl border-sidebar-border/80 bg-sidebar text-sidebar-foreground shadow-none hover:bg-sidebar-accent"
                        onClick={() => {
                            setDraftCurrency(baseCurrency)
                            setIsPreferencesOpen(true)
                        }}
                    >
                        <Settings2 className="size-4" />
                        Preferencias
                    </Button>
                </SidebarFooter>
            </Sidebar>
            <Dialog open={isPreferencesOpen} onOpenChange={setIsPreferencesOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>Preferencias</DialogTitle>
                        <DialogDescription>
                            Elige la moneda base en la que se mostrarán los reportes y exportaciones.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid grid-cols-2 gap-3">
                        {(["MXN", "USD"] as BaseCurrency[]).map((currency) => (
                            <button
                                key={currency}
                                type="button"
                                className={[
                                    "rounded-2xl border px-4 py-4 text-left transition-colors",
                                    draftCurrency === currency
                                        ? "border-slate-900 bg-slate-900 text-white"
                                        : "border-slate-200 bg-slate-50 text-slate-900 hover:bg-slate-100",
                                ].join(" ")}
                                onClick={() => setDraftCurrency(currency)}
                            >
                                <p className="text-sm font-semibold">{currency}</p>
                                <p
                                    className={`mt-1 text-xs ${draftCurrency === currency ? "text-white/75" : "text-slate-500"}`}
                                >
                                    {currency === "MXN" ? "Pesos mexicanos" : "Dólares estadounidenses"}
                                </p>
                            </button>
                        ))}
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => setIsPreferencesOpen(false)}>
                            Cancelar
                        </Button>
                        <Button
                            type="button"
                            onClick={() => {
                                setStoredBaseCurrency(draftCurrency)
                                setIsPreferencesOpen(false)
                            }}
                        >
                            Guardar
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    )
}
