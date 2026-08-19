import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { useExceptions, useUpdateExceptionStatus } from "@/hooks/useQueries";
import { LoadingState, EmptyState, ErrorBanner } from "@/components/ui/LoadingState";
import { Badge } from "@/components/ui/Badge";
import { apiErrorMessage } from "@/api/client";
import { EXCEPTION_TYPE_LABEL, formatMonth } from "@/lib/format";

const STATUS_FILTERS = ["open", "acknowledged", "resolved", "dismissed"] as const;
const SEVERITY_FILTERS = ["critical", "high", "medium", "low"] as const;

export function ExceptionsPage() {
  const [status, setStatus] = useState<string>("open");
  const [severity, setSeverity] = useState<string | undefined>(undefined);

  const exceptions = useExceptions({ status: status || undefined, severity });
  const updateStatus = useUpdateExceptionStatus();

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Planning Exceptions</h1>
          <p className="page-subtitle">Demand spikes, drops, stockout and excess-inventory risks.</p>
        </div>
      </div>

      <div className="tag-row">
        <button className={clsx("chip", !status && "active")} onClick={() => setStatus("")}>
          All statuses
        </button>
        {STATUS_FILTERS.map((item) => (
          <button
            key={item}
            className={clsx("chip", status === item && "active")}
            onClick={() => setStatus(item)}
          >
            {item[0].toUpperCase() + item.slice(1)}
          </button>
        ))}
        <span style={{ width: 1, background: "var(--color-border)", margin: "0 4px" }} />
        <button className={clsx("chip", !severity && "active")} onClick={() => setSeverity(undefined)}>
          All severities
        </button>
        {SEVERITY_FILTERS.map((item) => (
          <button
            key={item}
            className={clsx("chip", severity === item && "active")}
            onClick={() => setSeverity(item)}
          >
            {item[0].toUpperCase() + item.slice(1)}
          </button>
        ))}
      </div>

      <div className="card">
        {exceptions.isLoading ? (
          <LoadingState />
        ) : exceptions.isError ? (
          <ErrorBanner message={apiErrorMessage(exceptions.error)} />
        ) : exceptions.data && exceptions.data.length > 0 ? (
          <div className="scrollable">
            <table className="table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Product</th>
                  <th>Type</th>
                  <th>Period</th>
                  <th>Message</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {exceptions.data.map((exception) => (
                  <tr key={exception.id}>
                    <td>
                      <Badge variant={exception.severity} />
                    </td>
                    <td>
                      <Link to={`/products/${exception.product_id}`} style={{ fontWeight: 600, textDecoration: "none" }}>
                        {exception.product_sku ?? exception.product_id}
                      </Link>
                      <div style={{ fontSize: 11.5, color: "var(--color-text-faint)" }}>{exception.product_name}</div>
                    </td>
                    <td>{EXCEPTION_TYPE_LABEL[exception.exception_type] ?? exception.exception_type}</td>
                    <td>{formatMonth(exception.detected_for_period)}</td>
                    <td style={{ maxWidth: 420 }}>
                      <div>{exception.message}</div>
                      {exception.recommendation && (
                        <div style={{ fontSize: 11.5, color: "var(--color-text-faint)", marginTop: 3 }}>
                          → {exception.recommendation}
                        </div>
                      )}
                    </td>
                    <td>
                      <Badge variant={exception.status} />
                    </td>
                    <td>
                      {exception.status === "open" && (
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            className="btn btn-sm"
                            disabled={updateStatus.isPending}
                            onClick={() => updateStatus.mutate({ id: exception.id, status: "acknowledged" })}
                          >
                            Ack
                          </button>
                          <button
                            className="btn btn-sm"
                            disabled={updateStatus.isPending}
                            onClick={() => updateStatus.mutate({ id: exception.id, status: "resolved" })}
                          >
                            Resolve
                          </button>
                        </div>
                      )}
                      {exception.status === "acknowledged" && (
                        <button
                          className="btn btn-sm"
                          disabled={updateStatus.isPending}
                          onClick={() => updateStatus.mutate({ id: exception.id, status: "resolved" })}
                        >
                          Resolve
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No exceptions match these filters" />
        )}
      </div>
    </div>
  );
}
