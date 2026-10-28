import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { CompanySummary, DocumentSummary } from "../api/types";
import { Icon } from "../components/Icons";
import { EmptyState, ErrorNotice, Panel, Spinner, StatusBadge } from "../components/Ui";
import { fmtDate, fmtNumber, shortHash } from "../utils/format";

export function NewAnalysisPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [documentHash, setDocumentHash] = useState(searchParams.get("document") ?? "");
  const [companyId, setCompanyId] = useState("");
  const [reviewer, setReviewer] = useState(
    () => window.localStorage.getItem("aarthik.reviewer") ?? "analyst",
  );
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [loadingCompanies, setLoadingCompanies] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const nextDocuments = await api.documents();
        if (cancelled) return;
        const usableDocuments = nextDocuments.filter(
          (document) => document.status === "completed" || document.status === "partial",
        );
        setDocuments(usableDocuments);
        const requested = searchParams.get("document");
        if (requested && usableDocuments.some((document) => document.hash === requested)) {
          setDocumentHash(requested);
        } else if (usableDocuments[0]) {
          setDocumentHash(usableDocuments[0].hash);
        } else {
          setDocumentHash("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load analysis setup.");
        }
      } finally {
        if (!cancelled) setLoadingDocuments(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  useEffect(() => {
    if (!documentHash) {
      setCompanies([]);
      setCompanyId("");
      setLoadingCompanies(false);
      return;
    }
    let cancelled = false;
    setLoadingCompanies(true);
    setCompanyId("");
    setCompanies([]);
    (async () => {
      try {
        const linked = await api.documentCompanies(documentHash);
        if (cancelled) return;
        setCompanies(linked);
        setCompanyId(linked[0]?.id ?? "");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load companies for this document.");
        }
      } finally {
        if (!cancelled) setLoadingCompanies(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentHash]);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.hash === documentHash) ?? null,
    [documents, documentHash],
  );
  const selectedCompany = useMemo(
    () => companies.find((company) => company.id === companyId) ?? null,
    [companies, companyId],
  );
  const loading = loadingDocuments || loadingCompanies;

  async function start() {
    if (!documentHash || !companyId || !reviewer.trim()) {
      setError("Choose a document and company, and provide a reviewer name.");
      return;
    }
    setStarting(true);
    setError(null);
    window.localStorage.setItem("aarthik.reviewer", reviewer.trim());
    try {
      const analysis = await api.startAnalysis({
        company_id: companyId,
        document_hash: documentHash,
        reviewer: reviewer.trim(),
        max_iterations: 3,
      });
      navigate(`/analyses/${analysis.analysis_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the analysis.");
      setStarting(false);
    }
  }

  if (loading) {
    return (
      <div className="loading-page">
        <Spinner label="Loading analysis setup" />
      </div>
    );
  }

  if (starting) {
    return (
      <div className="running-page">
        <div className="running-mark">
          <span className="pulse-ring" />
          <Icon name="graph" size={30} />
        </div>
        <p className="eyebrow">Analysis in progress</p>
        <h2>The Auditor and Quant are working.</h2>
        <p>
          The workspace is reviewing the company profile, document passages, prior assessments and
          graph position. The workflow will stop at the human review checkpoint; no approval is
          assumed.
        </p>
        <Spinner label="Waiting for the human review checkpoint" />
      </div>
    );
  }

  return (
    <div className="stack">
      {error && <ErrorNotice message={error} />}

      <section className="page-intro">
        <div>
          <p className="eyebrow">Reviewed risk workflow</p>
          <h2>Start with a document and a company.</h2>
          <p>
            This runs the standard review workflow — Auditor, Quant, then a human review checkpoint.
            Nothing is approved until you submit a review and it is confirmed.
          </p>
        </div>
        <div className="intro-note">
          <Icon name="alert" size={18} />
          <span>You can review, override, or re-run before a report is generated.</span>
        </div>
      </section>

      {documents.length === 0 ? (
        <Panel>
          <EmptyState
            title="No completed documents"
            body="An analysis needs a document registered as completed or partial. Upload a financial PDF first."
            action={
              <Link className="button button-primary button-small" to="/documents">
                Go to documents
              </Link>
            }
          />
        </Panel>
      ) : (
        <section className="bento setup-grid">
          <Panel className="span-7" eyebrow="Step 1" title="Choose the source document">
            <div className="choice-list">
              {documents.map((document) => (
                <label
                  className={`choice-row ${documentHash === document.hash ? "selected" : ""}`}
                  key={document.hash}
                >
                  <input
                    type="radio"
                    name="document"
                    value={document.hash}
                    checked={documentHash === document.hash}
                    onChange={() => setDocumentHash(document.hash)}
                  />
                  <span className="choice-icon">
                    <Icon name="document" size={18} />
                  </span>
                  <span className="choice-main">
                    <strong>{document.filename ?? "Untitled document"}</strong>
                    <span>
                      #{shortHash(document.hash)} · {fmtDate(document.ingested_at)}
                    </span>
                  </span>
                  <span className="choice-meta">
                    <StatusBadge status={document.status} />
                    <small>{fmtNumber(document.entity_count ?? 0, 0)} entities</small>
                  </span>
                </label>
              ))}
            </div>

            <div className="form-row">
              <label className="field">
                <span>Reviewer name</span>
                <input
                  value={reviewer}
                  maxLength={120}
                  onChange={(event) => setReviewer(event.target.value)}
                  placeholder="Name for the audit trail"
                />
              </label>
              <label className="field">
                <span>Scoring rounds</span>
                <input value="3 rounds maximum" readOnly />
              </label>
            </div>
          </Panel>

          <Panel className="span-5" eyebrow="Step 2" title="Confirm the target company">
            {loadingCompanies ? (
              <div className="loading-block">
                <Spinner label="Loading companies mentioned in this document" />
              </div>
            ) : companies.length === 0 ? (
              <EmptyState
                title="No company is linked to this document"
                body="The analysis can only score a company that this document mentions. Upload or retry the document before starting an analysis."
              />
            ) : (
              <>
                <label className="field">
                  <span>Company entity</span>
                  <select value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                    {companies.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name ?? company.id}
                      </option>
                    ))}
                  </select>
                </label>

                {selectedCompany && (
                  <div className="selection-summary">
                    <div>
                      <span>Entity id</span>
                      <strong>{selectedCompany.id}</strong>
                    </div>
                    <div>
                      <span>Graph relationships</span>
                      <strong>{selectedCompany.relationship_count}</strong>
                    </div>
                    <div>
                      <span>Assessments</span>
                      <strong>{selectedCompany.assessment_count}</strong>
                    </div>
                  </div>
                )}

                {selectedDocument && (
                  <div className="selection-context">
                    <span className="note-label">Selected source</span>
                    <strong>{selectedDocument.filename}</strong>
                    <span>
                      {fmtNumber(selectedDocument.entity_count ?? 0, 0)} entities ·{" "}
                      {fmtNumber(selectedDocument.relationship_count ?? 0, 0)} relationships
                    </span>
                  </div>
                )}

                <button
                  type="button"
                  className="button button-primary button-wide"
                  onClick={() => void start()}
                  disabled={!documentHash || !companyId || !reviewer.trim()}
                >
                  Run Auditor and Quant
                  <Icon name="arrow" size={16} />
                </button>
                <p className="form-note">
                  The workflow may take a minute or more. Keep this page open until the review
                  checkpoint appears.
                </p>
              </>
            )}
          </Panel>
        </section>
      )}
    </div>
  );
}
