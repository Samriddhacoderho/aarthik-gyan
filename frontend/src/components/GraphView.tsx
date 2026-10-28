import { useEffect, useRef, useState } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import type { GraphEdge, GraphNode } from "../api/types";
import { titleCase } from "../utils/format";
import { Icon } from "./Icons";

const TYPE_COLORS: Record<string, string> = {
  Company: "#1f4d3a",
  Executive: "#bd6b3c",
  Subsidiary: "#6f8269",
  RiskFactor: "#9b3b34",
  Auditor: "#3d5f86",
};

export function GraphView({
  nodes,
  edges,
  onSelect,
  height = 520,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelect?: (node: GraphNode | null) => void;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const [empty, setEmpty] = useState(nodes.length === 0);

  useEffect(() => {
    if (!containerRef.current) return;
    const elements: ElementDefinition[] = [
      ...nodes.map((node) => ({
        group: "nodes" as const,
        data: {
          id: node.id,
          label: node.name || node.id,
          type: node.type || "Entity",
        },
      })),
      ...edges.map((edge, index) => ({
        group: "edges" as const,
        data: {
          id: `edge-${index}-${edge.source}-${edge.target}`,
          source: edge.source,
          target: edge.target,
          label: edge.type || "RELATED",
          detail: edge.detail || "",
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      wheelSensitivity: 0.18,
      layout: {
        name: "cose",
        animate: false,
        fit: true,
        padding: 36,
        nodeRepulsion: () => 9000,
        idealEdgeLength: () => 100,
        gravity: 0.35,
      },
      style: [
        {
          selector: "node",
          style: {
            width: 34,
            height: 34,
            "background-color": "#6f8269",
            label: "data(label)",
            color: "#24332a",
            "font-size": 9,
            "font-family": "system-ui, sans-serif",
            "text-valign": "bottom",
            "text-margin-y": 7,
            "text-wrap": "wrap",
            "text-max-width": "90px",
            "border-width": 2,
            "border-color": "#fbfaf6",
          },
        },
        {
          selector: 'node[type = "Company"]',
          style: {
            width: 58,
            height: 42,
            shape: "round-rectangle",
            "background-color": "#1f4d3a",
            color: "#ffffff",
            "font-size": 10,
            "font-weight": 600,
          },
        },
        {
          selector: 'node[type = "Executive"]',
          style: { shape: "ellipse", "background-color": "#bd6b3c" },
        },
        {
          selector: 'node[type = "Subsidiary"]',
          style: { shape: "round-rectangle", "background-color": "#6f8269" },
        },
        {
          selector: 'node[type = "RiskFactor"]',
          style: { shape: "diamond", width: 38, height: 38, "background-color": "#9b3b34" },
        },
        {
          selector: 'node[type = "Auditor"]',
          style: { shape: "hexagon", "background-color": "#3d5f86" },
        },
        {
          selector: "node:selected",
          style: { "border-width": 3, "border-color": "#bd6b3c" },
        },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "line-color": "#c7c0b2",
            "target-arrow-color": "#c7c0b2",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 7,
            "font-family": "system-ui, sans-serif",
            color: "#7a8279",
            "text-rotation": "autorotate",
            "text-background-color": "#fbfaf6",
            "text-background-opacity": 0.88,
            "text-background-padding": "2px",
          },
        },
        {
          selector: "edge:selected",
          style: { "line-color": "#bd6b3c", "target-arrow-color": "#bd6b3c", width: 2 },
        },
      ],
    });

    cyRef.current = cy;
    setEmpty(elements.length === 0);
    cy.on("tap", "node", (event) => {
      const node = event.target;
      onSelect?.({
        id: String(node.id()),
        name: String(node.data("label") ?? ""),
        type: String(node.data("type") ?? ""),
      });
    });
    cy.on("tap", (event) => {
      if (event.target === cy) onSelect?.(null);
    });

    const observer = new ResizeObserver(() => {
      cy.resize();
      cy.fit(undefined, 36);
    });
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
  }, [nodes, edges, onSelect]);

  return (
    <div className="graph-shell" style={{ height }}>
      <div ref={containerRef} className="graph-canvas" />
      {empty && (
        <div className="graph-empty">
          <p>No graph relationships are available for this company yet.</p>
        </div>
      )}
      <div className="graph-controls">
        <button
          type="button"
          className="icon-button"
          title="Fit graph"
          onClick={() => cyRef.current?.fit(undefined, 36)}
        >
          <Icon name="scale" size={16} />
        </button>
        <button
          type="button"
          className="icon-button"
          title="Reset view"
          onClick={() => {
            cyRef.current?.center();
            cyRef.current?.fit(undefined, 36);
          }}
        >
          <Icon name="refresh" size={16} />
        </button>
      </div>
      <div className="graph-legend">
        {Object.keys(TYPE_COLORS).map((type) => (
          <span key={type}>
            <i style={{ background: TYPE_COLORS[type] }} />
            {titleCase(type)}
          </span>
        ))}
      </div>
    </div>
  );
}
