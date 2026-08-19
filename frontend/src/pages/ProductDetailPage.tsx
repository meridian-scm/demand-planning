import { useParams } from "react-router-dom";
import { useGenerateInsight, useInsights, useProductDetail } from "@/hooks/useQueries";
import { LoadingState, ErrorBanner, EmptyState } from "@/components/ui/LoadingState";
import { DemandChart } from "@/components/charts/DemandChart";
import { InsightPanel } from "@/components/ui/InsightPanel";
import { Badge } from "@/components/ui/Badge";
import { apiErrorMessage } from "@/api/client";
import { EXCEPTION_TYPE_LABEL, MODEL_LABEL, formatMonth, formatPercent, formatUnits } from "@/lib/format";

export function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const productId = params.id ? Number(params.id) : undefined;

  const detail = useProductDetail(productId);
  const insights = useInsights(productId);
  const generateInsight = useGenerateInsight();

  if (detail.isLoading) return <LoadingState label="Loading product…" />;
  if (detail.isError) return <ErrorBanner message={apiErrorMessage(detail.error)} />;
  if (!detail.data) return <EmptyState title="Product not found" />;

  const { product, timeline, exceptions } = detail.data;
  const latestInsight = insights.data?.[0];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            {product.name} <span style={{ color: "var(--color-text-faint)", fontWeight: 500 }}>· {product.sku}</span>
          </h1>
          <p className="page-subtitle">
            {product.category}
            {product.subcategory ? ` · ${product.subcategory}` : ""} · Lead time {product.lead_time_days}d ·
            Safety stock {product.safety_stock_units} units
          </p>
        </div>
      </div>

      <div className="grid grid-kpi" style={{ marginBottom: 20 }}>
        <div className="kpi-tile">
          <p className="kpi-label">Recent Demand</p>
          <p className="kpi-value">{formatUnits(detail.data.history_total_units)}</p>
        </div>
        <div className="kpi-tile">
          <p className="kpi-label">Forecast (horizon)</p>
          <p className="kpi-value">{formatUnits(detail.data.forecast_total_units)}</p>
        </div>
        <div className="kpi-tile">
          <p className="kpi-label">Model Used</p>
          <p className="kpi-value" style={{ fontSize: 18 }}>
            {detail.data.model_used ? MODEL_LABEL[detail.data.model_used] ?? detail.data.model_used : "—"}
          </p>
        </div>
        <div className="kpi-tile">
          <p className="kpi-label">Forecast Accuracy</p>
          <p className="kpi-value">{detail.data.wape !== null ? `${(100 - detail.data.wape).toFixed(0)}%` : "—"}</p>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Demand: Actual vs. Forecast</h2>
            </div>
          </div>
          <DemandChart timeline={timeline} />
        </div>

        <InsightPanel
          insight={latestInsight}
          isGenerating={generateInsight.isPending}
          onGenerate={() => generateInsight.mutate({ scope: "product", product_id: productId })}
        />
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Open Exceptions</h2>
            <p className="card-subtitle">{exceptions.length} open for this product</p>
          </div>
        </div>
        {exceptions.length === 0 ? (
          <EmptyState title="No open exceptions" description="This product is planning within tolerance." />
        ) : (
          <div className="scrollable">
            <table className="table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Period</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {exceptions.map((exception) => (
                  <tr key={exception.id}>
                    <td>{EXCEPTION_TYPE_LABEL[exception.exception_type] ?? exception.exception_type}</td>
                    <td>
                      <Badge variant={exception.severity} />
                    </td>
                    <td>{formatMonth(exception.detected_for_period)}</td>
                    <td style={{ maxWidth: 480 }}>{exception.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {detail.data.mape !== null && (
        <p style={{ marginTop: 12, fontSize: 12, color: "var(--color-text-faint)" }}>
          Backtest error: {formatPercent(detail.data.mape)} MAPE, {formatPercent(detail.data.wape)} WAPE
        </p>
      )}
    </div>
  );
}
