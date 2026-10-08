import React, { useMemo } from "react";
import type { LessonSolution } from "../lib/types";
import type { TeachingDocument } from "../lib/teachingDocument";
import { optionStages, pathStages } from "../lib/teachingDocument";
import { SchemeEngine } from "./engines/SchemeEngine";
import { FlowEngine } from "./engines/FlowEngine";
import { PlotEngine } from "./engines/PlotEngine";
import { FigureEngine } from "./engines/FigureEngine";
import { FbdEngine } from "./engines/FbdEngine";
import { EquationCard } from "./primitives";

type Props = {
  progress: number;
  solution?: LessonSolution;
  activeSee?: string;
  title?: string;
  /** Per-scene layout override from toolkit mix (scheme | flowchart | ...) */
  layoutOverride?: string;
  docOverride?: TeachingDocument | null;
};

function asDoc(
  solution?: LessonSolution,
  docOverride?: TeachingDocument | null,
  layoutOverride?: string
): TeachingDocument | null {
  if (docOverride && docOverride.layout) {
    const o = { ...docOverride } as TeachingDocument;
    if (layoutOverride) o.layout = layoutOverride;
    return o;
  }
  const td = solution?.teachingDocument;
  if (td && td.layout) {
    const base = { ...(td as TeachingDocument) };
    if (layoutOverride) base.layout = layoutOverride;
    return base;
  }
  const pack = solution?.visualPack;
  if (!pack) return null;
  if (pack.flowGraph?.nodes?.length) {
    return {
      layout: "flowchart",
      title: pack.title,
      stages: (pack.flowGraph.nodes || []).map((n) => ({
        id: n.id,
        label: n.label,
        kind: "label",
        role: n.kind === "reagent" ? "start" : "mid",
      })),
      edges: (pack.flowGraph.edges || []).map((e) => ({
        from: e.source,
        to: e.target,
        label: e.label,
        id: e.id,
      })),
    };
  }
  if (pack.molecules?.length) {
    const roleMap: Record<string, string> = {
      reactant: "start",
      intermediate: "mid",
      product: "end",
      option: "option",
    };
    const stages = pack.molecules.map((m) => ({
      id: m.id || "m",
      label: m.label,
      smiles: m.smiles,
      kind: m.role === "option" ? "option" : "molecule",
      role: roleMap[String(m.role || "")] || "other",
      correct: m.correct,
    }));
    const path = stages.filter((s) => s.role !== "option");
    const edges = (pack.reactionSteps || []).slice(0, Math.max(0, path.length - 1)).map((r, i) => ({
      from: path[i]?.id,
      to: path[i + 1]?.id,
      label: r.reagents,
    }));
    return {
      layout: path.length >= 2 || (pack.reactionSteps || []).length >= 2 ? "scheme" : "mcq",
      title: pack.title,
      stages,
      edges,
      answer: { option: pack.correctOption },
    };
  }
  if (pack.bioFigure?.type) {
    return {
      layout: "figure",
      title: pack.title,
      figure: pack.bioFigure,
      stages: [],
      edges: [],
    };
  }
  return null;
}

/**
 * ONLY Remotion visual entry for lessons.
 * Picks an engine from TeachingDocument.layout — never per-question components.
 */
export const TeachingStage: React.FC<Props> = ({
  progress,
  solution,
  activeSee = "",
  title,
  layoutOverride,
  docOverride,
}) => {
  const doc = useMemo(
    () => asDoc(solution, docOverride, layoutOverride),
    [solution, docOverride, layoutOverride]
  );
  const layout = String(doc?.layout || "").toLowerCase();

  if (!doc) {
    if ((solution?.diagramSpec?.elements?.length || 0) >= 2) {
      return (
        <FbdEngine progress={progress} spec={solution?.diagramSpec as any} activeSee={activeSee} />
      );
    }
    return (
      <div style={{ color: "#94A3B8", padding: 16 }}>
        TeachingDocument missing — AI must return layout + stages/edges/plot/figure.
      </div>
    );
  }

  if (layout === "flowchart") {
    return <FlowEngine progress={progress} doc={doc} activeSee={activeSee} />;
  }

  if (layout === "plot") {
    if (doc.plot && ((doc.plot.series || []).length || (doc.plot.marks || []).length)) {
      return <PlotEngine progress={progress} doc={doc} activeSee={activeSee} />;
    }
    return (
      <FbdEngine progress={progress} spec={solution?.diagramSpec as any} activeSee={activeSee} />
    );
  }

  if (layout === "figure") {
    return (
      <FigureEngine
        progress={progress}
        figure={doc.figure || solution?.visualPack?.bioFigure}
        activeSee={activeSee}
      />
    );
  }

  if (layout === "fbd") {
    return (
      <FbdEngine progress={progress} spec={solution?.diagramSpec as any} activeSee={activeSee} />
    );
  }

  // scheme | mcq
  const path = pathStages(doc);
  const opts = optionStages(doc);
  const roleInv: Record<string, string> = {
    start: "reactant",
    mid: "intermediate",
    end: "product",
    option: "option",
  };
  const molecules = [...path, ...opts].map((s) => ({
    id: s.id,
    smiles: s.smiles || undefined,
    label: s.label,
    role: roleInv[String(s.role)] || String(s.role || "other"),
    correct: Boolean(s.correct),
    callout: s.callout || undefined,
  }));
  const reactionSteps = (doc.edges || []).map((e, i) => ({
    n: i + 1,
    reagents: e.label || `step ${i + 1}`,
  }));

  // Never blank: if still no stages, show equations / answer from solution
  if (!molecules.length) {
    const eqs = (solution?.equationBeats || []).slice(0, 4);
    const steps = (solution?.steps || [])
      .map((s) => (typeof s === "string" ? s : s.title || s.say || s.explanation || ""))
      .filter(Boolean)
      .slice(0, 4);
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          gap: 12,
          padding: 8,
          overflow: "hidden",
        }}
      >
        <div style={{ color: "#F8FAFC", fontSize: 24, fontWeight: 800 }}>
          {(doc.title || title || solution?.concept || "Solution").slice(0, 60)}
        </div>
        {solution?.formula ? (
          <EquationCard equation={String(solution.formula)} label="Formula" highlight compact />
        ) : null}
        {eqs.map((e, i) => (
          <EquationCard
            key={e.id || i}
            equation={String(e.latex || "")}
            label={e.label || `Step ${i + 1}`}
            compact
            highlight={i === eqs.length - 1}
          />
        ))}
        {!eqs.length &&
          steps.map((t, i) => (
            <EquationCard key={i} equation={String(t)} label={`Step ${i + 1}`} compact />
          ))}
        {/* Never dump final answer in teaching fallback — only CONCLUSION scene shows it */}
      </div>
    );
  }

  return (
    <SchemeEngine
      progress={progress}
      title={doc.title || title || "Scheme"}
      molecules={molecules}
      reactionSteps={reactionSteps}
      correctOption={doc.answer?.option}
      activeSee={activeSee}
    />
  );
};
