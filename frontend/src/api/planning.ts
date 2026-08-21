import { getJson, postJson } from './http-client';

export interface Store {
  readonly store_id: string;
  readonly store_code: string;
  readonly store_name: string;
  readonly city: string;
  readonly region: string;
  readonly country: string;
  readonly timezone: string;
}

export interface Product {
  readonly product_id: string;
  readonly sku: string;
  readonly product_name: string;
  readonly category: string;
  readonly subcategory: string;
  readonly brand: string;
  readonly unit_cost: string;
  readonly unit_price: string;
}

export interface DemandPoint {
  readonly period_start: string;
  readonly demand_units: number;
}

export interface DemandSeries {
  readonly store_id: string;
  readonly product: Product;
  readonly policy: {
    readonly lead_time_days: number;
    readonly safety_stock: number;
    readonly reorder_point: number;
    readonly minimum_order_quantity: number;
    readonly order_multiple: number;
    readonly service_level_target: number;
  };
  readonly observations: readonly DemandPoint[];
  readonly summary: {
    readonly period_start: string;
    readonly period_end: string;
    readonly total_units: number;
    readonly average_monthly_units: number;
    readonly minimum_monthly_units: number;
    readonly maximum_monthly_units: number;
    readonly zero_demand_months: number;
  };
}

export interface ForecastMetrics {
  readonly wape: number | null;
  readonly mase: number | null;
  readonly rmse: number;
  readonly bias: number | null;
  readonly interval_coverage: number | null;
  readonly validation_points: number;
}

export interface ModelEvaluation {
  readonly model_name: string;
  readonly status: 'succeeded' | 'failed';
  readonly validation_origins: number;
  readonly metrics: ForecastMetrics | null;
  readonly failure_detail: string | null;
}

export interface ForecastPoint {
  readonly period_start: string;
  readonly forecast_value: number;
  readonly lower_bound: number;
  readonly upper_bound: number;
  readonly horizon: number;
}

export interface ForecastPreview {
  readonly forecast_id: string;
  readonly store_id: string;
  readonly product: Product;
  readonly selected_model: string;
  readonly training_cutoff: string;
  readonly horizon_months: number;
  readonly interval_level: number;
  readonly intermittent_demand: boolean;
  readonly validation_origins: number;
  readonly selected_metrics: ForecastMetrics;
  readonly evaluations: readonly ModelEvaluation[];
  readonly forecasts: readonly ForecastPoint[];
}

export interface ForecastPreviewRequest {
  readonly store_id: string;
  readonly product_id: string;
  readonly horizon_months: number;
  readonly interval_level: number;
}

export interface DemandSignal {
  readonly signal_id: string;
  readonly store_id: string;
  readonly product_id: string;
  readonly sku: string;
  readonly signal_type: 'trend' | 'volatility' | 'seasonality' | 'anomaly';
  readonly direction:
    'growing' | 'declining' | 'stable' | 'volatile' | 'seasonal' | 'spike' | 'drop';
  readonly severity: 'info' | 'watch' | 'warning';
  readonly period_start: string | null;
  readonly title: string;
  readonly description: string;
  readonly metric_name: string;
  readonly metric_value: number;
  readonly baseline_value: number | null;
  readonly threshold_value: number;
  readonly evidence: Readonly<Record<string, string | number>>;
}

export interface InventoryPosition {
  readonly store_id: string;
  readonly product_id: string;
  readonly sku: string;
  readonly snapshot_at: string;
  readonly on_hand: number;
  readonly allocated: number;
  readonly on_order: number;
  readonly on_order_due_within_lead_time: number;
  readonly next_expected_receipt_at: string | null;
  readonly lead_time_days: number;
  readonly safety_stock: number;
}

