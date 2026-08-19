import { apiClient } from "@/api/client";
import type {
  CategoryBreakdown,
  DashboardSummary,
  DemandTimeline,
  ExceptionBreakdown,
  ForecastLine,
  ForecastPreview,
  ForecastRun,
  IngestionReport,
  Insight,
  InventoryRecord,
  Location,
  Page,
  PlanningException,
  Product,
  ProductCreateInput,
  ProductDetail,
  SalesRecord,
  TrendsResponse,
} from "@/types/api";

// --------------------------------------------------------------------------
// Products
// --------------------------------------------------------------------------
export interface ListProductsParams {
  category?: string;
  active?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}

export const productsApi = {
  list: (params: ListProductsParams = {}) =>
    apiClient.get<Page<Product>>("/products", { params }).then((r) => r.data),

  get: (id: number) => apiClient.get<Product>(`/products/${id}`).then((r) => r.data),

  create: (payload: ProductCreateInput) =>
    apiClient.post<Product>("/products", payload).then((r) => r.data),

  update: (id: number, payload: Partial<ProductCreateInput> & { active?: boolean }) =>
    apiClient.patch<Product>(`/products/${id}`, payload).then((r) => r.data),

  deactivate: (id: number) => apiClient.delete(`/products/${id}`),
};

// --------------------------------------------------------------------------
// Locations
// --------------------------------------------------------------------------
export const locationsApi = {
  list: () => apiClient.get<Location[]>("/locations").then((r) => r.data),
  create: (payload: { code: string; name: string; region: string; country?: string }) =>
    apiClient.post<Location>("/locations", payload).then((r) => r.data),
};

// --------------------------------------------------------------------------
// Sales history
// --------------------------------------------------------------------------
export const salesApi = {
  list: (params: { product_id?: number; limit?: number; offset?: number } = {}) =>
    apiClient.get<Page<SalesRecord>>("/sales", { params }).then((r) => r.data),

  uploadCsv: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<IngestionReport>("/sales/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  bulkUpsert: (
    records: {
      product_id: number;
      location_id?: number | null;
      period_start: string;
      units_sold: number;
    }[],
  ) => apiClient.post<IngestionReport>("/sales/bulk", { records }).then((r) => r.data),
};

// --------------------------------------------------------------------------
// Inventory
// --------------------------------------------------------------------------
export const inventoryApi = {
  list: (productId?: number) =>
    apiClient
      .get<InventoryRecord[]>("/inventory", { params: productId ? { product_id: productId } : {} })
      .then((r) => r.data),

  upsert: (payload: {
    product_id: number;
    location_id?: number | null;
    snapshot_date: string;
    on_hand_units: number;
    on_order_units: number;
    allocated_units: number;
  }) => apiClient.post<InventoryRecord>("/inventory", payload).then((r) => r.data),
};

// --------------------------------------------------------------------------
// Forecasts
// --------------------------------------------------------------------------
export const forecastsApi = {
  runCycle: (payload: {
    horizon: number;
    model: string;
    product_ids?: number[] | null;
    run_label?: string;
    detect_exceptions?: boolean;
  }) => apiClient.post<ForecastRun>("/forecasts/runs", payload).then((r) => r.data),

  listRuns: (limit = 20) =>
    apiClient.get<ForecastRun[]>("/forecasts/runs", { params: { limit } }).then((r) => r.data),

  getRun: (id: number) => apiClient.get<ForecastRun>(`/forecasts/runs/${id}`).then((r) => r.data),

  getRunLines: (id: number, productId?: number) =>
    apiClient
      .get<ForecastLine[]>(`/forecasts/runs/${id}/lines`, {
        params: productId ? { product_id: productId } : {},
      })
      .then((r) => r.data),

  preview: (productId: number, horizon: number, model: string) =>
    apiClient
      .get<ForecastPreview>(`/forecasts/preview/${productId}`, { params: { horizon, model } })
      .then((r) => r.data),
};

// --------------------------------------------------------------------------
// Exceptions
// --------------------------------------------------------------------------
export const exceptionsApi = {
  list: (params: { status?: string; severity?: string; exception_type?: string; product_id?: number } = {}) =>
    apiClient.get<PlanningException[]>("/exceptions", { params }).then((r) => r.data),

  updateStatus: (id: number, status: string) =>
    apiClient.patch<PlanningException>(`/exceptions/${id}`, { status }).then((r) => r.data),

  refreshForProduct: (productId: number) =>
    apiClient
      .post<PlanningException[]>(`/exceptions/products/${productId}/refresh`)
      .then((r) => r.data),
};

// --------------------------------------------------------------------------
// Insights
// --------------------------------------------------------------------------
export const insightsApi = {
  generate: (payload: { scope: "portfolio" | "product"; product_id?: number; persist?: boolean }) =>
    apiClient.post<Insight>("/insights", payload).then((r) => r.data),

  list: (params: { product_id?: number; limit?: number } = {}) =>
    apiClient.get<Insight[]>("/insights", { params }).then((r) => r.data),
};

// --------------------------------------------------------------------------
// Analytics
// --------------------------------------------------------------------------
export const analyticsApi = {
  summary: () => apiClient.get<DashboardSummary>("/analytics/summary").then((r) => r.data),

  timeline: (productId?: number) =>
    apiClient
      .get<DemandTimeline>("/analytics/timeline", { params: productId ? { product_id: productId } : {} })
      .then((r) => r.data),

  trends: (limit = 10) =>
    apiClient.get<TrendsResponse>("/analytics/trends", { params: { limit } }).then((r) => r.data),

  categories: () =>
    apiClient.get<CategoryBreakdown[]>("/analytics/categories").then((r) => r.data),

  exceptionBreakdown: () =>
    apiClient.get<ExceptionBreakdown[]>("/analytics/exceptions/breakdown").then((r) => r.data),

  productDetail: (productId: number) =>
    apiClient.get<ProductDetail>(`/analytics/products/${productId}`).then((r) => r.data),
};
