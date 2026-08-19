import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

export default function ForecastRunsPage() {
  return (
    <div className="page">
      <PageHeader
        description="Inspect auditable model evaluations, training cutoffs, and published reference forecasts."
        eyebrow="Forecast governance"
        title="Forecast Runs"
      />
      <EmptyState
        description="Run metadata will appear after the offline forecasting pipeline and immutable artifacts are implemented."
        eyebrow="Coming in a later step"
        title="No forecast runs available"
      />
    </div>
  );
}
