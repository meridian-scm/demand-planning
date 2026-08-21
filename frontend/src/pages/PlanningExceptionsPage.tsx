import { useQuery } from '@tanstack/react-query';
import { useDeferredValue, useState } from 'react';

import {
  getPlanningExceptions,
  listStores,
  searchProducts,
  type PlanningException,
} from '../api/planning';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

type ExceptionGroup = 'all' | 'inventory' | 'demand' | 'forecast';

const decimalFormatter = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 2 });
const percentageFormatter = new Intl.NumberFormat('en-CA', {
  maximumFractionDigits: 1,
  style: 'percent',
});

const groupTypes: Readonly<Record<Exclude<ExceptionGroup, 'all'>, readonly string[]>> = {
  inventory: ['potential_stockout', 'below_safety_stock', 'excess_inventory'],
  demand: ['demand_spike', 'demand_decline'],
  forecast: ['forecast_uncertainty', 'forecast_bias'],
};

function formatMonth(value: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatMetric(exception: PlanningException): string {
  if (exception.exception_type === 'forecast_bias') {
    return percentageFormatter.format(exception.metric_value);
  }
  if (exception.metric_name.includes('inventory') || exception.metric_name.includes('demand')) {
    return `${decimalFormatter.format(exception.metric_value)} units`;
  }
  if (exception.metric_name === 'coverage_months') {
    return `${decimalFormatter.format(exception.metric_value)} months`;
  }
  return decimalFormatter.format(exception.metric_value);
}

function formatEvidenceLabel(value: string): string {
  return value.replaceAll('_', ' ').replace(/^./, (character) => character.toUpperCase());
}

function formatEvidenceValue(value: string | number): string {
  return typeof value === 'number' ? decimalFormatter.format(value) : value;
}

function evidenceSource(exception: PlanningException): string {
  if (exception.related_risk_id) return 'Inventory projection';
  if (exception.related_signal_id) return 'Demand signal';
  return 'Forecast validation';
}

export default function PlanningExceptionsPage() {
  const [selectedStoreId, setSelectedStoreId] = useState('');
  const [selectedProductId, setSelectedProductId] = useState('');
  const [productSearch, setProductSearch] = useState('');
  const [group, setGroup] = useState<ExceptionGroup>('all');
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
  const activeProduct = productsQuery.data?.find(
    (product) => product.product_id === activeProductId,
  );
  const exceptionsQuery = useQuery({
    queryKey: ['planning-exceptions', activeStoreId, activeProductId],
    queryFn: ({ signal }) => getPlanningExceptions(activeStoreId, activeProductId, signal),
    enabled: Boolean(activeStoreId && activeProductId),
  });

  const exceptions = exceptionsQuery.data ?? [];
  const visibleExceptions =
    group === 'all'
      ? exceptions
      : exceptions.filter((exception) => groupTypes[group].includes(exception.exception_type));
  const criticalCount = exceptions.filter((exception) => exception.severity === 'critical').length;
  const highCount = exceptions.filter((exception) => exception.severity === 'high').length;
  const isLoading = storesQuery.isLoading || productsQuery.isLoading || exceptionsQuery.isLoading;
  const hasError = storesQuery.isError || productsQuery.isError || exceptionsQuery.isError;

  return (
    <div className="page">
      <PageHeader
        description="Review evidence-backed demand, forecast, and inventory conditions in priority order."
        eyebrow="Attention queue"
        title="Planning Exceptions"
      />

      <div aria-label="Exception filters" className="filter-shell exception-filter-shell">
        <label>
          <span>Store</span>
          <select
            aria-label="Exception store"
            disabled={storesQuery.isLoading || !storesQuery.data?.length}
            onChange={(event) => {
              setSelectedStoreId(event.target.value);
              setSelectedProductId('');
              setProductSearch('');
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
            aria-label="Search exception SKU or product"
            onChange={(event) => setProductSearch(event.target.value)}
            placeholder="SKU, product, or category"
            type="search"
            value={productSearch}
          />
        </label>
        <label>
          <span>SKU or product</span>
          <select
            aria-label="Exception SKU or product"
            disabled={productsQuery.isLoading || !productsQuery.data?.length}
            onChange={(event) => setSelectedProductId(event.target.value)}
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

      {hasError ? (
        <section className="message-panel message-panel--error" role="alert">
          <strong>Planning exceptions could not be loaded.</strong>
          <p>Demand Explorer remains available while this selected-series queue reloads.</p>
        </section>
      ) : null}

      {!hasError && isLoading ? (
        <section aria-live="polite" className="message-panel" role="status">
          <strong>Prioritizing planning exceptions…</strong>
          <p>Meridian is combining inventory, demand-signal, and forecast evidence.</p>
        </section>
      ) : null}

      {!hasError && productsQuery.data?.length === 0 ? (
        <EmptyState
          description="Try a different SKU, product name, or category for this store."
          eyebrow="No matches"
          title="Adjust your catalog search"
        />
      ) : null}

      {!hasError && activeProduct && exceptionsQuery.data ? (
        <div className="exception-workspace">
          <section className="exception-context">
            <div>
              <p className="eyebrow">{activeProduct.sku}</p>
              <h2>{activeProduct.product_name}</h2>
              <p>
                {activeProduct.brand} · {activeProduct.category} / {activeProduct.subcategory}
              </p>
            </div>
            <div className="exception-counts" aria-label="Exception summary">
              <div>
                <span>Open</span>
                <strong>{exceptions.length}</strong>
              </div>
              <div>
                <span>Critical</span>
                <strong>{criticalCount}</strong>
              </div>
              <div>
                <span>High</span>
                <strong>{highCount}</strong>
              </div>
            </div>
          </section>

          <section className="exception-queue" aria-labelledby="exception-queue-heading">
            <div className="exception-queue-heading">
              <div>
                <p className="eyebrow">Selected-series priority</p>
                <h2 id="exception-queue-heading">Exception queue</h2>
                <p>
                  Portfolio-wide prioritization will use the immutable reference runs implemented in
                  the next Forecast Runs slice.
                </p>
              </div>
              <label>
                <span>Exception group</span>
                <select
                  aria-label="Exception group"
                  onChange={(event) => setGroup(event.target.value as ExceptionGroup)}
                  value={group}
                >
                  <option value="all">All exceptions</option>
                  <option value="inventory">Inventory</option>
                  <option value="demand">Demand</option>
                  <option value="forecast">Forecast</option>
                </select>
              </label>
            </div>

            {visibleExceptions.length === 0 ? (
              <div className="exception-empty">
                <strong>No exceptions in this view</strong>
                <p>
                  This selection does not currently cross the chosen exception thresholds. Try a
                  different group or Store + SKU.
                </p>
              </div>
            ) : (
              <div className="exception-list">
                {visibleExceptions.map((exception, index) => (
                  <article
                    className={`exception-card exception-card--${exception.severity}`}
                    key={exception.exception_id}
                  >
                    <div className="exception-rank" aria-label={`Priority ${index + 1}`}>
                      {index + 1}
                    </div>
                    <div className="exception-main">
                      <div className="exception-card-heading">
                        <div>
                          <span
                            className={`exception-severity exception-severity--${exception.severity}`}
                          >
                            {exception.severity}
                          </span>
                          <span className="exception-status">{exception.status}</span>
                        </div>
                        <span>{formatMonth(exception.relevant_period)}</span>
                      </div>
                      <h3>{exception.title}</h3>
                      <p>{exception.description}</p>
                      <div className="exception-metric">
                        <div>
                          <span>Measured evidence</span>
                          <strong>{formatMetric(exception)}</strong>
                        </div>
                        <div>
                          <span>Priority score</span>
                          <strong>{exception.priority_score}</strong>
                        </div>
                        <div>
                          <span>Evidence source</span>
                          <strong>{evidenceSource(exception)}</strong>
                        </div>
                      </div>
                      <details className="exception-evidence">
                        <summary>Review supporting evidence</summary>
                        <dl>
                          {Object.entries(exception.evidence)
                            .slice(0, 6)
                            .map(([label, value]) => (
                              <div key={label}>
                                <dt>{formatEvidenceLabel(label)}</dt>
                                <dd>{formatEvidenceValue(value)}</dd>
                              </div>
                            ))}
                        </dl>
                      </details>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}
