import config from "../config"
import { getStoredBaseCurrency } from "@/lib/reportPreferences"
import { supabase } from "@/lib/supabase"

export class ApiError extends Error {
    constructor(
        public readonly status: number,
        public readonly statusText: string,
    ) {
        super(`Request failed: ${status} ${statusText}`)
    }
}

type ResponseType = "json" | "blob"

type ApiRequestOptions = Omit<RequestInit, "body"> & {
    body?: unknown
    responseType?: ResponseType
}

const buildHeaders = async (headers?: HeadersInit, hasJsonBody = false) => {
    const nextHeaders = new Headers(headers)
    nextHeaders.set("X-Base-Currency", getStoredBaseCurrency())
    if (hasJsonBody && !nextHeaders.has("Content-Type")) {
        nextHeaders.set("Content-Type", "application/json")
    }
    const { data } = await supabase.auth.getSession()
    if (data.session?.access_token) {
        nextHeaders.set("Authorization", `Bearer ${data.session.access_token}`)
    }
    return nextHeaders
}

export const apiRequest = async <T>(
    path: string,
    { body, headers, responseType = "json", ...init }: ApiRequestOptions = {},
): Promise<T> => {
    const response = await apiResponse(path, { body, headers, ...init })

    if (responseType === "blob") {
        return (await response.blob()) as T
    }

    return (await response.json()) as T
}

export const apiResponse = async (
    path: string,
    { body, headers, ...init }: Omit<ApiRequestOptions, "responseType"> = {},
) => {
    const hasJsonBody = body !== undefined && !(body instanceof FormData)
    const response = await fetch(`${config.apiUrl}${path}`, {
        ...init,
        headers: await buildHeaders(headers, hasJsonBody),
        body: body === undefined ? undefined : hasJsonBody ? JSON.stringify(body) : (body as BodyInit),
    })

    if (!response.ok) {
        if (response.status === 401) {
            await supabase.auth.signOut()
            window.location.replace("/login")
        }
        throw new ApiError(response.status, response.statusText)
    }

    return response
}
