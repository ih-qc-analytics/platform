/// <reference types="vite/client" />

const config = {
    apiUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
} as const

export default config