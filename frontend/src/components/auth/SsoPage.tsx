import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { setToken } from "@/lib/auth"
import config from "@/config"

export default function SsoPage() {
    const [params] = useSearchParams()
    const navigate = useNavigate()
    const token = params.get("token")
    const [error, setError] = useState<string | null>(token ? null : "Token no encontrado.")

    useEffect(() => {
        if (!token) return

        fetch(`${config.apiUrl}/auth/sso/exchange`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token }),
        })
            .then((res) => {
                if (!res.ok) throw new Error("invalid")
                return res.json()
            })
            .then(({ access_token }) => {
                setToken(access_token)
                // Full reload so App.tsx re-reads the token from localStorage
                window.location.replace("/ventas-totales")
            })
            .catch(() => setError("Sesión inválida o expirada. Por favor inicia sesión."))
    }, [token, navigate])

    if (error) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-muted/30">
                <div className="w-full max-w-sm rounded-3xl border border-border bg-card p-8 shadow-xl text-center">
                    <p className="text-sm text-destructive">{error}</p>
                </div>
            </div>
        )
    }

    return null
}
