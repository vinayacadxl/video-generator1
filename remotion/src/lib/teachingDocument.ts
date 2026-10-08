/** Canonical TeachingDocument IR — mirrors ai/teaching_document.py */

export type TeachingLayout =
  | "scheme"
  | "flowchart"
  | "plot"
  | "figure"
  | "mcq"
  | "fbd";

export type StageKind =
  | "molecule"
  | "label"
  | "gas"
  | "option"
  | "axis_mark"
  | "bio_part";

export type StageRole = "start" | "mid" | "end" | "option" | "reagent" | "other";

export interface TeachingStage {
  id: string;
  kind?: StageKind | string;
  label?: string;
  smiles?: string | null;
  role?: StageRole | string;
  correct?: boolean;
  callout?: string | null;
}

export interface TeachingEdge {
  from?: string;
  to?: string;
  source?: string;
  target?: string;
  label?: string;
  id?: string;
}

export interface PlotSeries {
  id?: string;
  label?: string;
  points?: number[][];
  color?: string;
}

export interface PlotSpec {
  title?: string;
  xLabel?: string;
  yLabel?: string;
  xMin?: number;
  xMax?: number;
  yMin?: number;
  yMax?: number;
  series?: PlotSeries[];
  marks?: Array<{ id?: string; x?: number; y?: number; label?: string }>;
}

export interface FigureSpec {
  type?: string;
  title?: string;
  highlight?: string;
  parts?: Array<{ id?: string; label?: string }>;
}

export interface TeachingDocument {
  layout: TeachingLayout | string;
  title?: string;
  stages?: TeachingStage[];
  edges?: TeachingEdge[];
  plot?: PlotSpec | null;
  figure?: FigureSpec | null;
  answer?: { option?: string | null; plain?: string };
  beats?: Array<{ t?: number; focus?: string | null; say?: string }>;
}

export function edgeSource(e: TeachingEdge): string {
  return String(e.from || e.source || "");
}

export function edgeTarget(e: TeachingEdge): string {
  return String(e.to || e.target || "");
}

export function pathStages(doc: TeachingDocument): TeachingStage[] {
  const stages = doc.stages || [];
  const roles = ["start", "mid", "end"];
  const ordered = roles.flatMap((r) => stages.filter((s) => String(s.role) === r));
  if (ordered.length >= 1) return ordered;
  return stages.filter((s) => String(s.role) !== "option");
}

export function optionStages(doc: TeachingDocument): TeachingStage[] {
  return (doc.stages || []).filter(
    (s) =>
      String(s.role) === "option" ||
      String(s.kind) === "option" ||
      /^\([A-D]\)/i.test(s.label || "")
  );
}
