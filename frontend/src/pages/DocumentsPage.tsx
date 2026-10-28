import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { BatchProgress, BatchStatus, DocumentSummary, JobResponse } from "../api/types";
import { Icon } from "../components/Icons";
import { EmptyState, ErrorNotice, Panel, Spinner, StatusBadge } from "../components/Ui";
import { fmtDate, fmtNumber, shortHash } from "../utils/format";

const TERMINAL = new Set(["completed", "partial", "failed"]);

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  reading: "Reading PDF",
  extracting: "Extracting entities",
  writing: "Building graph",
  indexing: "Indexing evidence",
  risk: "Calculating risk",
  done: "Done",
  failed: "Failed",
};

function batchCounts(job: JobResponse): Record<BatchStatus, number> {
  const counts: Record<BatchStatus, number> = {
    pending: 0,
    running: 0,
    cached: 0,
    completed: 0,
    failed: 0,
  };
  for (const batch of job.batches) counts[batch.status] += 1;
  return counts;
}

function batchLabel(batch: BatchProgress): string {
  const base = `Batch ${batch.index}: ${batch.status}`;
  if (batch.status === "failed" && batch.error) return `${base} (${batch.error})`;
  if (batch.entities !== null) return `${base} · ${batch.entities} entities`;
  return base;
}

