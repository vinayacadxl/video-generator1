import React, { useMemo } from "react";
import dagre from "dagre";
import {
  Background,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { TeachingDocument } from "../../lib/teachingDocument";
import { edgeSource, edgeTarget } from "../../lib/teachingDocument";

type Props = {
  progress: number;
  doc: TeachingDocument;
  activeSee?: string;
};

/** Larger nodes so vertical schemes fill the stage (not a tiny strip). */
const NODE_W = 320;
const NODE_H = 78;

function resolveFocus(activeSee: string, order: string[], progress: number) {
  const s = (activeSee || "").toLowerCase();
  const m = s.match(/^flow_(?:node_)?(.+)$/);
  if (m && m[1] !== "main" && m[1] !== "answer") {
    const tail = m[1].toLowerCase();
    const idx = order.findIndex((id) => id.toLowerCase() === tail);
    if (idx >= 0) return { idx, focusId: order[idx] };
    const idx2 = order.findIndex(
      (id) => tail.endsWith(id.toLowerCase()) || id.toLowerCase().endsWith(tail)
    );
    if (idx2 >= 0) return { idx: idx2, focusId: order[idx2] };
  }
  const idx = Math.min(
    order.length - 1,
    Math.floor(progress * Math.max(order.length, 1) * 0.92)
  );
  return { idx: Math.max(0, idx), focusId: order[idx] || "" };
}

function layoutPositions(doc: TeachingDocument) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: "TB",
    nodesep: 56,
    ranksep: 88,
    marginx: 16,
    marginy: 16,
  });
  (doc.stages || []).forEach((s) => {
    g.setNode(s.id, { width: NODE_W, height: NODE_H });
  });
  (doc.edges || []).forEach((e) => {
    const a = edgeSource(e);
    const b = edgeTarget(e);
    if (a && b) g.setEdge(a, b);
  });
  dagre.layout(g);
  const positions = new Map<string, { x: number; y: number }>();
  (doc.stages || []).forEach((s) => {
    const n = g.node(s.id);
    if (n) positions.set(s.id, { x: n.x - NODE_W / 2, y: n.y - NODE_H / 2 });
  });
  return positions;
}

function bfsOrder(doc: TeachingDocument): string[] {
  const ids = (doc.stages || []).map((s) => s.id);
  const edges = doc.edges || [];
  const inc = new Map(ids.map((id) => [id, 0]));
  edges.forEach((e) => {
    const t = edgeTarget(e);
    if (inc.has(t)) inc.set(t, (inc.get(t) || 0) + 1);
  });
  const roots = ids.filter((id) => (inc.get(id) || 0) === 0);
  const q = roots.length ? [...roots] : ids.slice(0, 1);
  const order: string[] = [];
  const seen = new Set<string>();
  while (q.length) {
    const id = q.shift()!;
    if (seen.has(id)) continue;
    seen.add(id);
    order.push(id);
    edges.forEach((e) => {
      if (edgeSource(e) === id && !seen.has(edgeTarget(e))) q.push(edgeTarget(e));
    });
  }
  ids.forEach((id) => {
    if (!seen.has(id)) order.push(id);
  });
  return order;
}

/**
 * Flowchart engine: dagre layout + React Flow.
 * Sized to fill the teaching board — not a tiny centered strip.
 */
export const FlowEngine: React.FC<Props> = ({ progress, doc, activeSee = "" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const order = useMemo(() => bfsOrder(doc), [doc]);
  const positions = useMemo(() => layoutPositions(doc), [doc]);
  const { idx, focusId } = useMemo(
    () => resolveFocus(activeSee, order, progress),
    [activeSee, order, progress]
  );
  const revealed = useMemo(() => new Set(order.slice(0, idx + 1)), [order, idx]);

  const show = Math.max(
    0.9,
    interpolate(progress, [0, 0.1], [0.9, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );

  const nodes: Node[] = useMemo(() => {
    return (doc.stages || []).map((s) => {
      const pos = positions.get(s.id) || { x: 0, y: 0 };
      const visible = revealed.has(s.id);
      const focused = s.id === focusId;
      return {
        id: s.id,
        position: { x: pos.x, y: pos.y },
        data: { label: s.label || s.id },
        style: {
          width: NODE_W,
          minHeight: NODE_H,
          background: focused ? "rgba(251,191,36,0.22)" : "rgba(15,23,42,0.96)",
          border: `3px solid ${focused ? "#FBBF24" : "#38BDF8"}`,
          borderRadius: 14,
          color: "#F8FAFC",
          fontWeight: 800,
          fontSize: 15,
          lineHeight: 1.3,
          opacity: visible ? 1 : 0.22,
          padding: "12px 14px",
          textAlign: "center" as const,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          whiteSpace: "normal" as const,
          wordBreak: "break-word" as const,
          boxShadow: focused ? "0 0 0 4px rgba(251,191,36,0.25)" : "none",
        },
        draggable: false,
        selectable: false,
      };
    });
  }, [doc.stages, positions, revealed, focusId, frame, fps]);

  const edges: Edge[] = useMemo(() => {
    return (doc.edges || []).map((e, i) => {
      const a = edgeSource(e);
      const b = edgeTarget(e);
      const visible = revealed.has(a) && revealed.has(b);
      return {
        id: e.id || `${a}-${b}-${i}`,
        source: a,
        target: b,
        label: e.label ? String(e.label) : undefined,
        animated: focusId === b,
        style: {
          stroke: focusId === b ? "#FBBF24" : "#94A3B8",
          strokeWidth: focusId === b ? 3 : 2.5,
          opacity: visible ? 1 : 0.18,
        },
        labelStyle: {
          fill: "#FECACA",
          fontWeight: 800,
          fontSize: 13,
        },
        labelBgStyle: { fill: "rgba(2,6,23,0.85)" },
        labelBgPadding: [4, 6] as [number, number],
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: focusId === b ? "#FBBF24" : "#94A3B8",
        },
      };
    });
  }, [doc.edges, revealed, focusId]);

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
        opacity: show,
      }}
    >
      <div
        style={{
          flex: 1,
          minHeight: 420,
          borderRadius: 16,
          border: "1px solid rgba(56,189,248,0.28)",
          background: "rgba(2,6,23,0.72)",
          overflow: "hidden",
        }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.06, maxZoom: 1.35, minZoom: 0.45 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          preventScrolling
          proOptions={{ hideAttribution: true }}
          colorMode="dark"
        >
          <Background color="#1E293B" gap={28} />
        </ReactFlow>
      </div>
    </div>
  );
};
