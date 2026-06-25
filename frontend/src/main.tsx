import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider, QueryCache } from "@tanstack/react-query"
import "./index.css"
import App from "./App.tsx"

const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: 1 } },
    queryCache: new QueryCache({
        onError: (error, query) => {
            console.error("Query failed:", query.queryKey, error)
        },
    }),
})

createRoot(document.getElementById("root")!).render(
    <StrictMode>
        <BrowserRouter>
            <QueryClientProvider client={queryClient}>
                <App />
            </QueryClientProvider>
        </BrowserRouter>
    </StrictMode>,
)
