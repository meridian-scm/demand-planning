import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
import type { DashboardSummary, DemandTimeline, Page, PlanningException, Product } from "@/types/api";

const BASE = "http://localhost:8000/api/v1";

export const sampleProduct: Product = {
  id: 1,
  sku: "SKU-1001",
  name: "Sparkling Water",
  category: "Beverages",
  subcategory: null,
  unit_of_measure: "EA",
  unit_cost: 5,
  unit_price: 9.5,
  lead_time_days: 30,
  safety_stock_units: 50,
  reorder_point_units: null,
  active: true,
  description: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

export const sampleSummary: DashboardSummary = {
  active_products: 25,
  history_total_units: 145044,
  forecast_total_units: 42484.39,
  forecast_periods: 6,
  demand_growth_pct: 7.77,
  open_exceptions: 7,
  critical_exceptions: 2,
  average_wape: 14.67,
  latest_run_id: 1,
};

export const sampleTimeline: DemandTimeline = {
  history: [
    { period_start: "2025-01-01", units: 100 },
    { period_start: "2025-02-01", units: 120 },
  ],
  forecast: [{ period_start: "2025-03-01", forecast_units: 140, lower_bound_units: 120, upper_bound_units: 160 }],
  run_id: 1,
};

export const sampleException: PlanningException = {
  id: 1,
  product_id: 1,
  exception_type: "stockout_risk",
  severity: "critical",
  status: "open",
  detected_for_period: "2025-03-01",
  title: "Stockout risk on Sparkling Water",
  message: "Available stock covers only 0.5 periods of forecast demand.",
  recommendation: "Expedite replenishment.",
  metric_value: 0.5,
  baseline_value: 1.0,
  deviation_pct: -50,
  context: null,
  created_at: "2025-03-01T00:00:00Z",
  product_sku: "SKU-1001",
  product_name: "Sparkling Water",
};

export const handlers = [
  http.get(`${BASE}/products`, () => {
    const page: Page<Product> = { items: [sampleProduct], total: 1, limit: 50, offset: 0 };
    return HttpResponse.json(page);
  }),
  http.get(`${BASE}/products/:id`, () => HttpResponse.json(sampleProduct)),
  http.get(`${BASE}/analytics/summary`, () => HttpResponse.json(sampleSummary)),
  http.get(`${BASE}/analytics/timeline`, () => HttpResponse.json(sampleTimeline)),
  http.get(`${BASE}/analytics/trends`, () =>
    HttpResponse.json({ growing: [], declining: [], window_periods: 3 }),
  ),
  http.get(`${BASE}/analytics/categories`, () => HttpResponse.json([])),
  http.get(`${BASE}/analytics/exceptions/breakdown`, () => HttpResponse.json([])),
  http.get(`${BASE}/analytics/products/:id`, () =>
    HttpResponse.json({
      product: sampleProduct,
      timeline: sampleTimeline,
      exceptions: [sampleException],
      history_total_units: 220,
      forecast_total_units: 140,
      model_used: "linear_trend",
      wape: 12.5,
      mape: 11.0,
    }),
  ),
  http.get(`${BASE}/exceptions`, () => HttpResponse.json([sampleException])),
  http.get(`${BASE}/insights`, () => HttpResponse.json([])),
  http.get(`${BASE}/forecasts/runs`, () => HttpResponse.json([])),
];

export const server = setupServer(...handlers);
