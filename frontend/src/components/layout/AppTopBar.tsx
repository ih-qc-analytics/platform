import { useState } from "react"
import { NavLink } from "react-router-dom"
import { BarChart2, Globe, TableProperties, Users, User, Check, LogOut, Settings2 } from "lucide-react"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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
import { clearToken } from "@/lib/auth"
import type { BaseCurrency } from "@/types"

const NAV_ITEMS = [
    { path: "/ventas-totales", label: "Ventas Totales", icon: <BarChart2 className="size-4" /> },
    { path: "/por-asesor", label: "Resultados por Asesor", icon: <Users className="size-4" /> },
    { path: "/detalle-asesor", label: "Detalle por Asesor", icon: <TableProperties className="size-4" /> },
    { path: "/por-pais", label: "Resultado por País", icon: <Globe className="size-4" /> },
]

export default function AppTopBar() {
    const baseCurrency = useBaseCurrency()
    const [isPreferencesOpen, setIsPreferencesOpen] = useState(false)
    const [draftCurrency, setDraftCurrency] = useState<BaseCurrency>(baseCurrency)

    const openPreferences = () => {
        setDraftCurrency(baseCurrency)
        setIsPreferencesOpen(true)
    }

    return (
        <>
            <header className="relative flex items-center h-16 px-6 bg-[hsl(var(--topbar))] text-white shadow-sm shrink-0">
                {/* Brand — absolutely positioned left */}
                <div className="absolute left-6 flex items-center gap-2 shrink-0">
                    <BarChart2 className="size-5" />
                    <span className="font-bold tracking-wide">QC Analytics</span>
                </div>

                {/* Nav links — truly centered */}
                <nav className="flex items-center gap-1 mx-auto">
                    {NAV_ITEMS.map((item) => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            className={({ isActive }) =>
                                [
                                    "flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors",
                                    isActive
                                        ? "bg-white/15 text-white"
                                        : "text-white/70 hover:bg-white/10 hover:text-white",
                                ].join(" ")
                            }
                        >
                            {item.icon}
                            {item.label}
                        </NavLink>
                    ))}
                </nav>

                {/* User profile dropdown — absolutely positioned right */}
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <button
                            type="button"
                            className="absolute right-6 flex items-center gap-2 px-3 py-2 rounded-md font-medium text-white/80 hover:bg-white/10 hover:text-white transition-colors"
                        >
                            <User className="size-4" />
                            Usuario
                        </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-52">
                        <DropdownMenuLabel>Perfil de usuario</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={openPreferences} className="justify-between">
                            <span>Moneda base: {baseCurrency}</span>
                            <Check className="size-4 text-muted-foreground" />
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={openPreferences}>
                            <Settings2 className="size-4 mr-2" />
                            Preferencias
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                            onClick={() => {
                                clearToken()
                                window.location.replace("/login")
                            }}
                            className="text-destructive focus:text-destructive"
                        >
                            <LogOut className="size-4 mr-2" />
                            Cerrar sesión
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </header>

            {/* Preferences dialog */}
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