export function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null);
  const [actionHash, setActionHash] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      setDocuments(await api.documents());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    let cancelled = false;
    const loadLatestJob = async () => {
      try {
        const jobs = await api.jobs();
        if (!cancelled && jobs.length > 0) {
          setJob((current) => current ?? jobs[0]);
        }
      } catch {
        // Job history is optional; the registry still works without it.
      }
    };
    void loadLatestJob();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!job || TERMINAL.has(job.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.job(job.job_id);
        setJob(next);
        if (TERMINAL.has(next.status)) {
          await loadDocuments();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not refresh the job status.");
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [job, loadDocuments]);

  useEffect(() => {
    if (!deleteTarget) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && actionHash === null) setDeleteTarget(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteTarget, actionHash]);

  const upload = useCallback(
    async (file: File) => {
      setError(null);
      setNotice(null);
      setUploading(true);
      setProgress(0);
      setJob(null);
      try {
        const response = await api.uploadDocument(file, setProgress);
        const initial: JobResponse = {
          job_id: response.job_id,
          status: response.status,
          stage: "queued",
          filename: response.filename,
          document_hash: response.document_hash,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          batch_total: 0,
          batches: [],
          document: null,
          error: null,
          persistent: false,
        };
        setJob(initial);
        const current = await api.job(response.job_id).catch(() => initial);
        setJob(current);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed.");
      } finally {
        setUploading(false);
      }
    },
    [],
  );

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (file) void upload(file);
    },
    [upload],
  );

  const retry = useCallback(
    async (documentHash: string, filename: string) => {
      setError(null);
      setNotice(null);
      setActionHash(documentHash);
      try {
        const next = await api.retryDocument(documentHash);
        setJob(next);
        setNotice(`Retry queued for ${filename}. Completed batches load from the extraction cache.`);
        await loadDocuments();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not retry ingestion.");
      } finally {
        setActionHash(null);
      }
    },
    [loadDocuments],
  );

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setError(null);
    setNotice(null);
    setActionHash(target.hash);
    try {
      const result = await api.deleteDocument(target.hash);
      setNotice(
        `Deleted ${result.filename ?? "document"}: ${result.deleted_entities} entities, ` +
          `${result.deleted_relationships} relationships, ${result.deleted_assessments} assessments, ` +
          `${result.deleted_points} indexed passages removed.`,
      );
      setJob((current) => (current?.document_hash === target.hash ? null : current));
      setDeleteTarget(null);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the document.");
    } finally {
      setActionHash(null);
    }
  }, [deleteTarget, loadDocuments]);

  const counts = job ? batchCounts(job) : null;
  const finishedBatches = counts ? counts.cached + counts.completed + counts.failed : 0;
  const failedBatches = job?.batches.filter((batch) => batch.status === "failed") ?? [];

  return (
    <div className="stack">
      {error && <ErrorNotice message={error} onRetry={() => void loadDocuments()} />}
      {notice && (
        <div className="notice" role="status">
          <Icon name="check" size={17} />
          <span>{notice}</span>
          <button type="button" className="text-button" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </div>
      )}

      <section className="page-intro">
        <div>
          <p className="eyebrow">Ingestion desk</p>
          <h2>The source document is the audit trail.</h2>
          <p>
            Upload a financial PDF to extract entities, build the evidence graph, and create a draft
            risk assessment for review.
          </p>
        </div>
        <div className="intro-note">
          <Icon name="clock" size={18} />
          <span>You can refresh this page safely while a document is processing.</span>
        </div>
      </section>

      <section className="bento documents-grid">
        <Panel className="span-5" eyebrow="New document" title="Upload a financial PDF">
          <button
            type="button"
            className={`dropzone ${dragActive ? "drag-active" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragActive(false);
              handleFiles(event.dataTransfer.files);
            }}
          >
            <span className="dropzone-icon">
              <Icon name="upload" size={24} />
            </span>
            <strong>{uploading ? "Uploading…" : "Drop a PDF here, or choose a file"}</strong>
            <span>PDF only · up to 25 MB · the same file is never processed twice</span>
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            hidden
            onChange={(event) => {
              handleFiles(event.target.files);
              event.target.value = "";
            }}
          />

          {uploading && (
            <div className="progress-block">
              <div className="progress-label">
                <span>Uploading</span>
                <span>{progress}%</span>
              </div>
              <div className="progress-track">
                <span style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          {job && (
            <div className="job-card">
              <div className="job-head">
                <div>
                  <p className="eyebrow">Ingestion job</p>
                  <strong>{job.filename}</strong>
                </div>
                <StatusBadge status={job.status} />
              </div>
              <div className="job-meta">
                <span>Document #{shortHash(job.document_hash)}</span>
                <span>{STAGE_LABELS[job.stage] ?? job.stage}</span>
              </div>

              {job.batch_total > 0 && counts && (
                <div className="batch-progress">
                  <div className="progress-label">
                    <span>Batches</span>
                    <span>
                      {finishedBatches}/{job.batch_total} finished
                    </span>
                  </div>
                  <div className="progress-track">
                    <span
                      style={{
                        width: `${Math.round((finishedBatches / job.batch_total) * 100)}%`,
                      }}
                    />
                  </div>
                  <div className="batch-grid" aria-label="Batch status">
                    {job.batches.map((batch) => (
                      <span
                        key={batch.index}
                        className={`batch-chip batch-${batch.status}`}
                        title={batchLabel(batch)}
                      >
                        {batch.index}
                      </span>
                    ))}
                  </div>
                  <div className="batch-legend">
                    <span>
                      <i className="batch-dot batch-completed" /> {counts.completed} completed
                    </span>
                    <span>
                      <i className="batch-dot batch-cached" /> {counts.cached} cached
                    </span>
                    <span>
                      <i className="batch-dot batch-failed" /> {counts.failed} failed
                    </span>
                    {counts.running > 0 && (
                      <span>
                        <i className="batch-dot batch-running" /> {counts.running} running
                      </span>
                    )}
                  </div>
                  {failedBatches.length > 0 && (
                    <div className="batch-failures">
                      <strong>
                        {failedBatches.length} batch{failedBatches.length === 1 ? "" : "es"} failed
                      </strong>
                      <ul>
                        {failedBatches.map((batch) => (
                          <li key={batch.index}>
                            Batch {batch.index}: {batch.error ?? "Extraction failed"}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {!TERMINAL.has(job.status) && (
                <div className="job-working">
                  <Spinner label="Extracting entities and indexing evidence" />
                </div>
              )}
              {job.status === "completed" && (
                <div className="job-success">
                  <Icon name="check" size={17} />
                  <span>
                    Ingestion completed. {fmtNumber(job.document?.entity_count ?? 0, 0)} entities and{" "}
                    {fmtNumber(job.document?.relationship_count ?? 0, 0)} relationships recorded.
                  </span>
                </div>
              )}
              {job.status === "partial" && (
                <div className="job-warning">
                  <Icon name="alert" size={17} />
                  <span>
                    Ingestion partially completed. Some processing steps failed; the document is
                    still usable for analysis with that limitation.
                  </span>
                </div>
              )}
              {job.error && <div className="job-error">{job.error}</div>}
              {(job.status === "partial" || job.status === "failed") && (
                <button
                  type="button"
                  className="button button-secondary button-small"
                  onClick={() => void retry(job.document_hash, job.filename)}
                  disabled={actionHash !== null}
                >
                  <Icon name="refresh" size={15} />
                  Retry ingestion
                </button>
              )}
              {TERMINAL.has(job.status) && job.status !== "failed" && (
                <div className="job-actions">
                  <Link
                    className="button button-secondary button-small"
                    to={`/documents/${encodeURIComponent(job.document_hash)}/ask`}
                  >
                    <Icon name="chat" size={15} />
                    Ask this document
                  </Link>
                  <Link
                    className="button button-secondary button-small"
                    to={`/analyses/new?document=${encodeURIComponent(job.document_hash)}`}
                  >
                    Analyze this document
                    <Icon name="arrow" size={15} />
                  </Link>
                </div>
              )}
            </div>
          )}

          <div className="panel-footnote">
            <Icon name="shield" size={14} />
            <span>
              Uploads are stored privately and identified by content, so re-uploading the same file
              reuses existing work.
            </span>
          </div>
        </Panel>

        <Panel
          className="span-7"
          eyebrow="Document registry"
          title="Ingested documents"
          action={
            <button type="button" className="text-button" onClick={() => void loadDocuments()}>
              <Icon name="refresh" size={14} /> Refresh
            </button>
          }
        >
          {loading ? (
            <div className="loading-block">
              <Spinner label="Loading document registry" />
            </div>
          ) : documents.length === 0 ? (
            <EmptyState
              title="The registry is empty"
              body="Upload the first financial report to create a Document node and index its chunks."
            />
          ) : (
            <div className="document-list">
              {documents.map((document) => (
                <article className="document-row" key={document.hash}>
                  <div className="document-icon">
                    <Icon name="document" size={19} />
                  </div>
                  <div className="document-main">
                    <strong>{document.filename ?? "Untitled document"}</strong>
                    <span>
                      #{shortHash(document.hash)} · {fmtDate(document.ingested_at)}
                    </span>
                  </div>
                  <div className="document-stats">
                    <span>{fmtNumber(document.entity_count ?? 0, 0)} entities</span>
                    <span>{fmtNumber(document.relationship_count ?? 0, 0)} relationships</span>
                    {document.failed_batch_count ? (
                      <span className="text-warn">
                        {document.failed_batch_count} failed batches
                      </span>
                    ) : null}
                  </div>
                  <StatusBadge status={document.status} />
                  <div className="document-actions">
                    {(document.status === "completed" || document.status === "partial") && (
                      <Link
                        className="text-link"
                        to={`/documents/${encodeURIComponent(document.hash)}/ask`}
                      >
                        <Icon name="chat" size={13} /> Ask
                      </Link>
                    )}
                    <Link
                      className="text-link"
                      to={`/analyses/new?document=${encodeURIComponent(document.hash)}`}
                    >
                      Analyze <Icon name="arrow" size={13} />
                    </Link>
                    {(document.status === "partial" || document.status === "failed") && (
                      <button
                        type="button"
                        className="text-button"
                        onClick={() =>
                          void retry(document.hash, document.filename ?? "document")
                        }
                        disabled={actionHash !== null}
                      >
                        <Icon name="refresh" size={13} /> Retry
                      </button>
                    )}
                    <button
                      type="button"
                      className="icon-button danger"
                      aria-label={`Delete ${document.filename ?? "document"}`}
                      title="Delete document and its graph/vector data"
                      onClick={() => setDeleteTarget(document)}
                      disabled={actionHash !== null}
                    >
                      <Icon name="trash" size={15} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Panel>
      </section>

      {deleteTarget && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => actionHash === null && setDeleteTarget(null)}
        >
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-document-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <span className="modal-icon">
                <Icon name="trash" size={20} />
              </span>
              <div>
                <p className="eyebrow">Destructive action</p>
                <h2 id="delete-document-title">Delete this document?</h2>
              </div>
            </div>
            <div className="modal-body">
              <p>
                <strong>{deleteTarget.filename ?? "Untitled document"}</strong> will be permanently
                removed, including its risk assessments, review history, and indexed evidence.
                Entities that another document still mentions are kept.
              </p>
              <p className="modal-warning">
                The stored PDF is deleted too, and any in-progress analysis for this document will
                fail. This cannot be undone.
              </p>
              <p className="modal-note">
                Previously extracted results are kept, so re-uploading the same PDF is faster.
              </p>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setDeleteTarget(null)}
                disabled={actionHash !== null}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button button-danger"
                onClick={() => void confirmDelete()}
                disabled={actionHash !== null}
              >
                {actionHash === deleteTarget.hash ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
