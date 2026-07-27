import { useState } from "react"
import { Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom"
import VentasTotales from "@/components/reports/VentasTotales"
import PorAsesor from "@/components/reports/PorAsesor"
import DetallePorAsesor from "@/components/reports/DetallePorAsesor"
import PorPais from "@/components/reports/PorPais"
import AppTopBar from "./components/layout/AppTopBar"
import LoginPage from "@/components/auth/LoginPage"
import SsoPage from "@/components/auth/SsoPage"
import { isAuthenticated } from "@/lib/auth"

function ProtectedLayout({ session }: { session: boolean }) {
    const location = useLocation()
    if (!session) return <Navigate to="/login" state={{ from: location }} replace />
    return (
        <div className="flex flex-col h-screen">
            <AppTopBar />
            <main className="flex-1 overflow-y-auto overflow-x-hidden bg-background">
                <Outlet />
            </main>
        </div>
    )
}

export default function App() {
    const [session] = useState<boolean>(() => isAuthenticated())

    return (
        <Routes>
            <Route path="/login" element={session ? <Navigate to="/ventas-totales" replace /> : <LoginPage />} />
            <Route path="/sso" element={<SsoPage />} />
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
