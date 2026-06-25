import { apiRequest } from "./client"
import type { FilterOptionsResponse, SellerOptionsResponse } from "../types"

export const fetchFilterOptions = async (): Promise<FilterOptionsResponse> =>
    apiRequest<FilterOptionsResponse>("/filters/options")

export const fetchSellerOptions = async (): Promise<SellerOptionsResponse> =>
    apiRequest<SellerOptionsResponse>("/filters/sellers")
