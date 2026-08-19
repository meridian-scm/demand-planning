import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

export default function OverviewPage() {
  return (
    <div className="page">
      <PageHeader
        description="A focused starting point for portfolio health, forecast reliability, and planning priorities."
        eyebrow="Portfolio"
        title="Overview"
      />
      <div className="foundation-banner" role="note">
        <span className="foundation-banner-icon" aria-hidden="true">
          01
        </span>
        <div>
          <strong>The application foundation is ready.</strong>
          <p>Planning summaries will appear after the reference-data pipeline is implemented.</p>
        </div>
      </div>
      <EmptyState
        description="The overview will prioritize material changes and exceptions once validated reference artifacts are available."
        eyebrow="Awaiting reference data"
        title="No portfolio summary yet"
      >
        <p className="supporting-copy">
          No placeholder KPIs are shown because Meridian does not fabricate planning results.
        </p>
      </EmptyState>
    </div>
  );
}
