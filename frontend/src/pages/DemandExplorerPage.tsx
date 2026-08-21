import { useMutation, useQuery } from '@tanstack/react-query';
import { useDeferredValue, useState } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  createForecastPreview,
  getDemandSignals,
  getDemandSeries,
  getInventoryPosition,
  getInventoryRisk,
  listStores,
  searchProducts,
  type DemandSeries,
  type DemandSignal,
  type ForecastPreview,
  type InventoryRisk,
} from '../api/planning';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

const integerFormatter = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 0 });
const decimalFormatter = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 2 });
const percentageFormatter = new Intl.NumberFormat('en-CA', {
  maximumFractionDigits: 1,
  style: 'percent',
});

interface ChartPoint {
  readonly period_start: string;
  readonly actual: number | null;
  readonly forecast: number | null;
  readonly interval: [number, number] | null;
}

function formatMonth(value: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatTooltipMonth(value: unknown): string {
  return typeof value === 'string' ? formatMonth(value) : '';
}

function formatTooltipValue(value: unknown, name: unknown): [string, string] {
  if (Array.isArray(value)) {
    const range = value as unknown[];
    if (typeof range[0] === 'number' && typeof range[1] === 'number') {
      return [
        `${integerFormatter.format(range[0])}–${integerFormatter.format(range[1])} units`,
        'Prediction interval',
      ];
    }
  }
  return [
    `${integerFormatter.format(typeof value === 'number' ? value : Number(value))} units`,
    typeof name === 'string' ? name : 'Demand',
  ];
}

function formatMetric(value: number | null, kind: 'percentage' | 'decimal'): string {
  if (value === null) return 'Not defined';
  return kind === 'percentage' ? percentageFormatter.format(value) : decimalFormatter.format(value);
}

function formatSignalMetric(signal: DemandSignal): string {
  if (signal.signal_type === 'trend') return percentageFormatter.format(signal.metric_value);
  return decimalFormatter.format(signal.metric_value);
}

function signalEvidence(signal: DemandSignal): readonly [string, string][] {
  if (signal.signal_type === 'trend') {
    return [
      [
        'Recent monthly average',
        `${decimalFormatter.format(Number(signal.evidence.recent_12_month_average))} units`,
      ],
      [
        'Prior monthly average',
        `${decimalFormatter.format(Number(signal.evidence.prior_12_month_average))} units`,
      ],
    ];
  }
  if (signal.signal_type === 'anomaly') {
    return [
      [
        'Observed demand',
        `${integerFormatter.format(Number(signal.evidence.observed_demand))} units`,
      ],
      [
        'Trailing baseline',
        `${decimalFormatter.format(Number(signal.evidence.trailing_12_month_median))} units`,
      ],
    ];
  }
  if (signal.signal_type === 'volatility') {
    return [
      [
        'Recent monthly average',
        `${decimalFormatter.format(Number(signal.evidence.mean_demand))} units`,
      ],
      [
        'Robust variation',
        `${decimalFormatter.format(Number(signal.evidence.robust_dispersion_units))} units`,
      ],
    ];
  }
  return [
    ['Same-month relationship', decimalFormatter.format(signal.metric_value)],
    [
      'History compared',
      `${integerFormatter.format(Number(signal.evidence.paired_observations))} months`,
    ],
  ];
}

function inventoryRiskContent(risk: InventoryRisk): {
  readonly title: string;
  readonly detail: string;
} {
  switch (risk.classification) {
    case 'stockout':
      return {
        title: 'Potential stockout',
        detail: 'Projected inventory falls below zero before replenishment arrives.',
      };
    case 'below_safety_stock':
      return {
        title: 'Below safety stock',
        detail: 'Projected inventory remains nonnegative but falls below the safety-stock policy.',
      };
    case 'excess':
      return {
        title: 'Excess inventory',
        detail: 'Projected inventory exceeds the configured maximum months-of-coverage threshold.',
      };
    default:
      return {
        title: 'Healthy inventory',
        detail: 'Projected inventory remains above safety stock without excessive coverage.',
      };
  }
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(value));
}

