import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="page not-found">
      <p className="eyebrow">404</p>
      <h1>That planning view does not exist.</h1>
      <p>Return to the overview to continue working in Meridian.</p>
      <Link className="text-link" to="/">
        Return to overview
      </Link>
    </div>
  );
}
