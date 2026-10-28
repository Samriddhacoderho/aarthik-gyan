import { Link } from "react-router-dom";
import { Icon } from "../components/Icons";

export function NotFoundPage() {
  return (
    <div className="not-found">
      <span className="not-found-code">404</span>
      <h2>This page is not in the ledger.</h2>
      <p>The route does not exist, or the analysis session was lost when the API restarted.</p>
      <div className="not-found-actions">
        <Link className="button button-primary" to="/">
          Back to overview
        </Link>
        <Link className="button button-secondary" to="/documents">
          Open documents <Icon name="arrow" size={15} />
        </Link>
      </div>
    </div>
  );
}