function buildChartData(series: DemandSeries, forecast?: ForecastPreview): ChartPoint[] {
  const history: ChartPoint[] = series.observations.map((point) => ({
    period_start: point.period_start,
    actual: point.demand_units,
    forecast: null,
    interval: null,
  }));
  if (!forecast || history.length === 0) return history;

  const lastObserved = history[history.length - 1];
  if (!lastObserved) return history;
  history[history.length - 1] = {
    period_start: lastObserved.period_start,
    actual: lastObserved.actual,
    forecast: lastObserved.actual,
    interval: null,
  };
  return history.concat(
    forecast.forecasts.map((point) => ({
      period_start: point.period_start,
      actual: null,
      forecast: point.forecast_value,
      interval: [point.lower_bound, point.upper_bound],
    })),
  );
}

export default function DemandExplorerPage() {
  const [selectedStoreId, setSelectedStoreId] = useState('');
  const [selectedProductId, setSelectedProductId] = useState('');
  const [productSearch, setProductSearch] = useState('');
  const [horizonMonths, setHorizonMonths] = useState(6);
  const deferredProductSearch = useDeferredValue(productSearch.trim());

  const storesQuery = useQuery({
    queryKey: ['stores'],
    queryFn: ({ signal }) => listStores(signal),
  });
  const activeStoreId = selectedStoreId || storesQuery.data?.[0]?.store_id || '';

  const productsQuery = useQuery({
    queryKey: ['products', activeStoreId, deferredProductSearch],
    queryFn: ({ signal }) => searchProducts(activeStoreId, deferredProductSearch, signal),
    enabled: Boolean(activeStoreId),
  });
  const productIsVisible = productsQuery.data?.some(
    (product) => product.product_id === selectedProductId,
  );
  const activeProductId =
    (productIsVisible ? selectedProductId : '') || productsQuery.data?.[0]?.product_id || '';

  const demandQuery = useQuery({
    queryKey: ['demand-series', activeStoreId, activeProductId],
    queryFn: ({ signal }) => getDemandSeries(activeStoreId, activeProductId, signal),
    enabled: Boolean(activeStoreId && activeProductId),
  });
  const signalsQuery = useQuery({
    queryKey: ['demand-signals', activeStoreId, activeProductId],
    queryFn: ({ signal }) => getDemandSignals(activeStoreId, activeProductId, signal),
    enabled: Boolean(activeStoreId && activeProductId),
  });
  const inventoryPositionQuery = useQuery({
    queryKey: ['inventory-position', activeStoreId, activeProductId],
    queryFn: ({ signal }) => getInventoryPosition(activeStoreId, activeProductId, signal),
    enabled: Boolean(activeStoreId && activeProductId),
  });
  const inventoryRiskQuery = useQuery({
    queryKey: ['inventory-risk', activeStoreId, activeProductId],
    queryFn: ({ signal }) => getInventoryRisk(activeStoreId, activeProductId, signal),
    enabled: Boolean(activeStoreId && activeProductId),
  });
  const forecastMutation = useMutation({ mutationFn: createForecastPreview });

  const hasRequestError = storesQuery.isError || productsQuery.isError || demandQuery.isError;
  const series = demandQuery.data;
  const forecast =
    forecastMutation.data?.store_id === activeStoreId &&
    forecastMutation.data.product.product_id === activeProductId &&
    forecastMutation.data.horizon_months === horizonMonths
      ? forecastMutation.data
      : undefined;
  const chartData = series ? buildChartData(series, forecast) : [];

  function resetForecast(): void {
    forecastMutation.reset();
  }

  return (
    <div className="page">
      <PageHeader
        description="Compare observed monthly demand with a validated statistical forecast, its uncertainty, and backtesting evidence at the Store + SKU grain."
        eyebrow="Core workflow"
        title="Demand Explorer"
      />
      <div aria-label="Demand filters" className="filter-shell">
        <label>
          <span>Store</span>
          <select
            aria-label="Store"
            disabled={storesQuery.isLoading || !storesQuery.data?.length}
            onChange={(event) => {
              setSelectedStoreId(event.target.value);
              setSelectedProductId('');
              setProductSearch('');
              resetForecast();
            }}
            value={activeStoreId}
          >
            {storesQuery.data?.map((store) => (
              <option key={store.store_id} value={store.store_id}>
                {store.store_name} · {store.store_code}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Search the catalog</span>
          <input
            aria-label="Search SKU or product"
            onChange={(event) => {
              setProductSearch(event.target.value);
              resetForecast();
            }}
            placeholder="SKU, product, or category"
            type="search"
            value={productSearch}
          />
        </label>
        <label>
          <span>SKU or product</span>
          <select
            aria-label="SKU or product"
            disabled={productsQuery.isLoading || !productsQuery.data?.length}
            onChange={(event) => {
              setSelectedProductId(event.target.value);
              resetForecast();
            }}
            value={activeProductId}
          >
            {productsQuery.data?.map((product) => (
              <option key={product.product_id} value={product.product_id}>
                {product.sku} · {product.product_name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {hasRequestError ? (
        <section className="message-panel message-panel--error" role="alert">
          <strong>Planning data could not be loaded.</strong>
          <p>Confirm that the FastAPI backend is running and its readiness check is successful.</p>
        </section>
      ) : null}

      {!hasRequestError &&
      (storesQuery.isLoading || productsQuery.isLoading || demandQuery.isLoading) ? (
        <section aria-live="polite" className="message-panel">
          <strong>Loading planning data…</strong>
          <p>Meridian is querying the selected Parquet reference artifacts.</p>
        </section>
      ) : null}

      {!hasRequestError && productsQuery.data?.length === 0 ? (
        <EmptyState
          description="Try a different SKU, product name, or category. No matching active products were found for this store."
          eyebrow="No matches"
          title="Adjust your catalog search"
        />
      ) : null}

      {series ? (
        <div className="explorer-content">
          <section className="product-context">
            <div>
              <p className="eyebrow">{series.product.sku}</p>
              <h2>{series.product.product_name}</h2>
              <p>
                {series.product.brand} · {series.product.category} / {series.product.subcategory}
              </p>
            </div>
            <dl>
              <div>
                <dt>Lead time</dt>
                <dd>{series.policy.lead_time_days} days</dd>
              </div>
              <div>
                <dt>Safety stock</dt>
                <dd>{integerFormatter.format(series.policy.safety_stock)} units</dd>
              </div>
              <div>
                <dt>Reorder point</dt>
                <dd>{integerFormatter.format(series.policy.reorder_point)} units</dd>
              </div>
            </dl>
          </section>

          <section aria-label="Demand key performance indicators" className="kpi-grid">
            <article>
              <span>Total demand</span>
              <strong>{integerFormatter.format(series.summary.total_units)}</strong>
              <small>units in selected history</small>
            </article>
            <article>
              <span>Monthly average</span>
              <strong>{decimalFormatter.format(series.summary.average_monthly_units)}</strong>
              <small>units per month</small>
            </article>
            <article>
              <span>Peak month</span>
              <strong>{integerFormatter.format(series.summary.maximum_monthly_units)}</strong>
              <small>units</small>
            </article>
            <article>
              <span>Zero-demand months</span>
              <strong>{series.summary.zero_demand_months}</strong>
              <small>stored true zeros</small>
            </article>
          </section>

          <section className="forecast-workspace">
            <div className="forecast-controls">
              <div>
                <p className="eyebrow">Forecast preview</p>
                <h2>Plan the next horizon</h2>
                <p>Compare eligible models using expanding-window backtesting for this series.</p>
              </div>
              <div className="forecast-actions">
                <label>
                  <span>Horizon</span>
                  <select
                    aria-label="Forecast horizon"
                    disabled={forecastMutation.isPending}
                    onChange={(event) => {
                      setHorizonMonths(Number(event.target.value));
                      resetForecast();
                    }}
                    value={horizonMonths}
                  >
                    {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
                      <option key={month} value={month}>
                        {month} {month === 1 ? 'month' : 'months'}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  disabled={!activeStoreId || !activeProductId || forecastMutation.isPending}
                  onClick={() =>
                    forecastMutation.mutate({
                      store_id: activeStoreId,
                      product_id: activeProductId,
                      horizon_months: horizonMonths,
                      interval_level: 90,
                    })
                  }
                  type="button"
                >
                  {forecastMutation.isPending ? 'Generating…' : 'Generate forecast'}
                </button>
              </div>
            </div>

            {forecastMutation.isPending ? (
              <div aria-live="polite" className="forecast-status" role="status">
                <span className="loading-indicator" />
                <div>
                  <strong>Evaluating candidate models…</strong>
                  <p>Rolling-origin validation may take a few seconds.</p>
                </div>
              </div>
            ) : null}

            {forecastMutation.isError ? (
              <div className="forecast-error" role="alert">
                <strong>Forecast could not be generated.</strong>
                <p>{forecastMutation.error.message}</p>
              </div>
            ) : null}

            {forecast ? (
              <div className="forecast-result" aria-live="polite">
                <div className="forecast-result-heading">
                  <div>
                    <span>Selected model</span>
                    <strong>{forecast.selected_model}</strong>
                  </div>
                  <p>
                    Compared {forecast.evaluations.length} eligible models across{' '}
                    {forecast.validation_origins} expanding validation origins.
                  </p>
                  <span className="model-badge">{forecast.interval_level}% interval</span>
                </div>
                <section aria-label="Forecast validation metrics" className="forecast-metrics">
                  <article>
                    <span>WAPE</span>
                    <strong>{formatMetric(forecast.selected_metrics.wape, 'percentage')}</strong>
                    <small>weighted absolute error</small>
                  </article>
                  <article>
                    <span>MASE</span>
                    <strong>{formatMetric(forecast.selected_metrics.mase, 'decimal')}</strong>
                    <small>seasonal-naive scaled</small>
                  </article>
                  <article>
                    <span>RMSE</span>
                    <strong>{decimalFormatter.format(forecast.selected_metrics.rmse)}</strong>
                    <small>units</small>
                  </article>
                  <article>
                    <span>Bias</span>
                    <strong>{formatMetric(forecast.selected_metrics.bias, 'percentage')}</strong>
                    <small>positive means over-forecast</small>
                  </article>
                  <article>
                    <span>Interval coverage</span>
                    <strong>
                      {formatMetric(forecast.selected_metrics.interval_coverage, 'percentage')}
                    </strong>
                    <small>{forecast.selected_metrics.validation_points} validation points</small>
                  </article>
                </section>
                <details className="model-comparison">
                  <summary>Review candidate comparison</summary>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Model</th>
                          <th>Status</th>
                          <th>WAPE</th>
                          <th>MASE</th>
                          <th>Bias</th>
                          <th>RMSE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {forecast.evaluations.map((evaluation) => (
                          <tr key={evaluation.model_name}>
                            <th scope="row">{evaluation.model_name}</th>
                            <td>
                              {evaluation.status === 'succeeded' ? 'Evaluated' : 'Unavailable'}
                            </td>
                            <td>{formatMetric(evaluation.metrics?.wape ?? null, 'percentage')}</td>
                            <td>{formatMetric(evaluation.metrics?.mase ?? null, 'decimal')}</td>
                            <td>{formatMetric(evaluation.metrics?.bias ?? null, 'percentage')}</td>
                            <td>
                              {evaluation.metrics
                                ? decimalFormatter.format(evaluation.metrics.rmse)
                                : 'Not defined'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </div>
            ) : null}
          </section>

          <section className="chart-panel">
            <div className="chart-heading">
              <div>
                <p className="eyebrow">Actual vs forecast</p>
                <h2>Monthly demand outlook</h2>
              </div>
              <div className="chart-badges">
                <span className="history-badge">Observed</span>
                {forecast ? <span className="forecast-badge">Forecast</span> : null}
              </div>
            </div>
            <div
              aria-label={`${forecast ? 'Actual and forecast' : 'Historical'} monthly demand chart for ${series.product.sku}`}
              className="demand-chart"
              role="img"
            >
              <ResponsiveContainer height="100%" minWidth={0} width="100%">
                <ComposedChart data={chartData} margin={{ left: 4, right: 18, top: 8 }}>
                  <CartesianGrid stroke="#e5ebe7" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    axisLine={false}
                    dataKey="period_start"
                    minTickGap={28}
                    tickFormatter={formatMonth}
                    tickLine={false}
                  />
                  <YAxis axisLine={false} tickLine={false} width={48} />
                  <Tooltip formatter={formatTooltipValue} labelFormatter={formatTooltipMonth} />
                  <Legend iconType="line" verticalAlign="top" />
                  {forecast ? (
                    <ReferenceLine
                      label={{ position: 'insideTopRight', value: 'Forecast starts' }}
                      stroke="#9aa8a2"
                      strokeDasharray="4 4"
                      x={forecast.training_cutoff}
                    />
                  ) : null}
                  {forecast ? (
                    <Area
                      connectNulls={false}
                      dataKey="interval"
                      fill="#d8e7df"
                      fillOpacity={0.75}
                      legendType="square"
                      name={`${forecast.interval_level}% prediction interval`}
                      stroke="none"
                      type="monotone"
                    />
                  ) : null}
                  <Line
                    activeDot={{ r: 5 }}
                    dataKey="actual"
                    dot={false}
                    name="Actual demand"
                    stroke="#1d5c46"
                    strokeWidth={2.5}
                    type="monotone"
                  />
                  {forecast ? (
                    <Line
                      activeDot={{ r: 5 }}
                      dataKey="forecast"
                      dot={{ fill: '#bb6b32', r: 3 }}
                      name="Forecast demand"
                      stroke="#bb6b32"
                      strokeDasharray="7 5"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                  ) : null}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <p className="chart-caption">
              Observed demand runs from {formatMonth(series.summary.period_start)} through{' '}
              {formatMonth(series.summary.period_end)}.
              {forecast
                ? ` The dashed line shows the selected ${forecast.selected_model} forecast; the shaded band is its ${forecast.interval_level}% prediction interval.`
                : ' Generate a forecast to compare the future outlook and uncertainty.'}
            </p>
          </section>

          <section aria-labelledby="signals-heading" className="signals-panel">
            <div className="signals-heading">
              <div>
                <p className="eyebrow">Explainable detection</p>
                <h2 id="signals-heading">Demand signals</h2>
                <p>Evidence-backed changes and behaviors that may deserve planner attention.</p>
              </div>
              {signalsQuery.data ? (
                <span className="signal-count">{signalsQuery.data.length} signals</span>
              ) : null}
            </div>

            {signalsQuery.isLoading ? (
              <div aria-live="polite" className="signals-status" role="status">
                <span className="loading-indicator" />
                <span>Reviewing demand history…</span>
              </div>
            ) : null}

            {signalsQuery.isError ? (
              <div className="signals-error" role="alert">
                <strong>Demand signals are unavailable.</strong>
                <p>
                  Historical demand and forecasting remain available while this analysis reloads.
                </p>
              </div>
            ) : null}

            {signalsQuery.data?.length === 0 ? (
              <div className="signals-empty">
                <strong>No notable demand signals</strong>
                <p>
                  The selected history does not currently cross the configured signal thresholds.
                </p>
              </div>
            ) : null}

            {signalsQuery.data?.length ? (
              <div className="signal-grid">
                {signalsQuery.data.map((signal) => (
                  <article
                    className={`signal-card signal-card--${signal.severity}`}
                    key={signal.signal_id}
                  >
                    <div className="signal-card-heading">
                      <span className={`signal-severity signal-severity--${signal.severity}`}>
                        {signal.severity}
                      </span>
                      <span>{signal.signal_type}</span>
                    </div>
                    <h3>{signal.title}</h3>
                    <p>{signal.description}</p>
                    <dl>
                      <div>
                        <dt>Measured signal</dt>
                        <dd>{formatSignalMetric(signal)}</dd>
                      </div>
                      {signalEvidence(signal).map(([label, value]) => (
                        <div key={label}>
                          <dt>{label}</dt>
                          <dd>{value}</dd>
                        </div>
                      ))}
                    </dl>
                    {signal.period_start ? (
                      <small>Evidence through {formatMonth(signal.period_start)}</small>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : null}
          </section>

          <section aria-labelledby="inventory-heading" className="inventory-panel">
            <div className="inventory-heading">
              <div>
                <p className="eyebrow">Replenishment outlook</p>
                <h2 id="inventory-heading">Inventory risk</h2>
                <p>Project the selected SKU's inventory when its replenishment lead time ends.</p>
              </div>
              {inventoryRiskQuery.data ? (
                <span
                  className={`inventory-risk-badge inventory-risk-badge--${inventoryRiskQuery.data.severity}`}
                >
                  {inventoryRiskContent(inventoryRiskQuery.data).title}
                </span>
              ) : null}
            </div>

            {inventoryPositionQuery.isLoading || inventoryRiskQuery.isLoading ? (
              <div aria-live="polite" className="inventory-status" role="status">
                <span className="loading-indicator" />
                <span>Calculating lead-time inventory exposure…</span>
              </div>
            ) : null}

            {inventoryPositionQuery.isError || inventoryRiskQuery.isError ? (
              <div className="inventory-error" role="alert">
                <strong>Inventory risk is unavailable.</strong>
                <p>Demand, signals, and forecast previews remain available for this selection.</p>
              </div>
            ) : null}

            {inventoryPositionQuery.data && inventoryRiskQuery.data ? (
              <div className="inventory-content">
                <div
                  className={`inventory-summary inventory-summary--${inventoryRiskQuery.data.severity}`}
                >
                  <div>
                    <span>Assessment</span>
                    <h3>{inventoryRiskContent(inventoryRiskQuery.data).title}</h3>
                    <p>{inventoryRiskContent(inventoryRiskQuery.data).detail}</p>
                  </div>
                  <div>
                    <span>Projected at arrival</span>
                    <strong>
                      {decimalFormatter.format(inventoryRiskQuery.data.projected_inventory)} units
                    </strong>
                    <small>
                      {formatDateTime(inventoryRiskQuery.data.replenishment_arrival_at)} ·{' '}
                      {inventoryPositionQuery.data.lead_time_days}-day lead time
                    </small>
                  </div>
                </div>

                <div aria-label="Projected inventory calculation" className="inventory-equation">
                  <div>
                    <span>Available inventory</span>
                    <strong>
                      {integerFormatter.format(inventoryRiskQuery.data.available_inventory)}
                    </strong>
                    <small>
                      {integerFormatter.format(inventoryPositionQuery.data.on_hand)} on hand −{' '}
                      {integerFormatter.format(inventoryPositionQuery.data.allocated)} allocated
                    </small>
                  </div>
                  <span aria-hidden="true">+</span>
                  <div>
                    <span>Incoming in lead time</span>
                    <strong>
                      {integerFormatter.format(
                        inventoryRiskQuery.data.on_order_due_within_lead_time,
                      )}
                    </strong>
                    <small>
                      of {integerFormatter.format(inventoryPositionQuery.data.on_order)} total on
                      order
                    </small>
                  </div>
                  <span aria-hidden="true">−</span>
                  <div>
                    <span>Lead-time demand</span>
                    <strong>
                      {decimalFormatter.format(
                        inventoryRiskQuery.data.forecast_demand_during_lead_time,
                      )}
                    </strong>
                    <small>{inventoryRiskQuery.data.selected_model} forecast</small>
                  </div>
                  <span aria-hidden="true">=</span>
                  <div className="inventory-equation-result">
                    <span>Projected inventory</span>
                    <strong>
                      {decimalFormatter.format(inventoryRiskQuery.data.projected_inventory)}
                    </strong>
                    <small>
                      {integerFormatter.format(inventoryRiskQuery.data.safety_stock)} safety stock
                    </small>
                  </div>
                </div>

                <dl className="inventory-evidence">
                  <div>
                    <dt>Months of coverage</dt>
                    <dd>
                      {inventoryRiskQuery.data.coverage_months === null
                        ? 'Not defined'
                        : decimalFormatter.format(inventoryRiskQuery.data.coverage_months)}
                    </dd>
                  </div>
                  <div>
                    <dt>Excess threshold</dt>
                    <dd>
                      {decimalFormatter.format(
                        inventoryRiskQuery.data.excess_coverage_threshold_months,
                      )}{' '}
                      months
                    </dd>
                  </div>
                  <div>
                    <dt>Snapshot date</dt>
                    <dd>{formatDateTime(inventoryPositionQuery.data.snapshot_at)}</dd>
                  </div>
                  <div>
                    <dt>Risk forecast</dt>
                    <dd>
                      {inventoryRiskQuery.data.forecast_horizon_months}{' '}
                      {inventoryRiskQuery.data.forecast_horizon_months === 1 ? 'month' : 'months'} ·{' '}
                      {inventoryRiskQuery.data.selected_model}
                    </dd>
                  </div>
                </dl>
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}
