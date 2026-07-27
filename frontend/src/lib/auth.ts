const TOKEN_KEY = "auth_token"

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY)

export const setToken = (token: string): void => localStorage.setItem(TOKEN_KEY, token)

export const clearToken = (): void => localStorage.removeItem(TOKEN_KEY)

export const isAuthenticated = (): boolean => {
    const token = getToken()
    if (!token) return false
    try {
        const payload = JSON.parse(atob(token.split(".")[1]))
        return typeof payload.exp === "number" && payload.exp * 1000 > Date.now()
    } catch {
        return false
    }
}
