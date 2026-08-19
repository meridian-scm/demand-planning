import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="empty-state">
      <p style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>Page not found</p>
      <Link to="/" className="btn btn-primary">
        Back to dashboard
      </Link>
    </div>
  );
}
