import { getJson } from './http-client';

export interface ForecastRun {
  readonly run_id: string;
  readonly data_version: string;
  readonly status: 'completed' | 'partial' | 'failed';
  readonly created_at: string;
  readonly training_cutoff: string;
  readonly horizon_months: number;
  readonly interval_level: number;
  readonly series_count: number;
  readonly successful_series_count: number;
  readonly failed_series_count: number;
  readonly evaluation_count: number;
  readonly forecast_count: number;
}

export interface ForecastSeriesResult {
  readonly run_id: string;
  readonly store_id: string;
  readonly product_id: string;
  readonly sku: string;
  readonly product_name: string;
  readonly category: string;
  readonly status: 'succeeded' | 'failed';
  readonly selected_model: string | null;
  readonly wape: number | null;
  readonly mase: number | null;
  readonly rmse: number | null;
  readonly bias: number | null;
  readonly interval_coverage: number | null;
  readonly validation_points: number | null;
  readonly failure_detail: string | null;
}

export interface StoredModelEvaluation {
  readonly run_id: string;
  readonly store_id: string;
  readonly product_id: string;
  readonly sku: string;
  readonly model_name: string;
  readonly selected: boolean;
  readonly status: 'succeeded' | 'failed';
  readonly validation_origins: number;
  readonly wape: number | null;
  readonly mase: number | null;
  readonly rmse: number | null;
  readonly bias: number | null;
  readonly interval_coverage: number | null;
  readonly validation_points: number | null;
  readonly failure_detail: string | null;
}

export interface StoredForecast {
  readonly run_id: string;
  readonly store_id: string;
  readonly product_id: string;
  readonly sku: string;
  readonly period_start: string;
  readonly forecast_value: number;
  readonly lower_bound: number;
  readonly upper_bound: number;
  readonly horizon: number;
  readonly selected_model: string;
  readonly training_cutoff: string;
}

export function listForecastRuns(signal?: AbortSignal): Promise<ForecastRun[]> {
  return getJson<ForecastRun[]>('/api/v1/forecast-runs', signal);
}

export function listForecastSeries(
  runId: string,
  storeId: string,
  query: string,
  signal?: AbortSignal,
): Promise<ForecastSeriesResult[]> {
  const parameters = new URLSearchParams({ query, limit: '100' });
  if (storeId) parameters.set('store_id', storeId);
  return getJson<ForecastSeriesResult[]>(
    `/api/v1/forecast-runs/${encodeURIComponent(runId)}/series?${parameters.toString()}`,
    signal,
  );
}

export function getStoredEvaluations(
  runId: string,
  storeId: string,
  productId: string,
  signal?: AbortSignal,
): Promise<StoredModelEvaluation[]> {
  const parameters = new URLSearchParams({ store_id: storeId, product_id: productId });
  return getJson<StoredModelEvaluation[]>(
    `/api/v1/forecast-runs/${encodeURIComponent(runId)}/evaluations?${parameters.toString()}`,
    signal,
  );
}

export function getStoredForecasts(
  runId: string,
  storeId: string,
  productId: string,
  signal?: AbortSignal,
): Promise<StoredForecast[]> {
  const parameters = new URLSearchParams({
    run_id: runId,
    store_id: storeId,
    product_id: productId,
  });
  return getJson<StoredForecast[]>(`/api/v1/forecasts?${parameters.toString()}`, signal);
}
