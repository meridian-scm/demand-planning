import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
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

import { listForecastRuns } from '../api/forecast-runs';
import { getPortfolioOverview, type OverviewException } from '../api/overview';
import { listStores } from '../api/planning';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

const integerFormatter = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 0 });
const decimalFormatter = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 2 });
const percentageFormatter = new Intl.NumberFormat('en-CA', {
  maximumFractionDigits: 1,
  style: 'percent',
});

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

function formatMetric(value: number | null, percentage = false): string {
  if (value === null) return 'Not defined';
  return percentage ? percentageFormatter.format(value) : decimalFormatter.format(value);
}

function formatExceptionMetric(exception: OverviewException): string {
  if (exception.exception_type === 'forecast_bias') {
    return percentageFormatter.format(exception.metric_value);
  }
  if (exception.exception_type === 'forecast_uncertainty') {
    return `${decimalFormatter.format(exception.metric_value)}×`;
  }
  if (exception.exception_type === 'excess_inventory') {
    return `${decimalFormatter.format(exception.metric_value)} months`;
  }
  return `${decimalFormatter.format(exception.metric_value)} units`;
}

function tooltipValue(value: unknown, name: unknown): [string, string] {
  return [
    `${integerFormatter.format(typeof value === 'number' ? value : Number(value))} units`,
    typeof name === 'string' ? name : 'Demand',
  ];
}

