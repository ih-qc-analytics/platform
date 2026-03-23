import { Routes, Route, Navigate, useLocation } from "react-router-dom"
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import VentasTotales from "@/components/reports/VentasTotales"
import AppSidebar from "./components/layout/AppSideBar"

const TITLES: Record<string, string> = {
    "/ventas-totales":  "Ventas Totales",
    "/por-asesor":      "Resultados por Asesor",
    "/detalle-asesor":  "Detalle por Asesor",
    "/por-pais":        "Resultado por País",
}

function PageTitle() {
    const { pathname } = useLocation()
    return <span className="font-semibold text-sm">{TITLES[pathname] ?? "QC Analytics"}</span>
}

export default function App() {
    return (
        <SidebarProvider>
            <AppSidebar />
            <SidebarInset>
                <header className="flex items-center gap-3 px-4 py-3 bg-[hsl(var(--topbar))] text-white shadow-sm">
                    <SidebarTrigger className="text-white hover:bg-white/10" />
                    <PageTitle />
                </header>
                <main className="flex-1 overflow-auto">
                    <Routes>
                        <Route path="/" element={<Navigate to="/ventas-totales" replace />} />
                        <Route path="/ventas-totales" element={<VentasTotales />} />
                        <Route path="/por-asesor" element={<div className="p-6 text-muted-foreground text-sm">Próximamente — Por Asesor</div>} />
                        <Route path="/detalle-asesor" element={<div className="p-6 text-muted-foreground text-sm">Próximamente — Detalle por Asesor</div>} />
                        <Route path="/por-pais" element={<div className="p-6 text-muted-foreground text-sm">Próximamente — Resultado por País</div>} />
                    </Routes>
                </main>
            </SidebarInset>
        </SidebarProvider>
    )
}