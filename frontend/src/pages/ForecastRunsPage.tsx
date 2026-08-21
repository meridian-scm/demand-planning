import { useQuery } from '@tanstack/react-query';
import { useDeferredValue, useState } from 'react';

import {
  getStoredEvaluations,
  getStoredForecasts,
  listForecastRuns,
  listForecastSeries,
} from '../api/forecast-runs';
import { listStores } from '../api/planning';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

const integerFormatter = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 0 });
const decimalFormatter = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 2 });
const percentageFormatter = new Intl.NumberFormat('en-CA', {
  maximumFractionDigits: 1,
  style: 'percent',
});

function formatMetric(value: number | null, percentage = false): string {
  if (value === null) return 'Not defined';
  return percentage ? percentageFormatter.format(value) : decimalFormatter.format(value);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(value.length === 10 ? `${value}T00:00:00Z` : value));
}

export default function ForecastRunsPage() {
  const [selectedRunId, setSelectedRunId] = useState('');
  const [selectedStoreId, setSelectedStoreId] = useState('');
  const [selectedSeriesKey, setSelectedSeriesKey] = useState('');
  const [seriesSearch, setSeriesSearch] = useState('');
  const deferredSearch = useDeferredValue(seriesSearch.trim());

  const runsQuery = useQuery({
    queryKey: ['forecast-runs'],
    queryFn: ({ signal }) => listForecastRuns(signal),
  });
  const storesQuery = useQuery({
    queryKey: ['stores'],
    queryFn: ({ signal }) => listStores(signal),
  });
  const activeRunId = selectedRunId || runsQuery.data?.[0]?.run_id || '';
  const activeRun = runsQuery.data?.find((run) => run.run_id === activeRunId);
  const seriesQuery = useQuery({
    queryKey: ['forecast-run-series', activeRunId, selectedStoreId, deferredSearch],
    queryFn: ({ signal }) =>
      listForecastSeries(activeRunId, selectedStoreId, deferredSearch, signal),
    enabled: Boolean(activeRunId),
  });
  const selectedSeriesIsVisible = seriesQuery.data?.some(
    (series) => `${series.store_id}:${series.product_id}` === selectedSeriesKey,
  );
  const activeSeries =
    (selectedSeriesIsVisible
      ? seriesQuery.data?.find(
          (series) => `${series.store_id}:${series.product_id}` === selectedSeriesKey,
        )
      : undefined) ?? seriesQuery.data?.[0];
  const evaluationsQuery = useQuery({
    queryKey: ['stored-evaluations', activeRunId, activeSeries?.store_id, activeSeries?.product_id],
    queryFn: ({ signal }) =>
      getStoredEvaluations(
        activeRunId,
        activeSeries?.store_id ?? '',
        activeSeries?.product_id ?? '',
        signal,
      ),
    enabled: Boolean(activeRunId && activeSeries),
  });
  const forecastsQuery = useQuery({
    queryKey: ['stored-forecasts', activeRunId, activeSeries?.store_id, activeSeries?.product_id],
    queryFn: ({ signal }) =>
      getStoredForecasts(
        activeRunId,
        activeSeries?.store_id ?? '',
        activeSeries?.product_id ?? '',
        signal,
      ),
    enabled: Boolean(activeRunId && activeSeries),
  });
  const hasError =
    runsQuery.isError ||
    storesQuery.isError ||
    seriesQuery.isError ||
    evaluationsQuery.isError ||
    forecastsQuery.isError;

  return (
    <div className="page">
      <PageHeader
        description="Inspect immutable forecast runs, selected models, validation evidence, and published forecasts."
        eyebrow="Forecast governance"
        title="Forecast Runs"
      />

      {hasError ? (
        <section className="message-panel message-panel--error" role="alert">
          <strong>Forecast-run artifacts could not be loaded.</strong>
          <p>Confirm that the selected run exists and its Parquet files pass readiness checks.</p>
        </section>
      ) : null}

      {!hasError && runsQuery.isLoading ? (
        <section aria-live="polite" className="message-panel" role="status">
          <strong>Loading published forecast runs…</strong>
        </section>
      ) : null}

      {!hasError && runsQuery.data?.length === 0 ? (
        <EmptyState
          description="Generate an immutable forecast run with the documented offline command, then reload this page."
          eyebrow="No published artifacts"
          title="No forecast runs available"
        />
      ) : null}

      {activeRun ? (
        <div className="run-workspace">
          <section className="run-header-card">
            <div>
              <p className="eyebrow">Published run</p>
              <h2>{activeRun.run_id}</h2>
              <p>
                Created {formatDate(activeRun.created_at)} · Training through{' '}
                {formatDate(activeRun.training_cutoff)} · {activeRun.horizon_months}-month horizon
              </p>
            </div>
            <label>
              <span>Forecast run</span>
              <select
                aria-label="Forecast run"
                onChange={(event) => {
                  setSelectedRunId(event.target.value);
                  setSelectedSeriesKey('');
                }}
                value={activeRunId}
              >
                {runsQuery.data?.map((run) => (
                  <option key={run.run_id} value={run.run_id}>
                    {run.run_id} · {run.status}
                  </option>
                ))}
              </select>
            </label>
          </section>

          <section aria-label="Forecast run summary" className="run-summary-grid">
            <article>
              <span>Series completed</span>
              <strong>{integerFormatter.format(activeRun.successful_series_count)}</strong>
              <small>of {integerFormatter.format(activeRun.series_count)}</small>
            </article>
            <article>
              <span>Series failed</span>
              <strong>{integerFormatter.format(activeRun.failed_series_count)}</strong>
              <small>isolated failures</small>
            </article>
            <article>
              <span>Candidate evaluations</span>
              <strong>{integerFormatter.format(activeRun.evaluation_count)}</strong>
              <small>rolling-origin comparisons</small>
            </article>
            <article>
              <span>Forecast points</span>
              <strong>{integerFormatter.format(activeRun.forecast_count)}</strong>
              <small>{activeRun.interval_level}% intervals</small>
            </article>
          </section>

          <section className="run-browser" aria-labelledby="run-series-heading">
            <div className="run-browser-heading">
              <div>
                <p className="eyebrow">Store + SKU results</p>
                <h2 id="run-series-heading">Published series</h2>
              </div>
              <div className="run-filters">
                <label>
                  <span>Store</span>
                  <select
                    aria-label="Forecast run store"
                    onChange={(event) => {
                      setSelectedStoreId(event.target.value);
                      setSelectedSeriesKey('');
                    }}
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
                  <span>Search</span>
                  <input
                    aria-label="Search forecast series"
                    onChange={(event) => {
                      setSeriesSearch(event.target.value);
                      setSelectedSeriesKey('');
                    }}
                    placeholder="SKU, product, or category"
                    type="search"
                    value={seriesSearch}
                  />
                </label>
              </div>
            </div>

            {seriesQuery.isLoading ? <p className="run-inline-status">Loading series…</p> : null}
            {seriesQuery.data?.length === 0 ? (
              <div className="exception-empty">
                <strong>No matching forecast series</strong>
                <p>Adjust the store or search filter.</p>
              </div>
            ) : null}
            {seriesQuery.data?.length ? (
              <div className="run-series-layout">
                <div aria-label="Forecast series results" className="run-series-list">
                  {seriesQuery.data.map((series) => {
                    const key = `${series.store_id}:${series.product_id}`;
                    const selected =
                      activeSeries?.store_id === series.store_id &&
                      activeSeries.product_id === series.product_id;
                    return (
                      <button
                        aria-pressed={selected}
                        className={
                          selected ? 'run-series-row run-series-row--selected' : 'run-series-row'
                        }
                        key={key}
                        onClick={() => setSelectedSeriesKey(key)}
                        type="button"
                      >
                        <span>
                          <strong>{series.sku}</strong>
                          <small>{series.product_name}</small>
                        </span>
                        <span>
                          <strong>{series.selected_model ?? 'Failed'}</strong>
                          <small>{series.store_id}</small>
                        </span>
                        <span>
                          <strong>{formatMetric(series.wape, true)}</strong>
                          <small>WAPE</small>
                        </span>
                      </button>
                    );
                  })}
                </div>

                {activeSeries ? (
                  <div className="run-series-detail">
                    <div className="run-detail-heading">
                      <div>
                        <p className="eyebrow">{activeSeries.sku}</p>
                        <h3>{activeSeries.product_name}</h3>
                        <p>
                          {activeSeries.store_id} · {activeSeries.category} ·{' '}
                          {activeSeries.selected_model ?? 'Forecast failed'}
                        </p>
                      </div>
                      <span className={`run-status run-status--${activeSeries.status}`}>
                        {activeSeries.status}
                      </span>
                    </div>

                    <div className="run-detail-metrics">
                      <div>
                        <span>WAPE</span>
                        <strong>{formatMetric(activeSeries.wape, true)}</strong>
                      </div>
                      <div>
                        <span>MASE</span>
                        <strong>{formatMetric(activeSeries.mase)}</strong>
                      </div>
                      <div>
                        <span>Bias</span>
                        <strong>{formatMetric(activeSeries.bias, true)}</strong>
                      </div>
                      <div>
                        <span>Coverage</span>
                        <strong>{formatMetric(activeSeries.interval_coverage, true)}</strong>
                      </div>
                    </div>

                    <div className="run-table-block">
                      <h4>Candidate evaluation</h4>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>Model</th>
                              <th>Selected</th>
                              <th>WAPE</th>
                              <th>MASE</th>
                              <th>Bias</th>
                            </tr>
                          </thead>
                          <tbody>
                            {evaluationsQuery.data?.map((evaluation) => (
                              <tr key={evaluation.model_name}>
                                <th scope="row">{evaluation.model_name}</th>
                                <td>{evaluation.selected ? 'Yes' : 'No'}</td>
                                <td>{formatMetric(evaluation.wape, true)}</td>
                                <td>{formatMetric(evaluation.mase)}</td>
                                <td>{formatMetric(evaluation.bias, true)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div className="run-table-block">
                      <h4>Published forecast</h4>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>Period</th>
                              <th>Forecast</th>
                              <th>Lower</th>
                              <th>Upper</th>
                            </tr>
                          </thead>
                          <tbody>
                            {forecastsQuery.data?.map((forecast) => (
                              <tr key={forecast.period_start}>
                                <th scope="row">{formatDate(forecast.period_start)}</th>
                                <td>{decimalFormatter.format(forecast.forecast_value)}</td>
                                <td>{decimalFormatter.format(forecast.lower_bound)}</td>
                                <td>{decimalFormatter.format(forecast.upper_bound)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}
