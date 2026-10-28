import type { ReactNode } from "react";
import { Icon } from "./Icons";
import { riskLevel, titleCase } from "../utils/format";

export function Panel({
  title,
  eyebrow,
  action,
  children,
  className = "",
}: {
  title?: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`.trim()}>
      {(title || eyebrow || action) && (
        <header className="panel-head">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <h2 className="panel-title">{title}</h2>}
          </div>
          {action && <div className="panel-action">{action}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function RiskBadge({ level, large = false }: { level: unknown; large?: boolean }) {
  const normalized = riskLevel(level);
  return (
    <span className={`risk-badge risk-${normalized.toLowerCase()} ${large ? "risk-large" : ""}`}>
      <span className="risk-dot" />
      {normalized}
    </span>
  );
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const value = (status ?? "unknown").toLowerCase();
  const tone =
    value === "completed" || value === "approved" || value === "ready" || value === "low"
      ? "good"
      : value === "partial" || value === "medium" || value === "draft"
        ? "warn"
        : value === "failed" || value === "high"
          ? "bad"
          : "neutral";
  return <span className={`status-badge status-${tone}`}>{titleCase(status ?? "unknown")}</span>;
}

export function Spinner({ label = "Working" }: { label?: string }) {
  return (
    <span className="spinner-wrap" role="status" aria-label={label}>
      <span className="spinner" />
      <span>{label}</span>
    </span>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-mark">
        <Icon name="document" size={22} />
      </div>
      <h3>{title}</h3>
      <p>{body}</p>
      {action}
    </div>
  );
}

export function ErrorNotice({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-notice" role="alert">
      <Icon name="alert" size={18} />
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="text-button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {hint && <span className="metric-hint">{hint}</span>}
    </div>
  );
}
