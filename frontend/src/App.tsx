import { useEffect, useState } from "react"
import { Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom"
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import VentasTotales from "@/components/reports/VentasTotales"
import PorAsesor from "@/components/reports/PorAsesor"
import DetallePorAsesor from "@/components/reports/DetallePorAsesor"
import PorPais from "@/components/reports/PorPais"
import AppSidebar from "./components/layout/AppSideBar"
import LoginPage from "@/components/auth/LoginPage"
import { supabase } from "@/lib/supabase"
import type { Session } from "@supabase/supabase-js"

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

function ProtectedLayout({ session }: { session: Session | null | undefined }) {
    const location = useLocation()
    if (session === undefined) return null
    if (!session) return <Navigate to="/login" state={{ from: location }} replace />
    return (
        <SidebarProvider>
            <AppSidebar />
            <SidebarInset>
                <header className="flex items-center gap-3 px-4 py-3 bg-[hsl(var(--topbar))] text-white shadow-sm">
                    <SidebarTrigger className="text-white hover:bg-white/10" />
                    <PageTitle />
                </header>
                <main className="flex-1 overflow-y-auto overflow-x-hidden">
                    <Outlet />
                </main>
            </SidebarInset>
        </SidebarProvider>
    )
}

export default function App() {
    const [session, setSession] = useState<Session | null | undefined>(undefined)

    useEffect(() => {
        supabase.auth.getSession().then(({ data }) => setSession(data.session))
        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
            setSession(session)
        })
        return () => subscription.unsubscribe()
    }, [])

    return (
        <Routes>
            <Route path="/login" element={
                session ? <Navigate to="/ventas-totales" replace /> : <LoginPage />
            } />
            <Route element={<ProtectedLayout session={session} />}>
                <Route path="/" element={<Navigate to="/ventas-totales" replace />} />
                <Route path="/ventas-totales" element={<VentasTotales />} />
                <Route path="/por-asesor" element={<PorAsesor />} />
                <Route path="/detalle-asesor" element={<DetallePorAsesor />} />
                <Route path="/por-pais" element={<PorPais />} />
            </Route>
        </Routes>
    )
}
