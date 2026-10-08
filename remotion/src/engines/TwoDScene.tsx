import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type {
  SceneClipProps,
  LessonAction,
  LessonSolution,
  EquationBeat,
  OnScreenPayload,
  VisualBeat,
} from "../lib/types";
import {
  Arrow2D,
  EquationCard,
  KineticText,
  PopIn,
  SceneChrome,
} from "../components/primitives";
import { TeachingStage } from "../components/TeachingStage";
import { FbdEngine } from "../components/engines/FbdEngine";
import { SmilesCanvas } from "../components/engines/SchemeEngine";
import { formatMath } from "../lib/formatMath";
import {
  projectilePosition,
  projectileRange,
  projectileTimeOfFlight,
  trajectoryPoints,
} from "../lib/simulations";

/** Never show raw {'id': 'step_01', ...} on screen. */
function asDisplayText(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") {
    const t = value.trim();
    if (
      (/^\s*\{/.test(t) && /'id'\s*:|"id"\s*:/.test(t)) ||
      (t.includes("'id'") && t.includes("'title'") && t.includes("'explanation'"))
    ) {
      const title = t.match(/['"]title['"]\s*:\s*['"]([^'"]+)['"]/);
      const expl = t.match(/['"]explanation['"]\s*:\s*['"]([^'"]+)['"]/);
      const say = t.match(/['"]say['"]\s*:\s*['"]([^'"]+)['"]/);
      return title?.[1] || expl?.[1] || say?.[1] || "Step";
    }
    return t;
  }
  if (typeof value === "object") {
    const o = value as Record<string, unknown>;
    return String(o.title || o.explanation || o.say || o.latex || o.label || o.text || "");
  }
  return String(value);
}

function normalizeEq(item: unknown, i: number): EquationBeat | null {
  if (!item) return null;
  if (typeof item === "string") {
    const latex = asDisplayText(item);
    if (!latex) return null;
    return { id: `eq${i + 1}`, label: i === 0 ? "Formula" : `Step ${i}`, latex };
  }
  if (typeof item === "object") {
    const o = item as {
      latex?: string;
      label?: string;
      id?: string;
      say?: string;
      title?: string;
      explanation?: string;
    };
    const latex = asDisplayText(o.latex || o.title || o.explanation || o.say || "");
    if (!latex) return null;
    return {
      id: o.id || `eq${i + 1}`,
      label: o.label || o.title || (i === 0 ? "Formula" : `Step ${i}`),
      latex,
      say: o.say,
    };
  }
  return null;
}

function beatMeta(
  solution?: LessonSolution,
  onScreen?: OnScreenPayload,
  actions: LessonAction[] = []
): EquationBeat[] {
  if (onScreen?.equationBeats?.length) return onScreen.equationBeats;
  if (onScreen?.equations?.length) {
    return onScreen.equations
      .map((eq, i) => normalizeEq(eq, i))
      .filter(Boolean) as EquationBeat[];
  }
  if (solution?.equationBeats?.length) return solution.equationBeats;
  const fromActions = actions
    .filter((a) => a.action === "SHOW_EQUATION" && a.equation)
    .map((a, i) => ({
      id: `eq${i + 1}`,
      label: String(a.label || (i === 0 ? "Formula" : `Step ${i}`)),
      latex: String(a.equation),
    }));
  if (fromActions.length) return fromActions;
  const out: EquationBeat[] = [];
  if (solution?.formula) out.push({ id: "eq1", label: "Formula", latex: String(solution.formula) });
  for (const step of solution?.steps || []) {
    if (typeof step === "string") out.push({ latex: step });
    else
      out.push({
        latex: String(step.calculation || step.formula || step.explanation || ""),
        label: step.title,
      });
  }
  if (solution?.answer) out.push({ id: "eq_ans", label: "Answer", latex: String(solution.answer) });
  return out.filter((b) => b.latex);
}

/** Never truncate with "…" — wrap so the full line is readable. */
const ChipRow: React.FC<{
  items: string[];
  accent?: string;
  startDelay?: number;
  /** How many chips to show (progressive). Default = all. */
  visibleCount?: number;
  highlightLast?: boolean;
}> = ({
  items,
  accent = "#38BDF8",
  startDelay = 8,
  visibleCount,
  highlightLast = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!items?.length) return null;
  const n = Math.min(
    items.length,
    visibleCount == null ? items.length : Math.max(0, visibleCount)
  );
  if (n <= 0) return null;
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 10,
        marginBottom: 14,
        alignItems: "stretch",
      }}
    >
      {items.slice(0, n).map((item, i) => {
        const local = Math.max(0, frame - (startDelay + i * 6));
        const s = spring({ frame: local, fps, config: { damping: 14, stiffness: 140 } });
        const hi = highlightLast && i === n - 1;
        const long = item.length > 42;
        return (
          <div
            key={`${item}-${i}`}
            style={{
              transform: `translateY(${interpolate(s, [0, 1], [16, 0])}px) scale(${0.9 + 0.1 * s})`,
              opacity: s,
              padding: long ? "10px 16px" : "8px 14px",
              borderRadius: long ? 14 : 999,
              border: `1px solid ${hi ? "#F8FAFC" : `${accent}88`}`,
              background: hi
                ? `linear-gradient(135deg, ${accent}66, ${accent}33)`
                : `linear-gradient(135deg, ${accent}33, ${accent}14)`,
              color: "#F1F5F9",
              fontSize: long ? 15 : 16,
              fontWeight: 700,
              maxWidth: long ? "100%" : 560,
              flex: long ? "1 1 100%" : "0 1 auto",
              lineHeight: 1.35,
              whiteSpace: "normal",
              overflow: "visible",
              textOverflow: "clip",
              wordBreak: "break-word",
              overflowWrap: "anywhere",
            }}
          >
            {formatMath(item)}
          </div>
        );
      })}
    </div>
  );
};

const ProjectileDiagram: React.FC<{ progress: number; u?: number; theta?: number; g?: number }> = ({
  progress,
  u = 20,
  theta = 45,
  g = 9.8,
}) => {
  const T = projectileTimeOfFlight(u, theta, g);
  const range = projectileRange(u, theta, g);
  const pts = trajectoryPoints(u, theta, g, 48);
  const ball = projectilePosition(progress * T, u, theta, g);
  const scaleX = 700 / Math.max(range, 1);
  const scaleY = 260 / Math.max(...pts.map((p) => p.y), 1);
  const ox = 140;
  const oy = 400;
  const trailLen = Math.max(1, Math.floor(progress * pts.length));
  const bx = ox + ball.x * scaleX;
  const by = oy - ball.y * scaleY;
  return (
    <svg width="100%" height="440" viewBox="0 0 1000 440">
      <line x1={ox} y1={oy} x2={ox + 700} y2={oy} stroke="#334155" strokeWidth={3} />
      <line x1={ox} y1={oy} x2={ox} y2={oy - 300} stroke="#334155" strokeWidth={3} />
      <path
        d={pts
          .slice(0, trailLen)
          .map((p, i) => `${i === 0 ? "M" : "L"} ${ox + p.x * scaleX} ${oy - p.y * scaleY}`)
          .join(" ")}
        stroke="#38BDF8"
        strokeWidth={5}
        fill="none"
      />
      <circle cx={bx} cy={by} r={14} fill="#F59E0B" />
      <text x={bx + 16} y={by - 10} fill="#FDE68A" fontSize={18} fontWeight={700}>
        projectile
      </text>
    </svg>
  );
};

/** Route by TeachingDocument.layout (single IR). */
function detectVisual(scene: SceneClipProps["scene"], solution?: LessonSolution, topic?: string, title?: string) {
  const td = solution?.teachingDocument;
  const layout = String(td?.layout || "").toLowerCase();
  const primary = String(solution?.visualConcept?.primaryVisual || "").toLowerCase();
  const pack = solution?.visualPack;
  const blob = `${scene.narration} ${topic || ""} ${title || ""} ${solution?.concept || ""} ${(scene.visuals || []).join(" ")}`.toLowerCase();

  // Circuit / exam figure from question image — prefer FBD over empty scheme boards
  const hasFig = (solution?.diagramSpec?.elements?.length || 0) >= 2;
  const engine = String((scene as { engine?: string }).engine || "");
  const sceneTypeEarly = String(scene.type || "").toUpperCase();
  // Question-explain / plain math cards — do not auto-route to FBD via solution.diagramSpec
  if (
    sceneTypeEarly === "HOOK" ||
    sceneTypeEarly === "CALCULATION" ||
    sceneTypeEarly === "RECAP" ||
    sceneTypeEarly === "CONCLUSION" ||
    engine === "remotion_2d"
  ) {
    return "cards";
  }
  if (engine === "fbd_diagram" || String((scene as { boardLayout?: string }).boardLayout || "") === "fbd") {
    return hasFig ? "diagram_spec" : "teaching_stage";
  }
  if (hasFig && (layout === "fbd" || primary === "diagram_spec" || engine === "fbd_diagram")) {
    return "diagram_spec";
  }
  if (
    (scene as { boardLayout?: string; teachingDocumentOverride?: unknown })?.boardLayout ||
    ["smiles_scheme", "dagre_flow"].includes(engine) ||
    (scene as { teachingDocumentOverride?: unknown }).teachingDocumentOverride
  ) {
    return "teaching_stage";
  }
  if (td?.layout && layout !== "fbd") {
    if (
      primary.startsWith("teaching_") ||
      solution?.preferMoleculeBoard ||
      solution?.preferTeachingFlow ||
      solution?.preferBiologyFigure
    ) {
      return "teaching_stage";
    }
    if (layout === "scheme" || layout === "mcq" || layout === "flowchart" || layout === "figure" || layout === "plot") {
      return "teaching_stage";
    }
  }
  if (pack?.molecules?.length || pack?.flowGraph?.nodes?.length || pack?.bioFigure?.type) {
    return "teaching_stage";
  }
  if (layout === "fbd" || hasFig || primary === "diagram_spec") {
    return "diagram_spec";
  }
  if (
    (solution?.simulation?.type || "").toLowerCase() === "projectile" ||
    /projectile|thrown at an angle|parabolic path|angle of projection/.test(blob)
  ) {
    return "projectile";
  }
  return "diagram_spec";
}

function activeBeatIndex(beats: VisualBeat[] | undefined, timeSec: number): number {
  if (!beats?.length) return 0;
  let idx = 0;
  for (let i = 0; i < beats.length; i++) {
    if (timeSec >= (beats[i].at || 0)) idx = i;
  }
  return idx;
}

export const TwoDScene: React.FC<SceneClipProps> = ({
  scene,
  solution,
  title,
  subject,
  topic,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const actions = scene.actions || [];
  const onScreen = scene.onScreen || {};
  const beats = scene.visualBeats || [];
  const sceneType = String(scene.type || "EXPLANATION").toUpperCase();
  const timeSec = frame / Math.max(fps, 1);
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const beatIdx = activeBeatIndex(beats, timeSec);
  const spokenLine = (beats[beatIdx]?.say || "").trim();

  const displayTitle = onScreen.title || title || topic || solution?.concept || "Concept";
  const subtitle =
    onScreen.subtitle ||
    scene.learningGoal ||
    solution?.teachingGoal ||
    "";
  const given = (onScreen.given?.length ? onScreen.given : solution?.given || [])
    .map(asDisplayText)
    .filter(Boolean)
    .slice(0, 8);
  const find = asDisplayText(onScreen.find || solution?.find || "");
  const bullets = (onScreen.bullets || [])
    .map(asDisplayText)
    .filter(Boolean)
    .slice(0, 8);
  const isQuestionHook =
    sceneType === "HOOK" || sceneType === "INTRO" || sceneType === "QUESTION";
  // HOOK: never pull solution formulas/answer into the board
  const meta = (
    isQuestionHook || (onScreen as { hideFormulas?: boolean }).hideFormulas
      ? []
      : beatMeta(solution, onScreen, actions)
  ).slice(0, 8);
  const visual = detectVisual(scene, solution, topic, title);
  // HOOK always explains the question with chips — never steal the board for FBD
  const showTeaching = visual === "teaching_stage" && !isQuestionHook;
  const showGeneric = visual === "diagram_spec" && !isQuestionHook;
  const activeSee = String(beats[beatIdx]?.see || "");

  const params = solution?.simulation?.params || {};
  const u = Number(params.u ?? 20);
  const theta = Number(params.theta ?? 45);
  const g = Number(params.g ?? 9.8);

  const diagramScene =
    sceneType === "MOTION" ||
    sceneType === "INTRO" ||
    sceneType === "INTUITION" ||
    sceneType === "EXPLANATION" ||
    sceneType === "DIAGRAM" ||
    sceneType === "SIMULATION";

  const showDiagram =
    (showTeaching || showGeneric || visual === "projectile") && diagramScene;

  const questionText = asDisplayText(
    (onScreen as { questionText?: string }).questionText ||
      solution?.questionText ||
      ""
  );

  const boardOnly =
    Boolean((onScreen as { boardOnly?: boolean }).boardOnly) ||
    ["flowchart", "scheme"].includes(
      String((scene as { boardLayout?: string }).boardLayout || "").toLowerCase()
    ) ||
    ["dagre_flow", "smiles_scheme"].includes(String(scene.engine || ""));

  const showMath =
    !boardOnly &&
    !isQuestionHook &&
    (sceneType === "CALCULATION" ||
      sceneType === "CONCLUSION" ||
      sceneType === "RECAP" ||
      Boolean(onScreen.equationBeats?.length) ||
      Boolean(onScreen.equations?.length) ||
      (!showDiagram && meta.length > 0 && sceneType !== "INTUITION"));

  const revealFromBeats = beats.length ? beatIdx + 1 : 0;
  const revealCount = Math.max(
    1,
    Math.min(
      Math.max(meta.length, bullets.length, 1),
      revealFromBeats ||
        Math.floor(progress * (Math.max(meta.length, bullets.length, 1) + 0.2)) + 1
    )
  );

  // Final answer ONLY on last scenes — never mid-lesson spoil
  const answer =
    isQuestionHook ||
    (onScreen as { hideAnswer?: boolean }).hideAnswer ||
    !["CONCLUSION", "RECAP"].includes(sceneType)
      ? null
      : onScreen.answer || solution?.answer || null;

  const questionAnchor = (onScreen as {
    questionAnchor?: { smiles?: string; label?: string } | null;
  }).questionAnchor;

  // Progressive HOOK: count given beats so far → how many chips to show
  const givenBeatsSoFar = beats
    .slice(0, beatIdx + 1)
    .filter((b) => String(b.see || "").includes("given")).length;
  // Progressive: title → figure → question → givens → find (never answer)
  const showHookFigure =
    isQuestionHook &&
    Boolean(questionAnchor?.smiles) &&
    /question|figure|given|find|goal|options/i.test(activeSee);
  const showHookQuestion =
    isQuestionHook && /question|given|find|goal|options/i.test(activeSee);
  const showHookFind = isQuestionHook && /find|goal|options/i.test(activeSee);

  const layoutSplit =
    (showTeaching || showGeneric) &&
    (bullets.length > 0 || meta.length > 0) &&
    !isQuestionHook &&
    !boardOnly;
  const compact = (showTeaching || showGeneric) && !isQuestionHook;
  // Caption wraps fully — reserve enough height (no "..." cut)
  const captionReserve = spokenLine
    ? boardOnly
      ? spokenLine.length > 80
        ? 120
        : 96
      : spokenLine.length > 80
        ? 130
        : 110
    : boardOnly
      ? 16
      : 24;
  const pack = solution?.visualPack;

  return (
    <SceneChrome subject={subject} topic={topic || title} sceneType={sceneType}>
      <AbsoluteFill
        style={{
          padding: boardOnly
            ? `52px 24px ${captionReserve}px 24px`
            : compact
              ? `72px 36px ${captionReserve}px 36px`
              : `78px 40px ${captionReserve}px 40px`,
          overflow: "hidden",
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            height: "100%",
            display: "flex",
            flexDirection: "column",
            gap: 8,
            overflow: "hidden",
          }}
        >
          {/* Flow/diagram scenes: chrome already has title — avoid duplicate heading */}
          {!boardOnly ? (
            <KineticText
              text={displayTitle}
              style={{
                fontSize: compact ? 26 : 38,
                fontWeight: 800,
                color: "#F8FAFC",
                lineHeight: 1.2,
              }}
            />
          ) : null}
          {/* Subtitle = static scene hint only. Spoken line = bottom caption only (no duplicate). */}
          {subtitle && (!compact || isQuestionHook) && !spokenLine ? (
            <KineticText
              delay={4}
              text={subtitle}
              style={{
                fontSize: 18,
                color: "#94A3B8",
                maxWidth: 1200,
                lineHeight: 1.35,
              }}
            />
          ) : null}

          {/* HOOK: only question when that beat is active — no formula dump */}
          {/* HOOK: paper figure (reactant) + question text — students see the relation */}
          {isQuestionHook && (showHookFigure || showHookQuestion) ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  showHookFigure && questionAnchor?.smiles && showHookQuestion && questionText
                    ? "0.42fr 0.58fr"
                    : "1fr",
                gap: 12,
                alignItems: "stretch",
                minHeight: 0,
              }}
            >
              {showHookFigure && questionAnchor?.smiles ? (
                <PopIn delay={2}>
                  <div
                    style={{
                      background: "rgba(15, 23, 42, 0.92)",
                      border: /figure/i.test(activeSee)
                        ? "2px solid #FBBF24"
                        : "1px solid rgba(56,189,248,0.4)",
                      borderRadius: 16,
                      padding: "12px 14px",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <div
                      style={{
                        alignSelf: "flex-start",
                        color: "#94A3B8",
                        fontSize: 13,
                        fontWeight: 800,
                        letterSpacing: 1.1,
                        textTransform: "uppercase",
                      }}
                    >
                      Question figure
                    </div>
                    <SmilesCanvas
                      smiles={questionAnchor.smiles}
                      width={280}
                      height={170}
                    />
                    <div
                      style={{
                        color: "#E2E8F0",
                        fontSize: 15,
                        fontWeight: 700,
                        textAlign: "center",
                        lineHeight: 1.3,
                      }}
                    >
                      {questionAnchor.label || "Starting material"}
                    </div>
                  </div>
                </PopIn>
              ) : null}
              {showHookQuestion && questionText ? (
                <PopIn delay={4}>
                  <EquationCard
                    equation={questionText}
                    label="Question"
                    highlight={/question/i.test(activeSee)}
                    compact={questionText.length > 160}
                  />
                </PopIn>
              ) : null}
            </div>
          ) : null}

          {/* HOOK: reveal given chips one-by-one with speech */}
          {isQuestionHook ? (
            <ChipRow
              items={given}
              accent="#38BDF8"
              startDelay={4}
              visibleCount={givenBeatsSoFar}
              highlightLast
            />
          ) : !compact ? (
            <ChipRow items={given} accent="#38BDF8" startDelay={8} />
          ) : null}

          {isQuestionHook && showHookFind && find ? (
            <ChipRow
              items={[`Find: ${formatMath(find)}`]}
              accent="#A78BFA"
              startDelay={4}
              visibleCount={1}
              highlightLast
            />
          ) : !isQuestionHook && !compact && find ? (
            <ChipRow items={[`Find: ${formatMath(find)}`]} accent="#A78BFA" startDelay={12} />
          ) : null}

          <div
            style={{
              flex: 1,
              minHeight: 0,
              display: "grid",
              gridTemplateColumns: layoutSplit ? "1.2fr 0.8fr" : "1fr",
              gap: 12,
              overflow: "hidden",
              alignItems: "stretch",
            }}
          >
            {showDiagram && showTeaching ? (
              <div style={{ minHeight: 0, height: "100%", overflow: "hidden" }}>
                <TeachingStage
                  progress={Math.min(1, Math.max(0.18, progress * 1.05))}
                  solution={solution}
                  activeSee={activeSee}
                  title={pack?.title || displayTitle}
                  layoutOverride={scene.boardLayout || undefined}
                  docOverride={(scene.teachingDocumentOverride as any) || null}
                />
              </div>
            ) : null}

            {showDiagram && showGeneric && !showTeaching ? (
              <div style={{ minHeight: 0, height: "100%", overflow: "hidden" }}>
                <FbdEngine
                  progress={Math.min(1, progress * 1.05)}
                  spec={solution?.diagramSpec as any}
                  activeSee={activeSee}
                />
              </div>
            ) : null}

            {showDiagram && visual === "projectile" ? (
              <div style={{ position: "relative", height: "100%" }}>
                <ProjectileDiagram progress={Math.min(1, progress * 1.1)} u={u} theta={theta} g={g} />
                <Arrow2D x1={140} y1={400} x2={260} y2={300} color="#22D3EE" label="ux" delay={8} />
                <Arrow2D x1={140} y1={400} x2={140} y2={260} color="#F472B6" label="uy" delay={14} />
              </div>
            ) : null}

            <div style={{ minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column", gap: 10 }}>
              {showMath ? (
                <div style={{ display: "grid", gap: 10, maxHeight: "100%", overflow: "hidden" }}>
                  {meta.slice(0, revealCount).map((b, i) => {
                    const enter = spring({
                      frame: Math.max(0, frame - (8 + i * 10)),
                      fps,
                      config: { damping: 16, stiffness: 120 },
                    });
                    return (
                      <div
                        key={`${b.id || i}-${b.latex}`}
                        style={{
                          transform: `translateX(${interpolate(enter, [0, 1], [36, 0])}px)`,
                          opacity: enter,
                        }}
                      >
                        <EquationCard
                          equation={String(b.latex || "")}
                          label={b.label || (i === 0 ? "Formula" : `Step ${i + 1}`)}
                          highlight={i === revealCount - 1}
                          compact
                        />
                      </div>
                    );
                  })}
                </div>
              ) : null}

              {/* Never dump bullets on HOOK (they used to spoil answer/formulas) */}
              {!boardOnly && !isQuestionHook && bullets.length && (!showMath || layoutSplit) ? (
                <div style={{ display: "grid", gap: 10 }}>
                  {bullets.slice(0, revealCount).map((b, i) => (
                    <PopIn key={`${b}-${i}`} delay={6 + i * 8}>
                      <EquationCard
                        equation={b}
                        label={i === 0 ? "Step" : undefined}
                        compact
                        highlight={i === revealCount - 1}
                      />
                    </PopIn>
                  ))}
                </div>
              ) : null}

              {/* Voice = bottom caption only; never dump narration as IDEA card */}
              {null}

              {answer ? (
                <PopIn delay={Math.floor(fps * 0.2)}>
                  <EquationCard equation={String(answer)} label="Final Answer" highlight compact />
                </PopIn>
              ) : null}
            </div>
          </div>
        </div>

        {spokenLine ? (
          <div
            style={{
              position: "absolute",
              left: "50%",
              transform: "translateX(-50%)",
              bottom: 64,
              width: "min(1100px, 88%)",
              padding: "12px 20px",
              borderRadius: 14,
              background: "rgba(6, 12, 24, 0.88)",
              border: "1px solid rgba(255, 255, 255, 0.22)",
              color: "#FFFFFF",
              fontSize: spokenLine.length > 90 ? 18 : 22,
              fontWeight: 700,
              lineHeight: 1.35,
              textAlign: "center",
              maxHeight: 110,
              overflow: "visible",
              whiteSpace: "normal",
              wordBreak: "break-word",
              textShadow: "0 1px 8px rgba(0,0,0,0.55)",
            }}
          >
            {spokenLine}
          </div>
        ) : null}
      </AbsoluteFill>
    </SceneChrome>
  );
};
