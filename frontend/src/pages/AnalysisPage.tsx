import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  AnalysisResponse,
  EvidenceHit,
  ReviewAction,
  ReviewPayload,
  ReviewRequest,
  RiskLevel,
} from "../api/types";
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
  asNumber,
  fmtDate,
  fmtPercent,
  fmtRatio,
  riskLevel,
  scoreValue,
  shortHash,
  titleCase,
} from "../utils/format";

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

interface ScoreLike {
  debt_to_equity?: unknown;
  current_ratio?: unknown;
  net_margin?: unknown;
  risk_level?: unknown;
  notes?: unknown;
}

function scoreOf(value: Record<string, unknown> | null): ScoreLike {
  return value ?? {};
}

export function AnalysisPage() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    if (!analysisId) return;
    let cancelled = false;

    (async () => {
      try {
        const next = await api.analysis(analysisId);
        if (!cancelled) {
          setAnalysis(next);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load the analysis.");
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  // Poll whenever the backend reports a running workflow, including after a
  // review submission or a re-run. Status is the dependency, so polling stops
  // as soon as the next interrupt or completion arrives.
  useEffect(() => {
    if (!analysisId || analysis?.status !== "running") return;
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await api.analysis(analysisId);
        if (!cancelled) {
          setAnalysis(next);
          setPollError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setPollError(
            err instanceof Error ? err.message : "Could not refresh the analysis state.",
          );
        }
      }
    };
    const timer = window.setInterval(() => void tick(), 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [analysisId, analysis?.status]);

  if (loading) {
    return (
      <div className="loading-page">
        <Spinner label="Loading review workspace" />
      </div>
    );
  }
  if (error || !analysis) {
    return <ErrorNotice message={error ?? "Analysis not found."} />;
  }

  return (
    <div className="stack">
      {pollError && <ErrorNotice message={pollError} />}
      <section className="analysis-head">
        <div>
          <Link className="back-link" to="/">
            <Icon name="arrow" size={14} /> Overview
          </Link>
          <p className="eyebrow">Review workspace</p>
          <h2>{analysis.company_name}</h2>
          <p className="analysis-sub">
            {analysis.document_filename ?? "Untitled source"} · #{shortHash(analysis.document_hash)} ·{" "}
            {analysis.reviewer} · round {analysis.iteration} of {analysis.max_iterations}
          </p>
        </div>
        <div className="analysis-state">
          <StatusBadge status={analysis.status} />
          <span className="pill pill-quiet">
            <Icon name="clock" size={13} />
            Process-local session
          </span>
        </div>
      </section>

      <PhaseRail analysis={analysis} />

      {analysis.status === "failed" && (
        <ErrorNotice message={analysis.error ?? "The analysis failed before producing a review."} />
      )}

      {analysis.status === "running" && (
        <Panel>
          <div className="running-inline">
            <Spinner label="The workflow is still running" />
            <p>This page polls the API until the next interrupt or completion.</p>
          </div>
        </Panel>
      )}

      {analysis.status === "awaiting_review" && analysis.review && (
        <ReviewWorkspace analysis={analysis} review={analysis.review} onUpdated={setAnalysis} />
      )}

      {analysis.status === "completed" && <ResultView analysis={analysis} />}
    </div>
  );
}

function PhaseRail({ analysis }: { analysis: AnalysisResponse }) {
  const review = analysis.review;
  const phases = [
    { label: "Auditor", done: Boolean(review?.auditor_findings?.length) || analysis.status === "completed" },
    { label: "Quant", done: Boolean(review?.risk_score) || analysis.status === "completed" },
    {
      label: "Human review",
      done: analysis.status === "completed",
      active: analysis.status === "awaiting_review",
    },
    { label: "Report", done: analysis.status === "completed", active: false },
  ];
  return (
    <ol className="phase-rail">
      {phases.map((phase, index) => (
        <li
          key={phase.label}
          className={`${phase.done ? "done" : ""} ${phase.active ? "active" : ""}`}
        >
          <span className="phase-index">{phase.done ? <Icon name="check" size={12} /> : index + 1}</span>
          <span>{phase.label}</span>
        </li>
      ))}
    </ol>
  );
}

function ReviewWorkspace({
  analysis,
  review,
  onUpdated,
}: {
  analysis: AnalysisResponse;
  review: ReviewPayload;
  onUpdated: (analysis: AnalysisResponse) => void;
}) {
  return (
    <section className="bento review-grid">
      <div className="span-7 stack">
        <FindingsPanel review={review} />
        <EvidencePanel documentHash={analysis.document_hash} />
      </div>
      <div className="span-5 stack">
        <ScorePanel review={review} />
        <ReviewCard analysis={analysis} review={review} onUpdated={onUpdated} />
      </div>
    </section>
  );
}

function FindingsPanel({ review }: { review: ReviewPayload }) {
  return (
    <Panel eyebrow="Auditor agent" title="What the document says">
      {review.auditor_findings.length === 0 ? (
        <EmptyState title="No findings surfaced" body="The auditor returned no findings for this document." />
      ) : (
        <ul className="finding-list">
          {review.auditor_findings.map((finding, index) => (
            <li key={`${index}-${finding.slice(0, 24)}`}>
              <span className="finding-index">{String(index + 1).padStart(2, "0")}</span>
              <p>{finding}</p>
            </li>
          ))}
        </ul>
      )}
      <div className="panel-footnote">
        <Icon name="shield" size={14} />
        <span>
          Findings are generated by the Auditor agent and are not a substitute for reading the
          source report.
        </span>
      </div>
    </Panel>
  );
}

function ScorePanel({ review }: { review: ReviewPayload }) {
  const proposed = scoreOf(review.risk_score);
  const pending = scoreOf(review.final_score);
  const shown = review.final_score ? pending : proposed;
  const quant = asRecord(review.quant_context);
  const prior = asArray(quant?.prior_assessments)
    .map(asRecord)
    .filter((item): item is Record<string, unknown> => Boolean(item));
  const centrality = asRecord(quant?.centrality);
  const notes = asArray(shown.notes).map(asText).filter(Boolean);
  const level = riskLevel(shown.risk_level);

  return (
    <Panel eyebrow="Quant agent" title="Proposed risk">
      <div className="score-hero">
        <div>
          <span className="score-caption">{review.final_score ? "Pending override" : "System score"}</span>
          <RiskBadge level={level} large />
        </div>
        <div className="round-chip">
          <span>Round</span>
          <strong>{review.iteration}</strong>
        </div>
      </div>

      <div className="ratio-grid">
        <div>
          <span>Debt / equity</span>
          <strong>{fmtRatio(shown.debt_to_equity)}</strong>
        </div>
        <div>
          <span>Current ratio</span>
          <strong>{fmtRatio(shown.current_ratio)}</strong>
        </div>
        <div>
          <span>Net margin</span>
          <strong>{fmtPercent(shown.net_margin)}</strong>
        </div>
      </div>

      {notes.length > 0 && (
        <ul className="note-list">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}

      {centrality && (
        <div className="context-box">
          <span className="note-label">Graph position</span>
          {centrality.rank ? (
            <p>
              Ranked <strong>#{asText(centrality.rank)}</strong> by direct relationships with{" "}
              <strong>{asText(centrality.degree)}</strong> edges (top {asText(centrality.top_n)}).
            </p>
          ) : (
            <p>Not among the top {asText(centrality.top_n ?? "—")} most-connected entities.</p>
          )}
        </div>
      )}

      {prior.length > 0 && (
        <div className="context-box">
          <span className="note-label">Earlier assessments</span>
          <div className="prior-list">
            {prior.map((item, index) => (
              <div className="prior-row" key={`${asText(item.document)}-${index}`}>
                <span>{asText(item.document) || "Earlier document"}</span>
                <span>
                  <RiskBadge level={item.risk_level} />
                  {item.overridden ? <small className="override-tag">Analyst</small> : null}
                </span>
                <small>{asText(item.status)}</small>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

function ReviewCard({
  analysis,
  review,
  onUpdated,
}: {
  analysis: AnalysisResponse;
  review: ReviewPayload;
  onUpdated: (analysis: AnalysisResponse) => void;
}) {
  const proposed = scoreOf(review.risk_score);
  const current = scoreOf(review.final_score ?? review.risk_score);
  const [action, setAction] = useState<ReviewAction>("approve");
  const [notes, setNotes] = useState("");
  const [debtToEquity, setDebtToEquity] = useState(
    current.debt_to_equity === null || current.debt_to_equity === undefined
      ? ""
      : String(current.debt_to_equity),
  );
  const [currentRatio, setCurrentRatio] = useState(
    current.current_ratio === null || current.current_ratio === undefined
      ? ""
      : String(current.current_ratio),
  );
  const [netMargin, setNetMargin] = useState(
    current.net_margin === null || current.net_margin === undefined
      ? ""
      : String(current.net_margin),
  );
  // Empty means "let the V3 rules recalculate the level from the corrected
  // ratios". Only an explicit choice is sent to the backend, because
  // apply_override() treats a supplied level as a manual override.
  const [level, setLevel] = useState<RiskLevel | "">("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDebtToEquity(
      current.debt_to_equity === null || current.debt_to_equity === undefined
        ? ""
        : String(current.debt_to_equity),
    );
    setCurrentRatio(
      current.current_ratio === null || current.current_ratio === undefined
        ? ""
        : String(current.current_ratio),
    );
    setNetMargin(
      current.net_margin === null || current.net_margin === undefined
        ? ""
        : String(current.net_margin),
    );
    setLevel("");
  }, [review.iteration, review.final_score, review.risk_score]);

  const canRerun = review.reruns_left > 0;

  async function submit() {
    setError(null);
    if (action === "rerun" && !notes.trim()) {
      setError("Add a hint for the re-scoring.");
      return;
    }
    if (action === "override") {
      if (!notes.trim()) {
        setError("An override needs a reason for the audit trail.");
        return;
      }
      const changed =
        deValue(debtToEquity) !== asNumber(proposed.debt_to_equity) ||
        deValue(currentRatio) !== asNumber(proposed.current_ratio) ||
        deValue(netMargin) !== asNumber(proposed.net_margin) ||
        (level !== "" && level !== riskLevel(proposed.risk_level));
      if (!changed) {
        setError("Change at least one ratio or the risk level before overriding.");
        return;
      }
    }

    const payload: ReviewRequest = { action, notes: notes.trim() };
    if (action === "override") {
      payload.edited_score = {
        debt_to_equity: deValue(debtToEquity),
        current_ratio: deValue(currentRatio),
        net_margin: deValue(netMargin),
      };
      if (level) payload.risk_level = level;
    }

    setSubmitting(true);
    try {
      const next = await api.reviewAnalysis(analysis.analysis_id, payload);
      onUpdated(next);
      setNotes("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The review could not be recorded.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Panel eyebrow="Human-in-the-loop" title="Your decision">
      <div className="segmented" role="tablist" aria-label="Review action">
        <button
          type="button"
          role="tab"
          aria-selected={action === "approve"}
          className={action === "approve" ? "active" : ""}
          onClick={() => setAction("approve")}
        >
          Approve
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={action === "override"}
          className={action === "override" ? "active" : ""}
          onClick={() => setAction("override")}
        >
          Override
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={action === "rerun"}
          className={action === "rerun" ? "active" : ""}
          onClick={() => setAction("rerun")}
          disabled={!canRerun}
        >
          Re-run {canRerun ? `(${review.reruns_left})` : ""}
        </button>
      </div>

      {action === "approve" && (
        <p className="action-copy">
          Accept the score shown above. The Writer will record the approval in Neo4j and generate
          the PDF report.
        </p>
      )}
      {action === "override" && (
        <>
          <p className="action-copy">
            Set corrected values. The risk level and notes are recalculated with the same rules as
            the automatic score, unless you explicitly choose a level.
          </p>
          <div className="override-grid">
            <label className="field">
              <span>Debt / equity</span>
              <input
                inputMode="decimal"
                value={debtToEquity}
                onChange={(event) => setDebtToEquity(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Current ratio</span>
              <input
                inputMode="decimal"
                value={currentRatio}
                onChange={(event) => setCurrentRatio(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Net margin</span>
              <input
                inputMode="decimal"
                value={netMargin}
                onChange={(event) => setNetMargin(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Risk level</span>
              <select
                value={level}
                onChange={(event) => setLevel(event.target.value as RiskLevel | "")}
              >
                <option value="">Auto from ratios</option>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="UNKNOWN">Unknown</option>
              </select>
            </label>
          </div>
        </>
      )}
      {action === "rerun" && (
        <p className="action-copy">
          Ask the Quant to look again. The hint is used as an extra document search and passed to the
          metrics extractor. This consumes one of the bounded rounds.
        </p>
      )}

      <label className="field">
        <span>
          {action === "approve"
            ? "Review note (optional)"
            : action === "override"
              ? "Reason for the override (required)"
              : "Hint for the re-run (required)"}
        </span>
        <textarea
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          rows={3}
          placeholder={
            action === "approve"
              ? "Anything the audit trail should record."
              : action === "override"
                ? "Explain the correction and its source."
                : "For example: current assets and liabilities are on the consolidated balance sheet."
          }
        />
      </label>

      {error && <ErrorNotice message={error} />}

      <button
        type="button"
        className="button button-primary button-wide"
        onClick={() => void submit()}
        disabled={submitting}
      >
        {submitting ? (
          <Spinner label="Waiting for backend confirmation" />
        ) : (
          <>
            {action === "approve"
              ? "Record approval"
              : action === "override"
                ? "Confirm override"
                : "Re-run scoring"}
            <Icon name="arrow" size={16} />
          </>
        )}
      </button>
      <p className="form-note">
        The UI only shows success after the backend returns an approval record or a new review
        checkpoint. The LangGraph checkpoint is held in API memory and is lost on restart.
      </p>
    </Panel>
  );
}

function deValue(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value.replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function EvidencePanel({ documentHash }: { documentHash: string }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<EvidenceHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.evidence(documentHash, query.trim(), 5);
      setHits(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evidence search failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Panel eyebrow="Document evidence" title="Search the indexed source">
      <div className="search-row">
        <label className="field field-inline">
          <Icon name="search" size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void search();
            }}
            placeholder="Search this report, e.g. related-party loans"
          />
        </label>
        <button type="button" className="button button-secondary" onClick={() => void search()}>
          Search
        </button>
      </div>
      {loading && <Spinner label="Searching indexed chunks" />}
      {error && <ErrorNotice message={error} />}
      {hits && hits.length === 0 && (
        <EmptyState title="No passages found" body="Try a broader phrase from the report." />
      )}
      {hits && hits.length > 0 && (
        <div className="evidence-list">
          {hits.map((hit, index) => (
            <article className="evidence-item" key={`${index}-${hit.score}`}>
              <div className="evidence-meta">
                <span>{hit.filename ?? "Document chunk"}</span>
                <span>{hit.score.toFixed(3)} similarity</span>
              </div>
              <p>{hit.text}</p>
            </article>
          ))}
        </div>
      )}
    </Panel>
  );
}

function ResultView({ analysis }: { analysis: AnalysisResponse }) {
  const record = asRecord(analysis.approval_record) ?? {};
  const finalScore = scoreOf(asRecord(record.final_score));
  const originalScore = scoreOf(asRecord(record.original_score));
  const finalLevel = riskLevel(finalScore.risk_level);
  const history = asArray(record.review_history)
    .map(asRecord)
    .filter((item): item is Record<string, unknown> => Boolean(item));
  const decision = asText(record.decision) || "APPROVED";

  return (
    <section className="bento result-grid">
      <Panel className="span-7" eyebrow="Approval record" title="Review completed">
        <div className={`approval-banner ${decision === "APPROVED" ? "approved" : "rejected"}`}>
          <span className="approval-icon">
            <Icon name={decision === "APPROVED" ? "check" : "alert"} size={22} />
          </span>
          <div>
            <strong>{titleCase(decision)}</strong>
            <p>
              Recorded by {asText(record.approved_by) || analysis.reviewer} at{" "}
              {fmtDate(asText(record.approved_at))}.
            </p>
          </div>
          <StatusBadge status={decision} />
        </div>

        <div className="result-score">
          <div>
            <span className="score-caption">Final risk level</span>
            <RiskBadge level={finalLevel} large />
          </div>
          <div className="ratio-grid result-ratios">
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
        </div>

        <div className="comparison-grid">
          <div>
            <span className="note-label">System proposal</span>
            <p>
              {titleCase(riskLevel(originalScore.risk_level))} · D/E{" "}
              {fmtRatio(originalScore.debt_to_equity)} · CR {fmtRatio(originalScore.current_ratio)}
            </p>
          </div>
          <div>
            <span className="note-label">Approved values</span>
            <p>
              {titleCase(finalLevel)} · D/E {fmtRatio(finalScore.debt_to_equity)} · CR{" "}
              {fmtRatio(finalScore.current_ratio)}
            </p>
          </div>
        </div>

        {asText(record.edit_notes) && (
          <div className="context-box">
            <span className="note-label">Analyst notes</span>
            <p>{asText(record.edit_notes)}</p>
          </div>
        )}

        <div className="result-actions">
          <a className="button button-primary" href={api.reportUrl(analysis.analysis_id)}>
            <Icon name="download" size={17} />
            Download PDF report
          </a>
          <Link className="button button-secondary" to={`/companies/${encodeURIComponent(analysis.company_id)}`}>
            Open company dashboard
          </Link>
        </div>
      </Panel>

      <div className="span-5 stack">
        <Panel eyebrow="Audit trail" title="Review history">
          {history.length === 0 ? (
            <EmptyState title="No review events" body="The approval record contains no review history." />
          ) : (
            <ol className="timeline">
              {history.map((event, index) => (
                <li key={`${asText(event.id)}-${index}`}>
                  <span className={`timeline-dot action-${asText(event.action)}`} />
                  <div>
                    <div className="timeline-head">
                      <strong>{titleCase(asText(event.action))}</strong>
                      <span>{fmtDate(asText(event.at))}</span>
                    </div>
                    <p>
                      {asText(event.reviewer) || "analyst"} · round {asText(event.iteration)}
                    </p>
                    {asText(event.notes) && <blockquote>{asText(event.notes)}</blockquote>}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Panel>

        <Panel eyebrow="Backend truth" title="What was verified">
          <ul className="verified-list">
            <li>
              <Icon name="check" size={15} /> Approval record returned by the workflow
            </li>
            <li>
              <Icon name="check" size={15} /> Report file verified before the download link appeared
            </li>
            <li>
              <Icon name="check" size={15} /> Review events appended to the existing audit trail
            </li>
          </ul>
          <p className="form-note">
            Session status is process-local. The graph and PDF persist; the in-memory review session
            does not.
          </p>
        </Panel>
      </div>
    </section>
  );
}
