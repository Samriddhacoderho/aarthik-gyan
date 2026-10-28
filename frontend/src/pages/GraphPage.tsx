import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { CompanySummary, GraphNode, GraphResponse } from "../api/types";
import { GraphView } from "../components/GraphView";
import { Icon } from "../components/Icons";
import { EmptyState, ErrorNotice, Panel, Spinner } from "../components/Ui";
import { fmtNumber, titleCase } from "../utils/format";

export function GraphPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [companyId, setCompanyId] = useState(searchParams.get("company") ?? "");
  const [depth, setDepth] = useState(1);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await api.companies();
        if (cancelled) return;
        setCompanies(next);
        const requested = searchParams.get("company");
        if (requested && next.some((company) => company.id === requested)) {
          setCompanyId(requested);
        } else if (next[0]) {
          setCompanyId(next[0].id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load companies.");
        }
      } finally {
        if (!cancelled) setLoadingCompanies(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  const loadGraph = useCallback(async () => {
    if (!companyId) return;
    setLoadingGraph(true);
    setError(null);
    try {
      const next = await api.graph(companyId, depth);
      setGraph(next);
      setSelected((current) =>
        current && next.nodes.some((node) => node.id === current.id) ? current : null,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the graph.");
    } finally {
      setLoadingGraph(false);
    }
  }, [companyId, depth]);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  function chooseCompany(id: string) {
    setCompanyId(id);
    setSelected(null);
    setSearchParams(id ? { company: id } : {}, { replace: true });
  }

  const company = useMemo(
    () => companies.find((item) => item.id === companyId) ?? null,
    [companies, companyId],
  );

  const neighbours = useMemo(() => {
    if (!graph || !selected) return [];
    const ids = new Set<string>();
    graph.edges.forEach((edge) => {
      if (edge.source === selected.id) ids.add(edge.target);
      if (edge.target === selected.id) ids.add(edge.source);
    });
    return graph.nodes.filter((node) => ids.has(node.id));
  }, [graph, selected]);

  if (loadingCompanies) {
    return (
      <div className="loading-page">
        <Spinner label="Loading graph context" />
      </div>
    );
  }

  if (companies.length === 0) {
    return (
      <Panel>
        <EmptyState
          title="No companies in the graph"
          body="Ingest a financial document first. The graph explorer reads the Company entities created by the V3 pipeline."
          action={
            <Link className="button button-primary button-small" to="/documents">
              Upload a PDF
            </Link>
          }
        />
      </Panel>
    );
  }

  return (
    <div className="stack">
      {error && <ErrorNotice message={error} onRetry={() => void loadGraph()} />}

      <section className="page-intro graph-intro">
        <div>
          <p className="eyebrow">Neo4j explorer</p>
          <h2>Trace the relationships behind the score.</h2>
          <p>
            The map is generated from <code>:RELATION</code> edges written by the existing ingestion
            pipeline. Click a node to inspect its type and direct neighbours; use the depth control to
            expand one or two hops.
          </p>
        </div>
        <div className="graph-toolbar">
          <label className="field">
            <span>Company</span>
            <select value={companyId} onChange={(event) => chooseCompany(event.target.value)}>
              {companies.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name ?? item.id}
                </option>
              ))}
            </select>
          </label>
          <div className="field">
            <span>Depth</span>
            <div className="segmented compact">
              {[1, 2].map((value) => (
                <button
                  key={value}
                  type="button"
                  className={depth === value ? "active" : ""}
                  onClick={() => setDepth(value)}
                >
                  {value} hop{value > 1 ? "s" : ""}
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            className="button button-secondary button-small"
            onClick={() => void loadGraph()}
          >
            <Icon name="refresh" size={14} /> Refresh
          </button>
        </div>
      </section>

      <section className="bento graph-grid">
        <Panel
          className="span-8"
          eyebrow={company ? `${company.name ?? company.id}` : "Graph"}
          title="Relationship map"
          action={
            loadingGraph ? (
              <Spinner label="Loading" />
            ) : graph ? (
              <span className="graph-count">
                {fmtNumber(graph.nodes.length, 0)} nodes · {fmtNumber(graph.edges.length, 0)} edges
              </span>
            ) : undefined
          }
        >
          {graph ? (
            <>
              <GraphView
                key={`${companyId}-${depth}`}
                nodes={graph.nodes}
                edges={graph.edges}
                onSelect={setSelected}
                height={560}
              />
              <div className="graph-footnote">
                <span>
                  Depth {graph.depth} · {company?.relationship_count ?? 0} direct company relationships
                </span>
                {graph.truncated ? (
                  <span className="text-warn">
                    The view hit the safety cap and is truncated. Use depth 1 for the complete local
                    neighbourhood.
                  </span>
                ) : (
                  <span>Read-only projection of the stored graph</span>
                )}
              </div>
            </>
          ) : loadingGraph ? (
            <div className="loading-block">
              <Spinner label="Reading the graph" />
            </div>
          ) : (
            <EmptyState
              title="Graph unavailable"
              body="Select a company and retry. If the problem persists, check Neo4j connectivity."
            />
          )}
        </Panel>

        <div className="span-4 stack">
          <Panel eyebrow="Inspector" title={selected ? selected.name || selected.id : "Select a node"}>
            {selected ? (
              <div className="node-inspector">
                <div className="node-type">
                  <span className="node-swatch" />
                  {titleCase(selected.type ?? "Entity")}
                </div>
                <dl>
                  <div>
                    <dt>Entity id</dt>
                    <dd className="mono">{selected.id}</dd>
                  </div>
                  <div>
                    <dt>Direct neighbours</dt>
                    <dd>{fmtNumber(neighbours.length, 0)}</dd>
                  </div>
                </dl>
                {neighbours.length > 0 && (
                  <>
                    <span className="note-label">Connected entities</span>
                    <ul className="neighbour-list">
                      {neighbours.slice(0, 10).map((neighbor) => (
                        <li key={neighbor.id}>
                          <button type="button" onClick={() => setSelected(neighbor)}>
                            <span>{neighbor.name || neighbor.id}</span>
                            <small>{titleCase(neighbor.type ?? "Entity")}</small>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            ) : (
              <p className="inspector-hint">
                Click any node in the map. The inspector is a read-only view; the graph itself is only
                mutated by the ingestion pipeline.
              </p>
            )}
          </Panel>

          <Panel eyebrow="Company filter" title="Entities in this workspace">
            <ul className="company-picker">
              {companies.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={item.id === companyId ? "active" : ""}
                    onClick={() => chooseCompany(item.id)}
                  >
                    <span>
                      <strong>{item.name ?? item.id}</strong>
                      <small>{item.id}</small>
                    </span>
                    <span className="picker-count">
                      {fmtNumber(item.relationship_count, 0)}
                      <small> edges</small>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <Link
              className="text-link"
              to={companyId ? `/companies/${encodeURIComponent(companyId)}` : "/"}
            >
              Open company record <Icon name="arrow" size={14} />
            </Link>
          </Panel>
        </div>
      </section>
    </div>
  );
}
