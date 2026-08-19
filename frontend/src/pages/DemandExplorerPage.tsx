import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

export default function DemandExplorerPage() {
  return (
    <div className="page">
      <PageHeader
        description="Review history, forecasts, uncertainty, signals, and inventory risk at the Store + SKU grain."
        eyebrow="Core workflow"
        title="Demand Explorer"
      />
      <div aria-label="Demand filters" className="filter-shell">
        <div>
          <span>Store</span>
          <strong>Not available</strong>
        </div>
        <div>
          <span>SKU or product</span>
          <strong>Reference catalog required</strong>
        </div>
        <button disabled type="button">
          Explore demand
        </button>
      </div>
      <EmptyState
        description="Store and SKU selection will become available when the synthetic reference artifacts and catalog API are implemented."
        eyebrow="Selection required"
        title="Choose a Store + SKU to begin"
      />
    </div>
  );
}
