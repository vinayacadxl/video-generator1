export type VisualMode = "2D" | "3D";
export type VideoMode = "2D" | "3D" | "HYBRID";

export type SceneType =
  | "INTRO"
  | "HOOK"
  | "EXPLANATION"
  | "MOTION"
  | "CALCULATION"
  | "DIAGRAM"
  | "CONCLUSION"
  | "RECAP";

export interface LessonAction {
  action: string;
  target?: string;
  object?: string;
  type?: string;
  equation?: string;
  label?: string;
  color?: string;
  text?: string;
  position?: number[];
  from?: number[];
  to?: number[];
  start?: number[];
  end?: number[];
  direction?: number[];
  length?: number;
  delay?: number;
  duration?: number;
  property?: string;
  startValue?: number;
  endValue?: number;
  loop?: boolean;
  simulation?: string;
  params?: Record<string, number | string | boolean>;
  [key: string]: unknown;
}

export interface OnScreenPayload {
  title?: string;
  subtitle?: string;
  given?: string[];
  find?: string;
  bullets?: string[];
  /** Plain strings or { latex, label, id } objects from the planner */
  equations?: Array<string | { latex?: string; label?: string; id?: string }>;
  equationBeats?: EquationBeat[];
  answer?: string | null;
}

export interface VisualBeat {
  at?: number;
  see?: string;
  say?: string;
}

export interface LessonScene {
  id: string;
  type: SceneType | string;
  visualMode: VisualMode;
  duration: number;
  narration: string;
  learningGoal?: string;
  onScreen?: OnScreenPayload;
  visualBeats?: VisualBeat[];
  visuals?: string[];
  animations?: string[];
  objects?: Array<Record<string, unknown>>;
  actions?: LessonAction[];
  /** Toolkit mix: remotion_2d | smiles_scheme | dagre_flow | threejs */
  engine?: string;
  /** Force Three.js even when teachingDocument exists */
  force3D?: boolean;
  /** Per-scene TeachingDocument.layout override (scheme | flowchart | ...) */
  boardLayout?: string;
  /** Optional per-scene IR override for scheme/flow toolkit scenes */
  teachingDocumentOverride?: LessonSolution["teachingDocument"];
  camera?: {
    preset?: string;
    target?: string;
    position?: number[];
  };
}

export interface EquationBeat {
  id?: string;
  label?: string;
  latex?: string;
  say?: string;
}

export interface SolutionStep {
  id?: string;
  title?: string;
  explanation?: string;
  formula?: string;
  calculation?: string;
  visualCue?: string;
  say?: string;
}

export interface StructureAtom {
  id: string;
  x: number;
  y: number;
  label?: string;
  kind?: string;
  highlight?: boolean;
}

export interface StructureBond {
  from: string;
  to: string;
  order?: 1 | 2 | 3 | number;
  highlight?: string;
}

export interface StructureDiagram {
  title?: string;
  atoms: StructureAtom[];
  bonds: StructureBond[];
  captions?: string[];
  kind?: string;
}

export interface LessonSolution {
  concept?: string;
  teachingGoal?: string;
  given?: string[];
  find?: string;
  intuition?: string;
  formula?: string;
  steps?: Array<string | SolutionStep>;
  equationBeats?: EquationBeat[];
  answer?: string;
  answerPlain?: string;
  keyTakeaway?: string;
  commonMistake?: string;
  explanation?: string;
  /** Canonical IR — Remotion TeachingStage routes by layout */
  teachingDocument?: {
    layout: string;
    title?: string;
    stages?: Array<{
      id: string;
      kind?: string;
      label?: string;
      smiles?: string | null;
      role?: string;
      correct?: boolean;
      callout?: string | null;
    }>;
    edges?: Array<{
      from?: string;
      to?: string;
      source?: string;
      target?: string;
      label?: string;
      id?: string;
    }>;
    plot?: {
      title?: string;
      xLabel?: string;
      yLabel?: string;
      xMin?: number;
      xMax?: number;
      yMin?: number;
      yMax?: number;
      series?: Array<{ id?: string; label?: string; points?: number[][]; color?: string }>;
      marks?: Array<{ id?: string; x?: number; y?: number; label?: string }>;
    } | null;
    figure?: {
      type?: string;
      title?: string;
      highlight?: string;
      parts?: Array<{ id?: string; label?: string }>;
    } | null;
    answer?: { option?: string | null; plain?: string };
    beats?: Array<{ t?: number; focus?: string | null; say?: string }>;
  };
  /** Optional molecule graph — converted to diagramSpec for GenericDiagram */
  structureDiagram?: StructureDiagram;
  /** Rebuild of graph/schematic figures — GenericDiagram / FBD fallback */
  diagramSpec?: {
    title?: string;
    kind?: string;
    viewBox?: number[];
    elements?: Array<Record<string, unknown>>;
    phases?: Array<{ id?: string; groups?: string[]; see?: string; say?: string }>;
    rebuildFromQuestion?: boolean;
  };
  /** Shim from TeachingDocument — prefer teachingDocument */
  visualPack?: {
    domain?: string;
    title?: string;
    molecules?: Array<{
      id?: string;
      smiles?: string;
      label?: string;
      role?: string;
      correct?: boolean;
    }>;
    reactionSteps?: Array<{ n?: number; reagents?: string }>;
    correctOption?: string | null;
    bioFigure?: {
      type?: string;
      title?: string;
      highlight?: string;
      parts?: Array<{ id?: string; label?: string }>;
    };
    teachNotes?: string[];
    animationSequence?: Array<{
      at?: number;
      see?: string;
      focusId?: string;
      revealIndex?: number;
      say?: string;
      callout?: string;
    }>;
    flowGraph?: {
      title?: string;
      nodes?: Array<{ id: string; label: string; kind?: string }>;
      edges?: Array<{ id?: string; source: string; target: string; label?: string }>;
    };
  };
  preferTeachingFlow?: boolean;
  preferMoleculeBoard?: boolean;
  preferBiologyFigure?: boolean;
  simulation?: {
    type?: string;
    params?: Record<string, number | string | boolean | object>;
    describe?: string;
  };
  visualConcept?: {
    bestEngine?: string;
    primaryVisual?: string;
    why?: string;
    mustShow?: string[];
  };
  stepTexts?: string[];
}

export interface LessonPlan {
  video: {
    title: string;
    subject: string;
    topic?: string;
    targetDuration?: number;
    visualMode?: VideoMode;
    quality?: string;
    aspectRatio?: string;
    pedagogy?: string;
    engines?: { "2D"?: string; "3D"?: string };
  };
  solution?: LessonSolution;
  scenes: LessonScene[];
}

export interface SceneClipProps {
  scene: LessonScene;
  solution?: LessonSolution;
  title?: string;
  subject?: string;
  topic?: string;
  durationInSeconds: number;
  fps: number;
}

export interface LessonVideoProps {
  lesson: LessonPlan;
  fps: number;
  timeline?: Array<{
    sceneId: string;
    startTime: number;
    duration: number;
    audioPath?: string | null;
    /** Remotion public-relative path, e.g. audio/scene_01.mp3 */
    audioFile?: string | null;
  }>;
}
