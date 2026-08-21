import { getJson } from './http-client';

export interface OverviewTimelinePoint {
  readonly period_start: string;
  readonly actual_units: number | null;
  readonly forecast_units: number | null;
}

export interface OverviewRiskCounts {
  readonly stockout: number;
  readonly below_safety_stock: number;
  readonly healthy: number;
  readonly excess: number;
  readonly unavailable: number;
}

export interface OverviewException {
  readonly exception_id: string;
  readonly store_id: string;
  readonly store_name: string;
  readonly product_id: string;
  readonly sku: string;
  readonly product_name: string;
  readonly category: string;
  readonly exception_type:
    | 'potential_stockout'
    | 'below_safety_stock'
    | 'excess_inventory'
    | 'forecast_uncertainty'
    | 'forecast_bias';
  readonly severity: 'medium' | 'high' | 'critical';
  readonly priority_score: number;
  readonly title: string;
  readonly description: string;
  readonly metric_name: string;
  readonly metric_value: number;
  readonly threshold_value: number;
  readonly selected_model: string;
}

export interface PortfolioOverview {
  readonly run_id: string;
  readonly data_version: string;
  readonly training_cutoff: string;
  readonly horizon_months: number;
  readonly store_id: string | null;
  readonly store_name: string;
  readonly series_count: number;
  readonly recent_12_month_demand: number;
  readonly prior_12_month_demand: number;
  readonly demand_change: number | null;
  readonly forecast_horizon_demand: number;
  readonly median_series_wape: number | null;
  readonly median_series_mase: number | null;
  readonly median_absolute_bias: number | null;
  readonly weighted_interval_coverage: number | null;
  readonly risk_counts: OverviewRiskCounts;
  readonly timeline: readonly OverviewTimelinePoint[];
  readonly priority_exceptions: readonly OverviewException[];
}

export function getPortfolioOverview(
  runId: string,
  storeId: string,
  signal?: AbortSignal,
): Promise<PortfolioOverview> {
  const parameters = new URLSearchParams({ exception_limit: '10' });
  if (runId) parameters.set('run_id', runId);
  if (storeId) parameters.set('store_id', storeId);
  return getJson<PortfolioOverview>(`/api/v1/dashboard/summary?${parameters.toString()}`, signal);
}
