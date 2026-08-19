import { useRef, useState } from "react";
import { useUploadSalesCsv } from "@/hooks/useQueries";
import { apiErrorMessage } from "@/api/client";
import { ErrorBanner } from "@/components/ui/LoadingState";
import type { IngestionReport } from "@/types/api";

export function DataUploadPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [report, setReport] = useState<IngestionReport | null>(null);
  const uploadCsv = useUploadSalesCsv();

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setReport(null);
    uploadCsv.mutate(file, {
      onSuccess: (data) => setReport(data),
    });
    event.target.value = "";
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Upload Sales History</h1>
          <p className="page-subtitle">
            Import monthly demand actuals from a CSV export. Existing (product, period) rows are
            updated in place — re-uploading a corrected file is always safe.
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <h2 className="card-title" style={{ marginBottom: 8 }}>
          Expected columns
        </h2>
        <p style={{ fontSize: 13, color: "var(--color-text-muted)", marginBottom: 14 }}>
          Required: <code>sku</code>, <code>period_start</code> (any parseable date — snapped to the
          1st of the month), <code>units_sold</code>. Optional: <code>revenue</code>,{" "}
          <code>location_code</code>, <code>channel</code>. Column names are matched flexibly — e.g.{" "}
          <code>Item Code</code>, <code>Month</code>, and <code>Quantity</code> are all recognised.
        </p>
        <pre
          style={{
            background: "var(--color-bg)",
            border: "1px solid var(--color-border-soft)",
            borderRadius: 8,
            padding: 12,
            fontSize: 12,
            overflowX: "auto",
          }}
        >
{`sku,period_start,units_sold,revenue,location_code
SKU-1001,2025-01-01,120,4320.00,DC-EAST
SKU-1001,2025-02-01,135,4860.00,DC-EAST`}
        </pre>

        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          onChange={handleFileChange}
          style={{ display: "none" }}
        />
        <button
          className="btn btn-primary"
          style={{ marginTop: 12 }}
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadCsv.isPending}
        >
          {uploadCsv.isPending ? "Uploading…" : "Choose CSV File"}
        </button>

        {uploadCsv.isError && (
          <div style={{ marginTop: 14 }}>
            <ErrorBanner message={apiErrorMessage(uploadCsv.error)} />
          </div>
        )}
      </div>

      {report && (
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: 12 }}>
            Import Result
          </h2>
          <div className="grid grid-kpi" style={{ marginBottom: report.errors.length > 0 ? 16 : 0 }}>
            <div className="kpi-tile">
              <p className="kpi-label">Rows Received</p>
              <p className="kpi-value">{report.rows_received}</p>
            </div>
            <div className="kpi-tile">
              <p className="kpi-label">Imported</p>
              <p className="kpi-value" style={{ color: "var(--color-success)" }}>
                {report.rows_imported}
              </p>
            </div>
            <div className="kpi-tile">
              <p className="kpi-label">Updated</p>
              <p className="kpi-value" style={{ color: "var(--color-primary)" }}>
                {report.rows_updated}
              </p>
            </div>
            <div className="kpi-tile">
              <p className="kpi-label">Rejected</p>
              <p className="kpi-value" style={{ color: report.rows_rejected > 0 ? "var(--color-danger)" : undefined }}>
                {report.rows_rejected}
              </p>
            </div>
          </div>

          {report.errors.length > 0 && (
            <div className="scrollable">
              <table className="table">
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>Error</th>
                  </tr>
                </thead>
                <tbody>
                  {report.errors.map((error, index) => (
                    <tr key={index}>
                      <td>{error.line}</td>
                      <td>{error.error}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
