import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DocumentSummary, JobResponse } from "../api/types";
import { Icon } from "../components/Icons";
import { EmptyState, ErrorNotice, Panel, Spinner, StatusBadge } from "../components/Ui";
import { fmtBytes, fmtDate, fmtNumber, shortHash } from "../utils/format";

const TERMINAL = new Set(["completed", "partial", "failed"]);

export function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      setDocuments(await api.documents());
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
    if (!job || TERMINAL.has(job.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.job(job.job_id);
        setJob(next);
        if (TERMINAL.has(next.status)) {
          await loadDocuments();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not poll the ingestion job.");
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [job, loadDocuments]);

  const upload = useCallback(
    async (file: File) => {
      setError(null);
      setUploading(true);
      setProgress(0);
      setJob(null);
      try {
        const response = await api.uploadDocument(file, setProgress);
        const initial: JobResponse = {
          job_id: response.job_id,
          status: response.status,
          filename: response.filename,
          document_hash: response.document_hash,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
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

  return (
    <div className="stack">
      {error && <ErrorNotice message={error} onRetry={() => void loadDocuments()} />}

      <section className="page-intro">
        <div>
          <p className="eyebrow">Ingestion desk</p>
          <h2>The source document is the audit trail.</h2>
          <p>
            Upload a financial PDF. The existing V3 pipeline extracts entities, writes the Neo4j
            graph, indexes chunks in Qdrant, and creates a draft risk assessment. This screen only
            wraps that pipeline; it does not replace it.
          </p>
        </div>
        <div className="intro-note">
          <Icon name="clock" size={18} />
          <span>
            Ingestion jobs are process-local. Refreshing the page is safe; restarting the API loses
            job progress.
          </span>
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
            <span>PDF only · up to 25 MB · content hash deduplicates ingestion</span>
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
                <span>{job.persistent ? "Persistent" : "Process-local"}</span>
              </div>
              {!TERMINAL.has(job.status) && (
                <div className="job-working">
                  <Spinner label="Extracting entities and indexing chunks" />
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
                    Ingestion partially completed. Some extraction batches failed; the document is
                    still usable for analysis with that limitation.
                  </span>
                </div>
              )}
              {job.error && <div className="job-error">{job.error}</div>}
              {TERMINAL.has(job.status) && job.status !== "failed" && (
                <Link
                  className="button button-secondary button-small"
                  to={`/analyses/new?document=${encodeURIComponent(job.document_hash)}`}
                >
                  Analyze this document
                  <Icon name="arrow" size={15} />
                </Link>
              )}
            </div>
          )}

          <div className="panel-footnote">
            <Icon name="shield" size={14} />
            <span>
              The upload is stored under <code>data/uploads</code> using its SHA-256 hash. Client
              filenames are sanitized before storage.
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
                  <Link
                    className="text-link row-action"
                    to={`/analyses/new?document=${encodeURIComponent(document.hash)}`}
                  >
                    Analyze <Icon name="arrow" size={13} />
                  </Link>
                </article>
              ))}
            </div>
          )}
        </Panel>
      </section>
    </div>
  );
}
