import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { DocumentSummary } from "../api/types";
import { Icon } from "../components/Icons";
import { EmptyState, ErrorNotice, Panel, Spinner, StatusBadge } from "../components/Ui";
import { shortHash } from "../utils/format";

interface Turn {
  question: string;
  answer: string | null;
}

const SUGGESTIONS = [
  "Summarise this document",
  "What are the main risks?",
  "What do the financial ratios say?",
];

export function AskPage() {
  const { documentHash = "" } = useParams();
  const [document, setDocument] = useState<DocumentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await api.document(documentHash);
        if (!cancelled) setDocument(next);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load the document.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentHash]);

  const ready = document?.status === "completed" || document?.status === "partial";

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const ask = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || asking) return;
      setError(null);
      setQuestion("");
      setAsking(true);
      setTurns((current) => [...current, { question: text, answer: null }]);
      try {
        const response = await api.askDocument(documentHash, text);
        setTurns((current) =>
          current.map((turn, index) =>
            index === current.length - 1 ? { ...turn, answer: response.answer } : turn,
          ),
        );
      } catch (err) {
        setTurns((current) => current.slice(0, -1));
        setQuestion(text);
        setError(err instanceof Error ? err.message : "Could not answer that question.");
      } finally {
        setAsking(false);
      }
    },
    [asking, documentHash],
  );

  if (loading) {
    return (
      <div className="loading-page">
        <Spinner label="Loading document" />
      </div>
    );
  }

  return (
    <div className="stack">
      {error && <ErrorNotice message={error} onRetry={() => setError(null)} />}

      <section className="page-intro">
        <div>
          <Link className="back-link" to="/documents">
            <Icon name="arrow" size={14} /> Documents
          </Link>
          <p className="eyebrow">Document assistant</p>
          <h2>{document?.filename ?? "Document"}</h2>
          <p className="qa-meta">
            <span>Reference #{shortHash(documentHash)}</span>
            <StatusBadge status={document?.status} />
          </p>
          <p>
            Ask a question about this report. Answers use the evidence and relationships indexed
            during ingestion.
          </p>
        </div>
        <div className="intro-note">
          <Icon name="spark" size={18} />
          <span>Press Enter to send a question, or Shift+Enter for a new line.</span>
        </div>
      </section>

      {document && !ready ? (
        <Panel>
          <EmptyState
            title="Questions open after ingestion"
            body="This document is still processing, or ingestion did not finish. Try again once it is completed or partially completed."
            action={
              <Link className="button button-secondary button-small" to="/documents">
                Back to documents
              </Link>
            }
          />
        </Panel>
      ) : (
        <Panel className="qa-panel" eyebrow="Ask the source" title="Questions and answers">
          <div className="qa-thread">
            {turns.length === 0 ? (
              <div className="qa-empty">
                <span className="qa-mark">
                  <Icon name="chat" size={22} />
                </span>
                <strong>Ask anything about this document.</strong>
                <p>
                  Summaries, risks, ratios, or anything the report mentions. Answers are drawn from
                  the indexed evidence.
                </p>
                <div className="qa-suggestions">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      className="qa-chip"
                      onClick={() => void ask(suggestion)}
                      disabled={asking}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              turns.map((turn, index) => (
                <div className="qa-turn" key={`${index}-${turn.question}`}>
                  <div className="qa-row qa-row-question">
                    <span className="qa-avatar">You</span>
                    <p>{turn.question}</p>
                  </div>
                  <div className="qa-row qa-row-answer">
                    <span className="qa-avatar qa-avatar-bot">
                      <Icon name="spark" size={14} />
                    </span>
                    {turn.answer === null ? (
                      <Spinner label="Reading the document" />
                    ) : (
                      <p>{turn.answer}</p>
                    )}
                  </div>
                </div>
              ))
            )}
            <div ref={endRef} />
          </div>

          <form
            className="qa-composer"
            onSubmit={(event) => {
              event.preventDefault();
              void ask(question);
            }}
          >
            <label className="field qa-field">
              <span>Your question</span>
              <textarea
                value={question}
                rows={2}
                maxLength={1000}
                placeholder="e.g. What are the main risks in this report?"
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void ask(question);
                  }
                }}
                disabled={asking}
              />
            </label>
            <button
              type="submit"
              className="button button-primary"
              disabled={asking || !question.trim()}
            >
              {asking ? "Asking…" : "Ask"}
              <Icon name="arrow" size={15} />
            </button>
          </form>
          <p className="form-note">
            Answers are generated from your ingested evidence. Check them against the source before
            relying on them.
          </p>
        </Panel>
      )}
    </div>
  );
}
