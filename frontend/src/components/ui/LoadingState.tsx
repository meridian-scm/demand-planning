export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="loading-row" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="empty-state">
      <p style={{ fontWeight: 600, color: "var(--color-text-muted)", margin: "0 0 4px" }}>{title}</p>
      {description && <p style={{ margin: 0, fontSize: 12.5 }}>{description}</p>}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="alert-banner alert-error" role="alert">
      {message}
    </div>
  );
}
