/** Shared display formatting so every page renders numbers/dates consistently. */

const numberFormatter = new Intl.NumberFormat("en-US");
const compactFormatter = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const currencyFormatter = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const monthFormatter = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" });

export function formatUnits(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return numberFormatter.format(Math.round(value));
}

export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return compactFormatter.format(value);
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return currencyFormatter.format(value);
}

export function formatPercent(value: number | null | undefined, opts: { signed?: boolean } = {}): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = opts.signed && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function formatMonth(isoDate: string | null | undefined): string {
  if (!isoDate) return "—";
  const date = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return isoDate;
  return monthFormatter.format(date);
}

export function formatDateTime(isoDate: string | null | undefined): string {
  if (!isoDate) return "—";
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return isoDate;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export const SEVERITY_LABEL: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
  dismissed: "Dismissed",
};

export const EXCEPTION_TYPE_LABEL: Record<string, string> = {
  demand_spike: "Demand Spike",
  demand_drop: "Demand Drop",
  stockout_risk: "Stockout Risk",
  excess_inventory: "Excess Inventory",
  forecast_anomaly: "Forecast Anomaly",
  new_product_volatility: "New Product Volatility",
};

export const MODEL_LABEL: Record<string, string> = {
  naive: "Naive",
  moving_average: "Moving Average",
  linear_trend: "Linear Trend",
  holt_linear: "Holt Linear",
  holt_winters: "Holt-Winters",
  seasonal_naive: "Seasonal Naive",
  auto: "Auto-select",
};