export default function OverviewPage() {
  const [selectedStoreId, setSelectedStoreId] = useState('');
  const [selectedRunId, setSelectedRunId] = useState('');
  const storesQuery = useQuery({
    queryKey: ['stores'],
    queryFn: ({ signal }) => listStores(signal),
  });
  const runsQuery = useQuery({
    queryKey: ['forecast-runs'],
    queryFn: ({ signal }) => listForecastRuns(signal),
  });
  const activeRunId = selectedRunId || runsQuery.data?.[0]?.run_id || '';
  const overviewQuery = useQuery({
    queryKey: ['portfolio-overview', activeRunId, selectedStoreId],
    queryFn: ({ signal }) => getPortfolioOverview(activeRunId, selectedStoreId, signal),
    enabled: Boolean(activeRunId),
  });
  const overview = overviewQuery.data;
  const isLoading = storesQuery.isLoading || runsQuery.isLoading || overviewQuery.isLoading;
  const hasError = storesQuery.isError || runsQuery.isError || overviewQuery.isError;
  const riskTotal = overview
    ? overview.risk_counts.stockout +
      overview.risk_counts.below_safety_stock +
      overview.risk_counts.healthy +
      overview.risk_counts.excess +
      overview.risk_counts.unavailable
    : 0;

  return (
    <div className="page overview-page">
      <PageHeader
        description="See portfolio demand, forecast reliability, inventory exposure, and the decisions requiring attention."
        eyebrow="Portfolio"
        title="Overview"
      />

      <section aria-label="Overview scope" className="overview-scope">
        <div>
          <p className="eyebrow">Planning scope</p>
          <strong>{overview?.store_name ?? 'All stores'}</strong>
          <span>
            {overview
              ? `${integerFormatter.format(overview.series_count)} Store + SKU series · training through ${formatMonth(overview.training_cutoff)}`
              : 'Select a published forecast run'}
          </span>
        </div>
        <div className="overview-filters">
          <label>
            <span>Store</span>
            <select
              aria-label="Overview store"
              onChange={(event) => setSelectedStoreId(event.target.value)}
              value={selectedStoreId}
            >
              <option value="">All stores</option>
              {storesQuery.data?.map((store) => (
                <option key={store.store_id} value={store.store_id}>
                  {store.store_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Published run</span>
            <select
              aria-label="Overview forecast run"
              onChange={(event) => setSelectedRunId(event.target.value)}
              value={activeRunId}
            >
              {runsQuery.data?.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {hasError ? (
        <section className="message-panel message-panel--error" role="alert">
          <strong>Portfolio overview could not be loaded.</strong>
          <p>Confirm that the base data and selected forecast-run artifacts are available.</p>
        </section>
      ) : null}

      {!hasError && isLoading ? (
        <section aria-live="polite" className="message-panel" role="status">
          <strong>Loading portfolio planning evidence…</strong>
        </section>
      ) : null}

      {!hasError && !isLoading && runsQuery.data?.length === 0 ? (
        <EmptyState
          description="Publish an immutable forecast run before opening the portfolio overview."
          eyebrow="No published run"
          title="Portfolio evidence is not available"
        />
      ) : null}

      {overview ? (
        <div className="overview-workspace">
          <section aria-label="Demand summary" className="overview-kpis">
            <article>
              <span>Latest 12 months</span>
              <strong>{integerFormatter.format(overview.recent_12_month_demand)}</strong>
              <small>observed units</small>
            </article>
            <article>
              <span>Demand change</span>
              <strong>{formatMetric(overview.demand_change, true)}</strong>
              <small>latest 12 months vs prior 12</small>
            </article>
            <article>
              <span>Next {overview.horizon_months} months</span>
              <strong>{integerFormatter.format(overview.forecast_horizon_demand)}</strong>
              <small>published forecast units</small>
            </article>
            <article>
              <span>Inventory attention</span>
              <strong>
                {integerFormatter.format(
                  overview.risk_counts.stockout + overview.risk_counts.below_safety_stock,
                )}
              </strong>
              <small>series at or below safety risk</small>
            </article>
          </section>

          <div className="overview-primary-grid">
            <section className="overview-chart-panel">
              <div className="overview-section-heading">
                <div>
                  <p className="eyebrow">Demand outlook</p>
                  <h2>Portfolio demand by month</h2>
                </div>
                <span>{overview.store_name}</span>
              </div>
              <div
                aria-label={`Actual and forecast portfolio demand chart for ${overview.store_name}`}
                className="overview-chart"
                role="img"
              >
                <ResponsiveContainer height="100%" minWidth={0} width="100%">
                  <ComposedChart data={overview.timeline} margin={{ left: 4, right: 18, top: 10 }}>
                    <CartesianGrid stroke="#e5ebe7" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      axisLine={false}
                      dataKey="period_start"
                      minTickGap={24}
                      tickFormatter={formatMonth}
                      tickLine={false}
                    />
                    <YAxis axisLine={false} tickLine={false} width={56} />
                    <Tooltip formatter={tooltipValue} labelFormatter={formatTooltipMonth} />
                    <Legend iconType="line" verticalAlign="top" />
                    <ReferenceLine
                      label={{ position: 'insideTopRight', value: 'Forecast starts' }}
                      stroke="#9aa8a2"
                      strokeDasharray="4 4"
                      x={overview.training_cutoff}
                    />
                    <Line
                      activeDot={{ r: 5 }}
                      dataKey="actual_units"
                      dot={false}
                      name="Actual demand"
                      stroke="#1d5c46"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                    <Line
                      activeDot={{ r: 5 }}
                      dataKey="forecast_units"
                      dot={false}
                      name="Published forecast"
                      stroke="#bb6b32"
                      strokeDasharray="7 5"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section aria-labelledby="reliability-heading" className="overview-reliability">
              <div className="overview-section-heading">
                <div>
                  <p className="eyebrow">Forecast reliability</p>
                  <h2 id="reliability-heading">Validation evidence</h2>
                </div>
              </div>
              <dl>
                <div>
                  <dt>Median series WAPE</dt>
                  <dd>{formatMetric(overview.median_series_wape, true)}</dd>
                </div>
                <div>
                  <dt>Median series MASE</dt>
                  <dd>{formatMetric(overview.median_series_mase)}</dd>
                </div>
                <div>
                  <dt>Median absolute bias</dt>
                  <dd>{formatMetric(overview.median_absolute_bias, true)}</dd>
                </div>
                <div>
                  <dt>Interval coverage</dt>
                  <dd>{formatMetric(overview.weighted_interval_coverage, true)}</dd>
                </div>
              </dl>
              <p>
                Reliability uses rolling-origin results from the published run. WAPE is shown as the
                median Store + SKU result—not an incorrectly averaged portfolio accuracy score.
              </p>
              <Link to="/forecast-runs">Review model evidence</Link>
            </section>
          </div>

          <section aria-labelledby="risk-heading" className="overview-risk-panel">
            <div className="overview-section-heading">
              <div>
                <p className="eyebrow">Inventory exposure</p>
                <h2 id="risk-heading">Projected position at replenishment arrival</h2>
              </div>
              <span>{riskTotal} series evaluated</span>
            </div>
            <div className="overview-risk-grid">
              {(
                [
                  ['stockout', 'Potential stockout', overview.risk_counts.stockout],
                  ['below-safety', 'Below safety stock', overview.risk_counts.below_safety_stock],
                  ['healthy', 'Healthy', overview.risk_counts.healthy],
                  ['excess', 'Excess coverage', overview.risk_counts.excess],
                  ['unavailable', 'Unavailable', overview.risk_counts.unavailable],
                ] as const
              ).map(([kind, label, count]) => (
                <article className={`overview-risk overview-risk--${kind}`} key={kind}>
                  <span>{label}</span>
                  <strong>{count}</strong>
                  <small>{riskTotal ? percentageFormatter.format(count / riskTotal) : '0%'}</small>
                </article>
              ))}
            </div>
          </section>

          <section aria-labelledby="priority-heading" className="overview-priority-panel">
            <div className="overview-section-heading">
              <div>
                <p className="eyebrow">Decision queue</p>
                <h2 id="priority-heading">Priority planning exceptions</h2>
              </div>
              <Link to="/planning-exceptions">Open exception workspace</Link>
            </div>
            {overview.priority_exceptions.length ? (
              <div className="table-scroll">
                <table className="overview-exception-table">
                  <thead>
                    <tr>
                      <th>Priority</th>
                      <th>Store + SKU</th>
                      <th>Exception</th>
                      <th>Evidence</th>
                      <th>Model</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.priority_exceptions.map((exception) => (
                      <tr key={exception.exception_id}>
                        <td>
                          <span
                            className={`overview-severity overview-severity--${exception.severity}`}
                          >
                            {exception.priority_score}
                          </span>
                        </td>
                        <th scope="row">
                          <strong>{exception.sku}</strong>
                          <small>{exception.store_name}</small>
                        </th>
                        <td>
                          <strong>{exception.title}</strong>
                          <small>{exception.product_name}</small>
                        </td>
                        <td>{formatExceptionMetric(exception)}</td>
                        <td>{exception.selected_model}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="exception-empty">
                <strong>No priority exceptions</strong>
                <p>No inventory or forecast-reliability thresholds are crossed in this scope.</p>
              </div>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}