export interface InventoryRisk {
  readonly risk_id: string;
  readonly store_id: string;
  readonly product_id: string;
  readonly sku: string;
  readonly classification: 'stockout' | 'below_safety_stock' | 'healthy' | 'excess';
  readonly severity: 'info' | 'watch' | 'warning';
  readonly snapshot_at: string;
  readonly replenishment_arrival_at: string;
  readonly available_inventory: number;
  readonly on_order_due_within_lead_time: number;
  readonly forecast_demand_during_lead_time: number;
  readonly projected_inventory: number;
  readonly safety_stock: number;
  readonly coverage_months: number | null;
  readonly excess_coverage_threshold_months: number;
  readonly selected_model: string;
  readonly forecast_id: string;
  readonly training_cutoff: string;
  readonly forecast_horizon_months: number;
}

export interface PlanningException {
  readonly exception_id: string;
  readonly store_id: string;
  readonly product_id: string;
  readonly sku: string;
  readonly exception_type:
    | 'potential_stockout'
    | 'below_safety_stock'
    | 'excess_inventory'
    | 'demand_spike'
    | 'demand_decline'
    | 'forecast_uncertainty'
    | 'forecast_bias';
  readonly severity: 'medium' | 'high' | 'critical';
  readonly priority_score: number;
  readonly status: 'open' | 'acknowledged' | 'resolved' | 'dismissed';
  readonly relevant_period: string;
  readonly title: string;
  readonly description: string;
  readonly metric_name: string;
  readonly metric_value: number;
  readonly threshold_value: number;
  readonly evidence: Readonly<Record<string, string | number>>;
  readonly related_signal_id: string | null;
  readonly related_risk_id: string | null;
  readonly related_forecast_id: string | null;
  readonly created_at: string;
}

export function listStores(signal?: AbortSignal): Promise<Store[]> {
  return getJson<Store[]>('/api/v1/stores', signal);
}

export function searchProducts(
  storeId: string,
  query: string,
  signal?: AbortSignal,
): Promise<Product[]> {
  const parameters = new URLSearchParams({ store_id: storeId, query, limit: '50' });
  return getJson<Product[]>(`/api/v1/products?${parameters.toString()}`, signal);
}

export function getDemandSeries(
  storeId: string,
  productId: string,
  signal?: AbortSignal,
): Promise<DemandSeries> {
  const parameters = new URLSearchParams({ store_id: storeId, product_id: productId });
  return getJson<DemandSeries>(`/api/v1/demand/series?${parameters.toString()}`, signal);
}

export function getDemandSignals(
  storeId: string,
  productId: string,
  signal?: AbortSignal,
): Promise<DemandSignal[]> {
  const parameters = new URLSearchParams({ store_id: storeId, product_id: productId });
  return getJson<DemandSignal[]>(`/api/v1/signals?${parameters.toString()}`, signal);
}

export function getInventoryPosition(
  storeId: string,
  productId: string,
  signal?: AbortSignal,
): Promise<InventoryPosition> {
  const parameters = new URLSearchParams({ store_id: storeId, product_id: productId });
  return getJson<InventoryPosition>(`/api/v1/inventory/positions?${parameters.toString()}`, signal);
}

export function getInventoryRisk(
  storeId: string,
  productId: string,
  signal?: AbortSignal,
): Promise<InventoryRisk> {
  const parameters = new URLSearchParams({ store_id: storeId, product_id: productId });
  return getJson<InventoryRisk>(`/api/v1/inventory/risks?${parameters.toString()}`, signal);
}

export function getPlanningExceptions(
  storeId: string,
  productId: string,
  signal?: AbortSignal,
): Promise<PlanningException[]> {
  const parameters = new URLSearchParams({ store_id: storeId, product_id: productId });
  return getJson<PlanningException[]>(`/api/v1/exceptions?${parameters.toString()}`, signal);
}

export function createForecastPreview(request: ForecastPreviewRequest): Promise<ForecastPreview> {
  return postJson<ForecastPreviewRequest, ForecastPreview>('/api/v1/forecast-previews', request);
}
