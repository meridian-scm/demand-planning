import { useState } from "react";
import { useForecastRuns, useRunForecast } from "@/hooks/useQueries";
import { LoadingState, EmptyState, ErrorBanner } from "@/components/ui/LoadingState";
import { apiErrorMessage } from "@/api/client";
import { formatDateTime, MODEL_LABEL } from "@/lib/format";
import type { ForecastModel } from "@/types/api";

const MODEL_OPTIONS: ForecastModel[] = [
  "auto",
  "naive",
  "moving_average",
  "linear_trend",
  "holt_linear",
  "holt_winters",
  "seasonal_naive",
];

export function ForecastRunPage() {
  const [horizon, setHorizon] = useState(6);
  const [model, setModel] = useState<ForecastModel>("auto");

  const runs = useForecastRuns();
  const runForecast = useRunForecast();

  function handleRun() {
    runForecast.mutate({ horizon, model, detect_exceptions: true });
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Run Forecast Cycle</h1>
          <p className="page-subtitle">
            Forecasts every active product, backtests candidate models, and refreshes planning
            exceptions in one pass.
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="grid" style={{ gridTemplateColumns: "160px 220px 1fr", alignItems: "end", gap: 16 }}>
          <div className="field">
            <label htmlFor="horizon">Horizon (months)</label>
            <input
              id="horizon"
              type="number"
              className="input"
              min={1}
              max={36}
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label htmlFor="model">Model</label>
            <select id="model" className="select" value={model} onChange={(e) => setModel(e.target.value as ForecastModel)}>
              {MODEL_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {MODEL_LABEL[option]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <button className="btn btn-primary" onClick={handleRun} disabled={runForecast.isPending}>
              {runForecast.isPending ? "Running…" : "Run Forecast Cycle"}
            </button>
          </div>
        </div>

        {runForecast.isError && (
          <div style={{ marginTop: 14 }}>
            <ErrorBanner message={apiErrorMessage(runForecast.error)} />
          </div>
        )}
        {runForecast.isSuccess && (
          <div className="alert-banner alert-success" style={{ marginTop: 14 }}>
            Forecast complete: {runForecast.data.products_forecasted} product(s) forecasted,{" "}
            {runForecast.data.products_skipped} skipped for insufficient history.
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Run History</h2>
          </div>
        </div>
        {runs.isLoading ? (
          <LoadingState />
        ) : runs.data && runs.data.length > 0 ? (
          <div className="scrollable">
            <table className="table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Model</th>
                  <th>Horizon</th>
                  <th>Forecasted</th>
                  <th>Skipped</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((run) => (
                  <tr key={run.id}>
                    <td>{run.run_label}</td>
                    <td>{MODEL_LABEL[run.requested_model] ?? run.requested_model}</td>
                    <td>{run.horizon_periods} mo</td>
                    <td>{run.products_forecasted}</td>
                    <td>{run.products_skipped}</td>
                    <td>{formatDateTime(run.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No forecast runs yet" description="Run a cycle above to get started." />
        )}
      </div>
    </div>
  );
}
