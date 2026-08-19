/**
 * Types mirroring the backend's Pydantic schemas (see `backend/app/schemas`).
 * Kept as a single source of truth for the frontend so every component shares
 * the same shape as the API actually returns.
 */

export type ForecastModel =
  | "naive"
  | "moving_average"
  | "linear_trend"
  | "holt_linear"
  | "holt_winters"
  | "seasonal_naive"
  | "auto";

export type ExceptionType =
  | "demand_spike"
  | "demand_drop"
  | "stockout_risk"
  | "excess_inventory"
  | "forecast_anomaly"
  | "new_product_volatility";

export type ExceptionSeverity = "low" | "medium" | "high" | "critical";
export type ExceptionStatus = "open" | "acknowledged" | "resolved" | "dismissed";
export type InsightScope = "portfolio" | "product" | "exception";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Product {
  id: number;
  sku: string;
  name: string;
  category: string;
  subcategory: string | null;
  unit_of_measure: string;
  unit_cost: number | null;
  unit_price: number | null;
  lead_time_days: number;
  safety_stock_units: number;
  reorder_point_units: number | null;
  active: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductCreateInput {
  sku: string;
  name: string;
  category: string;
  subcategory?: string | null;
  unit_of_measure?: string;
  unit_cost?: number | null;
  unit_price?: number | null;
  lead_time_days?: number;
  safety_stock_units?: number;
  reorder_point_units?: number | null;
  description?: string | null;
}

export interface Location {
  id: number;
  code: string;
  name: string;
  region: string;
  country: string | null;
  active: boolean;
  created_at: string;
}

export interface SalesRecord {
  id: number;
  product_id: number;
  location_id: number | null;
  period_start: string;
  units_sold: number;
  revenue: number | null;
  channel: string | null;
  source: string;
}

export interface InventoryRecord {
  id: number;
  product_id: number;
  location_id: number | null;
  snapshot_date: string;
  on_hand_units: number;
  on_order_units: number;
  allocated_units: number;
  available_units: number;
}

export interface ForecastRun {
  id: number;
  run_label: string;
  requested_model: string;
  horizon_periods: number;
  products_forecasted: number;
  products_skipped: number;
  started_at: string;
  completed_at: string | null;
  notes: { skipped?: { product_id: number; sku: string; reason: string }[] } | null;
}

export interface ForecastLine {
  id: number;
  run_id: number;
  product_id: number;
  period_start: string;
  forecast_units: number;
  lower_bound_units: number | null;
  upper_bound_units: number | null;
  model_used: string;
  mape: number | null;
  wape: number | null;
  rmse: number | null;
  confidence_level: number;
}

export interface ForecastPoint {
  period_start: string;
  forecast_units: number;
  lower_bound_units: number;
  upper_bound_units: number;
}

export interface ForecastPreview {
  product_id: number;
  sku: string;
  name: string;
  model_used: string;
  history_periods: number;
  confidence_level: number;
  mape: number | null;
  wape: number | null;
  rmse: number | null;
  candidates_evaluated: Record<string, number | null>;
  points: ForecastPoint[];
  total_forecast_units: number;
}

export interface PlanningException {
  id: number;
  product_id: number;
  exception_type: ExceptionType;
  severity: ExceptionSeverity;
  status: ExceptionStatus;
  detected_for_period: string;
  title: string;
  message: string;
  recommendation: string | null;
  metric_value: number | null;
  baseline_value: number | null;
  deviation_pct: number | null;
  context: Record<string, unknown> | null;
  created_at: string;
  product_sku?: string | null;
  product_name?: string | null;
}

export interface Insight {
  id: number;
  scope: InsightScope;
  product_id: number | null;
  headline: string;
  summary: string;
  recommendations: string[] | null;
  generated_by: string;
  model_name: string | null;
  created_at: string;
}

export interface DashboardSummary {
  active_products: number;
  history_total_units: number;
  forecast_total_units: number;
  forecast_periods: number;
  demand_growth_pct: number | null;
  open_exceptions: number;
  critical_exceptions: number;
  average_wape: number | null;
  latest_run_id: number | null;
}

export interface HistoryPoint {
  period_start: string;
  units: number;
}

export interface ForecastSeriesPoint {
  period_start: string;
  forecast_units: number;
  lower_bound_units: number | null;
  upper_bound_units: number | null;
}

export interface DemandTimeline {
  history: HistoryPoint[];
  forecast: ForecastSeriesPoint[];
  run_id: number | null;
}

export interface TrendEntry {
  product_id: number;
  sku: string;
  name: string;
  category: string;
  recent_units: number;
  prior_units: number;
  growth_pct: number;
}

export interface TrendsResponse {
  growing: TrendEntry[];
  declining: TrendEntry[];
  window_periods: number;
}

export interface CategoryBreakdown {
  category: string;
  history_units: number;
  forecast_units: number;
}

export interface ExceptionBreakdown {
  exception_type: string;
  severity: string;
  count: number;
}

export interface ProductDetail {
  product: Product;
  timeline: DemandTimeline;
  exceptions: PlanningException[];
  history_total_units: number;
  forecast_total_units: number;
  model_used: string | null;
  wape: number | null;
  mape: number | null;
}

export interface IngestionReport {
  rows_received: number;
  rows_imported: number;
  rows_updated: number;
  rows_rejected: number;
  errors: { line: number; error: string }[];
  error_count: number;
  unknown_skus: string[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
