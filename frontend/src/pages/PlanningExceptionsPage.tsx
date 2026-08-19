import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

export default function PlanningExceptionsPage() {
  return (
    <div className="page">
      <PageHeader
        description="Review evidence-backed demand and inventory conditions in priority order."
        eyebrow="Attention queue"
        title="Planning Exceptions"
      />
      <EmptyState
        description="The exception queue will be populated by later trend, anomaly, forecast, and inventory-risk workflows."
        eyebrow="Coming in a later step"
        title="No planning exceptions available"
      />
    </div>
  );
}
