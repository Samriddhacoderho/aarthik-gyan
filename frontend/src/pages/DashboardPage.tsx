import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  CompanySummary,
  DashboardResponse,
  DocumentSummary,
  ReadinessResponse,
} from "../api/types";
import { Icon } from "../components/Icons";
import {
  EmptyState,
  ErrorNotice,
  Metric,
  Panel,
  RiskBadge,
  Spinner,
  StatusBadge,
} from "../components/Ui";
import {
  fmtDate,
  fmtNumber,
  fmtPercent,
  fmtRatio,
  riskLevel,
  scoreValue,
  shortHash,
  titleCase,
} from "../utils/format";

interface OverviewState {
  documents: DocumentSummary[];
  companies: CompanySummary[];
  dashboard: DashboardResponse | null;
  readiness: ReadinessResponse | null;
}

const CHECK_LABELS: Record<string, string> = {
  neo4j: "Graph database",
  qdrant: "Evidence index",
};

export function DashboardPage() {
  const [state, setState] = useState<OverviewState>({
    documents: [],
    companies: [],
    dashboard: null,
    readiness: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [documents, companies, readiness] = await Promise.all([
        api.documents(),
        api.companies(),
        api.ready().catch(() => null),
      ]);
      let dashboard: DashboardResponse | null = null;
      if (companies.length > 0) {
        dashboard = await api.dashboard(companies[0].id).catch(() => null);
      }
      setState({ documents, companies, dashboard, readiness });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the workspace.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const latest = state.dashboard?.latest_assessment ?? null;
  const finalLevel = riskLevel(latest?.final_risk_level ?? latest?.risk_level);
  const finalScore = {
    debt_to_equity: latest?.final_debt_to_equity ?? latest?.debt_to_equity,
    current_ratio: latest?.final_current_ratio ?? latest?.current_ratio,
    net_margin: latest?.final_net_margin ?? latest?.net_margin,
  };
  const latestDocument = state.documents.find(
    (document) => document.hash === latest?.document_hash,
  );
  const completed = state.documents.filter((document) => document.status === "completed").length;
  const partial = state.documents.filter((document) => document.status === "partial").length;

  return (
    <div className="stack">
      {error && <ErrorNotice message={error} onRetry={() => void load()} />}

      <section className="bento hero-grid">
        <div className="bento-card hero-card span-8">
          <p className="eyebrow">Auditable analysis for finance teams</p>
          <h2 className="hero-title">
            Read the report.
            <br />
            Interrogate the graph.
            <br />
            <em>Approve the risk.</em>
          </h2>
          <p className="hero-copy">
            A working review desk for chartered accountants and finance teams. Ingest a financial
            PDF, trace the graph evidence, and pause at a human checkpoint before any report is
            finalised.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/documents">
              <Icon name="upload" size={17} />
              Upload a report
            </Link>
            <Link className="button button-secondary" to="/analyses/new">
              Start an analysis
              <Icon name="arrow" size={16} />
            </Link>
          </div>
          <div className="hero-rule">
            <span>Auditor → Quant → Review → Report</span>
          </div>
        </div>

        <div className="bento-card span-4 readiness-card">
          <div className="panel-head bare">
            <div>
              <p className="eyebrow">Workspace status</p>
              <h2 className="panel-title">Live checks</h2>
            </div>
            <span className={`status-dot ${state.readiness?.status === "ready" ? "ok" : "warn"}`} />
          </div>
          {state.readiness ? (
            <div className="check-list">
              {state.readiness.checks.map((check) => (
                <div className="check-row" key={check.name}>
                  <span className={`check-icon ${check.ok ? "ok" : "bad"}`}>
                    <Icon name={check.ok ? "check" : "alert"} size={13} />
                  </span>
                  <div>
                    <strong>{CHECK_LABELS[check.name] ?? titleCase(check.name)}</strong>
                    <small>{check.ok ? "Connected" : "Unavailable"}</small>
                  </div>
                </div>
              ))}
              <div className="check-note">
                An analysis needs every check above to pass.
              </div>
            </div>
          ) : (
            <div className="check-list">
              <div className="check-note">
                Status is temporarily unavailable. Try again shortly.
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="metric-grid">
        <div className="bento-card metric-card">
          <Metric
            label="Documents"
            value={loading ? "—" : state.documents.length}
            hint={`${completed} completed${partial ? ` · ${partial} partial` : ""}`}
          />
        </div>
        <div className="bento-card metric-card">
          <Metric label="Companies" value={loading ? "—" : state.companies.length} hint="Entities in the graph" />
        </div>
        <div className="bento-card metric-card">
          <Metric
            label="Graph entities"
            value={loading ? "—" : fmtNumber(state.dashboard?.totals.entities ?? 0, 0)}
            hint="Across the current graph"
          />
        </div>
        <div className="bento-card metric-card">
          <Metric
            label="Relationships"
            value={loading ? "—" : fmtNumber(state.dashboard?.totals.relationships ?? 0, 0)}
            hint="Links between entities"
          />
        </div>
      </section>

      <section className="bento content-grid">
        <Panel
          className="span-7"
          eyebrow="Document ledger"
          title="Recent reports"
          action={
            <Link className="text-link" to="/documents">
              View all <Icon name="arrow" size={14} />
            </Link>
          }
        >
          {loading ? (
            <div className="loading-block">
              <Spinner label="Loading documents" />
            </div>
          ) : state.documents.length === 0 ? (
            <EmptyState
              title="No documents ingested"
              body="Upload a financial PDF to create the first document record in the graph."
              action={
                <Link className="button button-primary button-small" to="/documents">
                  Upload a PDF
                </Link>
              }
            />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Status</th>
                    <th>Entities</th>
                    <th>Ingested</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {state.documents.slice(0, 5).map((document) => (
                    <tr key={document.hash}>
                      <td>
                        <span className="table-primary">
                          {document.filename ?? shortHash(document.hash)}
                        </span>
                        <span className="table-sub">#{shortHash(document.hash)}</span>
                      </td>
                      <td>
                        <StatusBadge status={document.status} />
                      </td>
                      <td>{fmtNumber(document.entity_count ?? 0, 0)}</td>
                      <td>{fmtDate(document.ingested_at)}</td>
                      <td className="table-action">
                        <Link
                          className="text-link"
                          to={`/analyses/new?document=${encodeURIComponent(document.hash)}`}
                        >
                          Analyze <Icon name="arrow" size={13} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel
          className="span-5"
          eyebrow={state.dashboard?.company.name ? "Latest reviewed company" : "Risk desk"}
          title={state.dashboard?.company.name ?? "No company selected"}
          action={
            state.dashboard ? (
              <Link className="text-link" to={`/companies/${encodeURIComponent(state.dashboard.company.id)}`}>
                Open <Icon name="arrow" size={14} />
              </Link>
            ) : undefined
          }
        >
          {latest ? (
            <div className="score-stack">
              <div className="score-head">
                <RiskBadge level={finalLevel} large />
                <span className="score-status">
                  <StatusBadge status={latest.status} />
                  {latest.overridden && <span className="override-tag">Analyst override</span>}
                </span>
              </div>
              <div className="ratio-grid">
                <div>
                  <span>Debt / equity</span>
                  <strong>{fmtRatio(finalScore.debt_to_equity)}</strong>
                </div>
                <div>
                  <span>Current ratio</span>
                  <strong>{fmtRatio(finalScore.current_ratio)}</strong>
                </div>
                <div>
                  <span>Net margin</span>
                  <strong>{fmtPercent(finalScore.net_margin)}</strong>
                </div>
              </div>
              <div className="score-foot">
                <span>
                  {latestDocument?.filename ??
                    latest.document_filename ??
                    "Document context unavailable"}
                </span>
                <span>{fmtDate(latest.approved_at ?? latest.created_at)}</span>
              </div>
              <Link className="button button-secondary button-small" to="/analyses/new">
                Start a fresh review
                <Icon name="arrow" size={15} />
              </Link>
            </div>
          ) : (
            <EmptyState
              title="No reviewed risk yet"
              body="Run the Auditor and Quant workflow to produce a draft score, then approve or override it at the human checkpoint."
              action={
                <Link className="button button-secondary button-small" to="/analyses/new">
                  Start an analysis
                </Link>
              }
            />
          )}
        </Panel>
      </section>

      <section className="bento flow-grid">
        <div className="bento-card span-4 flow-step">
          <span className="step-number">01</span>
          <Icon name="upload" size={20} />
          <h3>Ingest the source</h3>
          <p>Text extraction, entity resolution, and searchable evidence indexing.</p>
        </div>
        <div className="bento-card span-4 flow-step">
          <span className="step-number">02</span>
          <Icon name="graph" size={20} />
          <h3>Inspect the evidence</h3>
          <p>Auditor findings, graph centrality, prior assessments and document passages.</p>
        </div>
        <div className="bento-card span-4 flow-step">
          <span className="step-number">03</span>
          <Icon name="shield" size={20} />
          <h3>Approve the decision</h3>
          <p>Pause at the human review checkpoint. Only a confirmed approval finalises the report.</p>
        </div>
      </section>
    </div>
  );
}
