import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  analyticsApi,
  exceptionsApi,
  forecastsApi,
  insightsApi,
  inventoryApi,
  locationsApi,
  productsApi,
  salesApi,
  type ListProductsParams,
} from "@/api/endpoints";
import type { ProductCreateInput } from "@/types/api";

/**
 * Thin wrappers around React Query so components don't hand-roll query keys.
 * Keeping the keys here means invalidation stays consistent across the app.
 */

export const queryKeys = {
  products: (params: ListProductsParams) => ["products", params] as const,
  product: (id: number) => ["products", id] as const,
  locations: () => ["locations"] as const,
  sales: (productId?: number) => ["sales", productId] as const,
  inventory: (productId?: number) => ["inventory", productId] as const,
  forecastRuns: () => ["forecast-runs"] as const,
  exceptions: (params: Record<string, unknown>) => ["exceptions", params] as const,
  insights: (productId?: number) => ["insights", productId] as const,
  summary: () => ["analytics", "summary"] as const,
  timeline: (productId?: number) => ["analytics", "timeline", productId] as const,
  trends: () => ["analytics", "trends"] as const,
  categories: () => ["analytics", "categories"] as const,
  exceptionBreakdown: () => ["analytics", "exception-breakdown"] as const,
  productDetail: (id: number) => ["analytics", "product-detail", id] as const,
};

export function useProducts(params: ListProductsParams = {}) {
  return useQuery({ queryKey: queryKeys.products(params), queryFn: () => productsApi.list(params) });
}

export function useProduct(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.product(id ?? -1),
    queryFn: () => productsApi.get(id as number),
    enabled: id !== undefined,
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProductCreateInput) => productsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useLocations() {
  return useQuery({ queryKey: queryKeys.locations(), queryFn: locationsApi.list });
}

export function useDashboardSummary() {
  return useQuery({ queryKey: queryKeys.summary(), queryFn: analyticsApi.summary });
}

export function useTimeline(productId?: number) {
  return useQuery({
    queryKey: queryKeys.timeline(productId),
    queryFn: () => analyticsApi.timeline(productId),
  });
}

export function useTrends() {
  return useQuery({ queryKey: queryKeys.trends(), queryFn: () => analyticsApi.trends(8) });
}

export function useCategoryBreakdown() {
  return useQuery({ queryKey: queryKeys.categories(), queryFn: analyticsApi.categories });
}

export function useExceptionBreakdown() {
  return useQuery({ queryKey: queryKeys.exceptionBreakdown(), queryFn: analyticsApi.exceptionBreakdown });
}

export function useProductDetail(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.productDetail(id ?? -1),
    queryFn: () => analyticsApi.productDetail(id as number),
    enabled: id !== undefined,
  });
}

export function useExceptions(params: { status?: string; severity?: string; product_id?: number } = {}) {
  return useQuery({ queryKey: queryKeys.exceptions(params), queryFn: () => exceptionsApi.list(params) });
}

export function useUpdateExceptionStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => exceptionsApi.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useForecastRuns() {
  return useQuery({ queryKey: queryKeys.forecastRuns(), queryFn: () => forecastsApi.listRuns() });
}

export function useRunForecast() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: forecastsApi.runCycle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["forecast-runs"] });
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });
}

export function useUploadSalesCsv() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: salesApi.uploadCsv,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useUpsertInventory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: inventoryApi.upsert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory"] }),
  });
}

export function useGenerateInsight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: insightsApi.generate,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.insights(variables.product_id) });
    },
  });
}

export function useInsights(productId?: number) {
  return useQuery({
    queryKey: queryKeys.insights(productId),
    queryFn: () => insightsApi.list({ product_id: productId, limit: 5 }),
  });
}
