import { Link } from "react-router-dom";
import {
  useCategoryBreakdown,
  useDashboardSummary,
  useGenerateInsight,
  useInsights,
  useTimeline,
  useTrends,
} from "@/hooks/useQueries";
import { KpiTile } from "@/components/ui/KpiTile";
import { LoadingState, EmptyState } from "@/components/ui/LoadingState";
import { DemandChart } from "@/components/charts/DemandChart";
import { CategoryChart } from "@/components/charts/CategoryChart";
import { InsightPanel } from "@/components/ui/InsightPanel";
import { formatCompact, formatPercent, formatUnits } from "@/lib/format";

export function DashboardPage() {
  const summary = useDashboardSummary();
  const timeline = useTimeline();
  const trends = useTrends();
  const categories = useCategoryBreakdown();
  const insights = useInsights();
  const generateInsight = useGenerateInsight();

  const latestInsight = insights.data?.[0];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Demand Planning Dashboard</h1>
          <p className="page-subtitle">
            Portfolio-wide demand, forecast accuracy, and planning exceptions at a glance.
          </p>
        </div>
        <div className="page-actions">
          <Link to="/forecast" className="btn btn-primary">
            Run Forecast Cycle
          </Link>
        </div>
      </div>

      {summary.isLoading ? (
        <LoadingState label="Loading dashboard…" />
      ) : summary.data ? (
        <div className="grid grid-kpi" style={{ marginBottom: 20 }}>
          <KpiTile label="Active Products" value={formatUnits(summary.data.active_products)} />
          <KpiTile
            label="Recent Demand"
            value={formatCompact(summary.data.history_total_units)}
            delta={
              summary.data.demand_growth_pct !== null
                ? {
                    text: formatPercent(summary.data.demand_growth_pct, { signed: true }),
                    direction:
                      summary.data.demand_growth_pct > 0
                        ? "positive"
                        : summary.data.demand_growth_pct < 0
                          ? "negative"
                          : "neutral",
                  }
                : undefined
            }
          />
          <KpiTile label="Forecast (horizon)" value={formatCompact(summary.data.forecast_total_units)} />
          <KpiTile
            label="Avg. Forecast Accuracy"
            value={summary.data.average_wape !== null ? `${(100 - summary.data.average_wape).toFixed(0)}%` : "—"}
          />
          <KpiTile
            label="Open Exceptions"
            value={formatUnits(summary.data.open_exceptions)}
            delta={
              summary.data.critical_exceptions > 0
                ? { text: `${summary.data.critical_exceptions} critical`, direction: "negative" }
                : { text: "none critical", direction: "positive" }
            }
          />
        </div>
      ) : null}

      <div className="grid grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Demand: Actual vs. Forecast</h2>
              <p className="card-subtitle">Portfolio total, monthly</p>
            </div>
          </div>
          {timeline.isLoading ? (
            <LoadingState />
          ) : timeline.data ? (
            <DemandChart timeline={timeline.data} />
          ) : (
            <EmptyState title="No data yet" />
          )}
        </div>

        <InsightPanel
          insight={latestInsight}
          isGenerating={generateInsight.isPending}
          onGenerate={() => generateInsight.mutate({ scope: "portfolio" })}
        />
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Demand by Category</h2>
              <p className="card-subtitle">Recent actuals vs. latest forecast</p>
            </div>
          </div>
          {categories.isLoading ? <LoadingState /> : <CategoryChart data={categories.data ?? []} />}
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Trending Products</h2>
              <p className="card-subtitle">Recent window vs. prior window</p>
            </div>
          </div>
          {trends.isLoading ? (
            <LoadingState />
          ) : trends.data && (trends.data.growing.length > 0 || trends.data.declining.length > 0) ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <TrendList title="Growing" entries={trends.data.growing} tone="positive" />
              <TrendList title="Declining" entries={trends.data.declining} tone="negative" />
            </div>
          ) : (
            <EmptyState title="Not enough history yet" description="Trends need at least 6 periods of data." />
          )}
        </div>
      </div>
    </div>
  );
}

function TrendList({
  title,
  entries,
  tone,
}: {
  title: string;
  entries: { product_id: number; sku: string; name: string; growth_pct: number }[];
  tone: "positive" | "negative";
}) {
  if (entries.length === 0) return null;
  return (
    <div>
      <p style={{ fontSize: 11.5, fontWeight: 700, textTransform: "uppercase", color: "var(--color-text-faint)", margin: "0 0 8px" }}>
        {title}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {entries.slice(0, 4).map((entry) => (
          <Link
            key={entry.product_id}
            to={`/products/${entry.product_id}`}
            style={{ display: "flex", justifyContent: "space-between", textDecoration: "none", fontSize: 13 }}
          >
            <span style={{ color: "var(--color-text)" }}>{entry.name}</span>
            <span className={`kpi-delta ${tone}`}>{formatPercent(entry.growth_pct, { signed: true })}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
