export function LoadingState() {
  return (
    <div aria-live="polite" className="route-loading" role="status">
      <span className="loading-indicator" />
      Loading planning workspace…
    </div>
  );
}
