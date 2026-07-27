import { useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { setToken } from "@/lib/auth"
import config from "@/config"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export default function LoginPage({ onLogin }: { onLogin: () => void }) {
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)
    const navigate = useNavigate()
    const location = useLocation()
    const from = (location.state as { from?: Location })?.from?.pathname ?? "/ventas-totales"

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)
        setLoading(true)
        try {
            const res = await fetch(`${config.apiUrl}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: email, password }),
            })
            if (!res.ok) {
                setError("Correo o contraseña incorrectos.")
            } else {
                const { access_token } = await res.json()
                setToken(access_token)
                onLogin()
                navigate(from, { replace: true })
            }
        } catch {
            setError("Error de conexión. Intenta de nuevo.")
        }
        setLoading(false)
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-muted/30">
            <div className="w-full max-w-sm rounded-3xl border border-border bg-card p-8 shadow-xl">
                <h1 className="mb-1 text-2xl font-semibold tracking-tight text-slate-900">QC Analytics</h1>
                <p className="mb-6 text-sm text-muted-foreground">Inicia sesión para continuar.</p>

                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                    <Input
                        type="email"
                        placeholder="Correo electrónico"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        autoComplete="email"
                        className="h-11 rounded-2xl"
                    />
                    <Input
                        type="password"
                        placeholder="Contraseña"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        autoComplete="current-password"
                        className="h-11 rounded-2xl"
                    />

                    {error ? <p className="text-sm text-destructive">{error}</p> : null}

                    <Button type="submit" className="h-11 rounded-2xl" disabled={loading}>
                        {loading ? "Entrando..." : "Entrar"}
                    </Button>
                </form>
            </div>
        </div>
    )
}
