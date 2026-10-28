import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AssessmentRecord, DashboardResponse, GraphResponse } from "../api/types";
import { GraphView } from "../components/GraphView";
import { Icon } from "../components/Icons";
import {
  EmptyState,
  ErrorNotice,
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
  shortHash,
} from "../utils/format";

export function CompanyPage() {
  const { companyId } = useParams<{ companyId: string }>();
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    try {
      const [nextDashboard, nextGraph] = await Promise.all([
        api.dashboard(companyId),
        api.graph(companyId, 1).catch(() => null),
      ]);
      setDashboard(nextDashboard);
      setGraph(nextGraph);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this company.");
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    void load();
  }, [load]);

  const assessments = useMemo(() => dashboard?.assessments ?? [], [dashboard]);
  const latest = dashboard?.latest_assessment ?? null;
  const latestDocument = useMemo(() => {
    if (!latest) return null;
    return (
      dashboard?.documents.find((document) => document.hash === latest.document_hash) ?? null
    );
  }, [dashboard, latest]);

  if (loading) {
    return (
      <div className="loading-page">
        <Spinner label="Loading company record" />
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="stack">
        <ErrorNotice message={error ?? "Company not found."} onRetry={() => void load()} />
        <Link className="text-link" to="/">
          <Icon name="arrow" size={14} /> Back to overview
        </Link>
      </div>
    );
  }

  const company = dashboard.company;
  const finalRatios = latest
    ? {
        debt_to_equity: latest.final_debt_to_equity ?? latest.debt_to_equity,
        current_ratio: latest.final_current_ratio ?? latest.current_ratio,
        net_margin: latest.final_net_margin ?? latest.net_margin,
      }
    : null;

  return (
    <div className="stack">
      <section className="company-head">
        <div>
          <Link className="back-link" to="/">
            <Icon name="arrow" size={14} /> Overview
          </Link>
          <p className="eyebrow">Company record</p>
          <h2>{company.name ?? company.id}</h2>
          <p className="analysis-sub">
            <span className="mono">{company.id}</span>
            {company.description ? ` · ${company.description}` : ""}
          </p>
        </div>
        <div className="company-head-actions">
          <Link
            className="button button-secondary button-small"
            to={`/graph?company=${encodeURIComponent(company.id)}`}
          >
            <Icon name="graph" size={15} /> Graph explorer
          </Link>
          <Link
            className="button button-primary button-small"
            to={`/analyses/new${latest?.document_hash ? `?document=${encodeURIComponent(latest.document_hash)}` : ""}`}
          >
            New analysis <Icon name="arrow" size={15} />
          </Link>
        </div>
      </section>

      <section className="metric-grid">
        <div className="bento-card metric-card">
          <span className="metric-label">Direct relationships</span>
          <strong className="metric-value">{fmtNumber(company.relationship_count, 0)}</strong>
          <span className="metric-hint">Typed RELATION edges</span>
        </div>
        <div className="bento-card metric-card">
          <span className="metric-label">Assessments</span>
          <strong className="metric-value">{fmtNumber(company.assessment_count, 0)}</strong>
          <span className="metric-hint">Across ingested documents</span>
        </div>
        <div className="bento-card metric-card">
          <span className="metric-label">Graph entities</span>
          <strong className="metric-value">{fmtNumber(dashboard.totals.entities ?? 0, 0)}</strong>
          <span className="metric-hint">Workspace total</span>
        </div>
        <div className="bento-card metric-card">
          <span className="metric-label">Registry documents</span>
          <strong className="metric-value">{fmtNumber(dashboard.documents.length, 0)}</strong>
          <span className="metric-hint">Ingested PDFs</span>
        </div>
      </section>

      <section className="bento company-grid">
        <Panel
          className="span-7"
          eyebrow="Latest assessment"
          title={latest ? `Risk on ${latest.document_filename ?? "current document"}` : "No assessment yet"}
          action={
            latest ? (
              <StatusBadge status={latest.status} />
            ) : undefined
          }
        >
          {latest ? (
            <div className="assessment-detail">
              <div className="assessment-top">
                <div>
                  <span className="score-caption">
                    {latest.overridden ? "Analyst-approved risk" : "System risk"}
                  </span>
                  <RiskBadge level={latest.final_risk_level ?? latest.risk_level} large />
                </div>
                <div className="assessment-meta">
                  <span>
                    System level <strong>{riskLevel(latest.risk_level)}</strong>
                  </span>
                  {latest.overridden && (
                    <span>
                      Override <strong>Yes</strong>
                    </span>
                  )}
                  <span>
                    Reviewer <strong>{latest.approved_by ?? "Pending"}</strong>
                  </span>
                </div>
              </div>

              <div className="ratio-grid">
                <div>
                  <span>Debt / equity</span>
                  <strong>{fmtRatio(finalRatios?.debt_to_equity)}</strong>
                </div>
                <div>
                  <span>Current ratio</span>
                  <strong>{fmtRatio(finalRatios?.current_ratio)}</strong>
                </div>
                <div>
                  <span>Net margin</span>
                  <strong>{fmtPercent(finalRatios?.net_margin)}</strong>
                </div>
              </div>

              {(latest.final_notes.length > 0 || latest.notes.length > 0) && (
                <div className="context-box">
                  <span className="note-label">Ratio notes</span>
                  <ul className="note-list">
                    {(latest.final_notes.length > 0 ? latest.final_notes : latest.notes).map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}

              {latest.edit_notes && (
                <div className="context-box">
                  <span className="note-label">Reviewer note</span>
                  <p>{latest.edit_notes}</p>
                </div>
              )}

              <div className="score-foot">
                <span>
                  <Icon name="document" size={14} />{" "}
                  {latestDocument?.filename ?? latest.document_filename ?? "Document context unavailable"}
                </span>
                <span>
                  {latest.approved_at
                    ? `Approved ${fmtDate(latest.approved_at)}`
                    : `Created ${fmtDate(latest.created_at)}`}
                </span>
              </div>

              {latest.review_events.length > 0 && (
                <div className="context-box">
                  <span className="note-label">Review trail</span>
                  <ol className="compact-timeline">
                    {latest.review_events.map((event, index) => (
                      <li key={event.id ?? `${index}-${event.at}`}>
                        <span className={`timeline-dot action-${event.action ?? "event"}`} />
                        <div>
                          <strong>{event.action ?? "event"}</strong>
                          <span>
                            {" "}
                            by {event.reviewer ?? "analyst"} · {fmtDate(event.at)}
                          </span>
                          {event.notes && <p>{event.notes}</p>}
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          ) : (
            <EmptyState
              title="No risk assessment recorded"
              body="A draft assessment appears after a document is ingested. If it is missing, start an analysis on a completed document."
              action={
                <Link className="button button-primary button-small" to="/analyses/new">
                  Start an analysis
                </Link>
              }
            />
          )}
        </Panel>

        <Panel
          className="span-5"
          eyebrow="Graph context"
          title="Relationship map"
          action={
            <Link
              className="text-link"
              to={`/graph?company=${encodeURIComponent(company.id)}`}
            >
              Expand <Icon name="arrow" size={14} />
            </Link>
          }
        >
          {graph && graph.nodes.length > 0 ? (
            <>
              <GraphView nodes={graph.nodes} edges={graph.edges} height={330} />
              <div className="graph-footnote">
                <span>
                  {fmtNumber(graph.nodes.length, 0)} nodes · {fmtNumber(graph.edges.length, 0)} edges
                </span>
                {graph.truncated && <span className="text-warn">View truncated for safety</span>}
              </div>
            </>
          ) : (
            <EmptyState
              title="No relationships found"
              body="This company has no recorded relationships yet. Ingest a source document that mentions it."
            />
          )}
        </Panel>
      </section>

      <section className="bento company-grid">
        <Panel className="span-7" eyebrow="History" title="Assessment ledger">
          {assessments.length === 0 ? (
            <EmptyState
              title="No assessments"
              body="Once the Auditor and Quant complete, the draft assessment appears here."
            />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>System</th>
                    <th>Final</th>
                    <th>Status</th>
                    <th>Reviewer</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {assessments.map((assessment) => (
                    <AssessmentRow key={assessment.id} assessment={assessment} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel className="span-5" eyebrow="Source documents" title="Document context">
          {dashboard.documents.length === 0 ? (
            <EmptyState
              title="No documents in the registry"
              body="Upload a financial PDF to create document context for this company."
            />
          ) : (
            <div className="linked-documents">
              {dashboard.documents.slice(0, 6).map((document) => {
                const linked = assessments.some(
                  (assessment) => assessment.document_hash === document.hash,
                );
                return (
                  <div className="linked-document" key={document.hash}>
                    <span className="document-icon">
                      <Icon name="document" size={17} />
                    </span>
                    <div>
                      <strong>{document.filename ?? shortHash(document.hash)}</strong>
                      <span>
                        #{shortHash(document.hash)} · {fmtNumber(document.entity_count ?? 0, 0)} entities
                      </span>
                    </div>
                    {linked ? (
                      <span className="link-flag">Assessed</span>
                    ) : (
                      <Link
                        className="text-link"
                        to={`/analyses/new?document=${encodeURIComponent(document.hash)}`}
                      >
                        Analyze
                      </Link>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Panel>
      </section>
    </div>
  );
}

function AssessmentRow({ assessment }: { assessment: AssessmentRecord }) {
  return (
    <tr>
      <td>
        <span className="table-primary">
          {assessment.document_filename ?? "Unknown document"}
        </span>
        <span className="table-sub">#{shortHash(assessment.document_hash)}</span>
      </td>
      <td>
        <RiskBadge level={assessment.risk_level} />
      </td>
      <td>
        <RiskBadge level={assessment.final_risk_level ?? assessment.risk_level} />
      </td>
      <td>
        <StatusBadge status={assessment.status} />
      </td>
      <td>{assessment.approved_by ?? "—"}</td>
      <td>
        {fmtDate(assessment.approved_at ?? assessment.created_at)}
        {assessment.overridden && <span className="override-tag">Override</span>}
      </td>
    </tr>
  );
}
