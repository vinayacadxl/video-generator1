import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  continueRender,
  delayRender,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type MoleculeItem = {
  id?: string;
  smiles?: string;
  label?: string;
  role?: string;
  correct?: boolean;
  callout?: string;
};

export type ReactionStep = { n?: number; reagents?: string };

type Props = {
  progress: number;
  title?: string;
  molecules?: MoleculeItem[];
  reactionSteps?: ReactionStep[];
  correctOption?: string | null;
  activeSee?: string;
};

function resolveReveal(
  activeSee: string,
  pathLen: number,
  progress: number,
  pathIds: string[] = []
) {
  const s = (activeSee || "").toLowerCase();
  if (s === "mol_options" || s === "mol_answer") {
    return {
      revealIndex: Math.max(0, pathLen - 1),
      showOptions: true,
      focusId: "",
      answerPulse: s === "mol_answer",
    };
  }
  const m = s.match(/^mol_(.+)$/);
  if (m && m[1] !== "main" && m[1] !== "path") {
    const tail = m[1].toLowerCase();
    let idx = pathIds.findIndex((id) => id.toLowerCase() === tail);
    if (idx < 0) {
      idx = pathIds.findIndex(
        (id) => id.toLowerCase().endsWith(tail) || tail.endsWith(id.toLowerCase())
      );
    }
    if (idx < 0 && /^step_?(\d+)$/i.test(tail)) {
      idx = Math.min(pathLen - 1, Math.max(0, Number(RegExp.$1) - 1));
    }
    if (idx < 0) idx = Math.max(0, pathLen - 1);
    return {
      revealIndex: idx,
      showOptions: false,
      focusId: pathIds[idx] || m[1],
      answerPulse: false,
    };
  }
  // Scheme first (~70%), then options
  const pathProgress = Math.min(1, progress / 0.7);
  const idx = Math.min(pathLen - 1, Math.floor(pathProgress * Math.max(pathLen, 1)));
  return {
    revealIndex: Math.max(0, idx),
    showOptions: progress > 0.72,
    focusId: "",
    answerPulse: false,
  };
}

/** Shared SMILES drawer — also used on HOOK to relate the question figure. */
export function SmilesCanvas({
  smiles,
  width,
  height,
  dark = true,
}: {
  smiles: string;
  width: number;
  height: number;
  dark?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [handle] = useState(() => delayRender(`smiles-${smiles.slice(0, 24)}`));
  const uid = useId();

  useEffect(() => {
    let cancelled = false;
    const canvas = canvasRef.current;
    if (!canvas || !smiles) {
      continueRender(handle);
      return;
    }

    (async () => {
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const SmilesDrawer = require("smiles-drawer");
        const drawer = new SmilesDrawer.Drawer({
          width,
          height,
          bondThickness: 2.4,
          bondLength: 16,
          shortBondLength: 0.85,
          bondSpacing: 5,
          atomVisualization: "default",
          isomeric: true,
          compactDrawing: false,
          themes: {
            dark: {
              C: "#F8FAFC",
              O: "#F87171",
              N: "#38BDF8",
              S: "#FBBF24",
              P: "#A78BFA",
              F: "#4ADE80",
              Cl: "#4ADE80",
              Br: "#F472B6",
              I: "#F472B6",
              H: "#94A3B8",
              BACKGROUND: "#0B1220",
            },
          },
        });
        await new Promise<void>((resolve) => {
          SmilesDrawer.parse(
            smiles,
            (tree: unknown) => {
              if (cancelled) {
                resolve();
                return;
              }
              try {
                drawer.draw(tree, canvas, dark ? "dark" : "light", false);
              } catch {
                /* ignore */
              }
              resolve();
            },
            () => resolve()
          );
        });
      } catch {
        /* missing package */
      } finally {
        if (!cancelled) continueRender(handle);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [smiles, width, height, dark, handle, uid]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ width, height, display: "block", borderRadius: 8 }}
    />
  );
}

/**
 * Layout engine for TeachingDocument layout=scheme|mcq.
 * Driven only by stages/edges JSON — not a per-question component.
 */
export const SchemeEngine: React.FC<Props> = ({
  progress,
  title = "Organic structures",
  molecules = [],
  reactionSteps = [],
  correctOption,
  activeSee = "",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const options = useMemo(
    () =>
      molecules.filter(
        (m) =>
          m.role === "option" ||
          /^opt/i.test(m.id || "") ||
          /^\([A-D]\)/i.test(m.label || "")
      ),
    [molecules]
  );

  const pathMols = useMemo(() => {
    const roles = ["reactant", "intermediate", "product"];
    const ordered = roles.map((r) => molecules.filter((m) => m.role === r)).flat();
    const nonOpt =
      ordered.length >= 1
        ? ordered
        : molecules.filter(
            (m) =>
              m.role !== "option" &&
              !/^opt/i.test(m.id || "") &&
              !/^\([A-D]\)/i.test(m.label || "")
          );
    // ONLY draw real structures (SMILES) — never empty text boxes
    const withBonds = nonOpt.filter((m) => Boolean((m.smiles || "").trim()));
    if (withBonds.length >= 1) {
      // Prefer start + intermediates with SMILES + product; cap at 6
      // Never inject correct MCQ option into the path (spoils answer early)
      return withBonds.slice(0, 6);
    }
    // Incomplete SMILES: show start only — do NOT attach correct option as product
    const start = nonOpt[0];
    if (start?.smiles) return [start];
    return [];
  }, [molecules, options]);

  /** Reagent text between drawn molecules (collapse skipped label-only steps onto arrows). */
  const arrowReagents = useMemo(() => {
    if (pathMols.length <= 1) return [] as string[];
    if (pathMols.length === 2 && reactionSteps.length >= 1) {
      // start → product: put full multi-step reagents on one arrow
      return [
        reactionSteps
          .map((r) => r.reagents)
          .filter(Boolean)
          .join("\n") || "(steps)",
      ];
    }
    return pathMols.slice(0, -1).map((_, i) => reactionSteps[i]?.reagents || `(${i + 1})`);
  }, [pathMols, reactionSteps]);

  // Prefer question-like scheme whenever we have path OR multi reagents
  const useScheme =
    pathMols.length >= 2 || (pathMols.length >= 1 && reactionSteps.length >= 2);

  const pathIds = useMemo(
    () => pathMols.map((m, i) => String(m.id || `m${i}`)),
    [pathMols]
  );

  const reveal = useMemo(
    () => resolveReveal(activeSee, Math.max(pathMols.length, 1), progress, pathIds),
    [activeSee, pathMols.length, progress, pathIds]
  );

  const focusIdx = useMemo(() => {
    if (!reveal.focusId) return reveal.revealIndex;
    const i = pathMols.findIndex(
      (p) => String(p.id || "").toLowerCase() === reveal.focusId.toLowerCase()
    );
    return i >= 0 ? i : reveal.revealIndex;
  }, [reveal, pathMols]);

  // Never blank on HOOK frame 0 — scheme must be readable immediately
  const showMain = Math.max(
    0.95,
    interpolate(progress, [0, 0.08], [0.95, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );
  const showOpts = interpolate(progress, [0.7, 0.82], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const optsOpacity = reveal.showOptions ? Math.max(showOpts, 0.95) : showOpts;

  const correctLetter = String(correctOption || "")
    .replace(/[^A-Da-d]/g, "")
    .toUpperCase()
    .slice(0, 1);

  const drawnCount = Math.max(pathMols.length, 1);
  const molW = useScheme
    ? Math.min(260, Math.floor(1200 / drawnCount - 36))
    : 280;
  const molH = useScheme ? 160 : 180;
  const optionsWithBonds = options.filter((m) => Boolean((m.smiles || "").trim()));

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        gap: 10,
        padding: "2px 4px",
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      {/* Title lives in scene chrome / lesson header — do not duplicate here */}

      {useScheme ? (
        <>
          {/* Bond drawings only — no empty label boxes */}
          <div
            style={{
              flex: optionsWithBonds.length && reveal.showOptions ? "0 0 auto" : 1,
              minHeight: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              opacity: showMain,
              overflowX: "auto",
              paddingBottom: 4,
            }}
          >
            {pathMols.length === 0 ? (
              <div style={{ color: "#94A3B8", fontSize: 16 }}>
                Structures loading (SMILES required for bonds)…
              </div>
            ) : null}
            {pathMols.map((m, i) => {
              const visible = i <= focusIdx;
              const focused = i === focusIdx;
              const enter = spring({
                frame: Math.max(0, frame + Math.floor(fps * 0.25) - i * Math.floor(fps * 0.35)),
                fps,
                config: { damping: 14, stiffness: 120 },
              });
              const reagent = arrowReagents[i];
              const cardOpacity = visible ? Math.max(0.85, enter) : 0.25;
              return (
                <React.Fragment key={m.id || i}>
                  <div
                    style={{
                      width: molW,
                      flexShrink: 0,
                      background: "transparent",
                      border: "none",
                      padding: 4,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      opacity: cardOpacity,
                      transform: `scale(${visible ? interpolate(enter, [0, 1], [0.94, 1]) : 0.92})`,
                      outline: focused ? "2px solid #FBBF24" : "none",
                      outlineOffset: 4,
                      borderRadius: 8,
                    }}
                  >
                    {m.smiles ? (
                      <SmilesCanvas smiles={m.smiles} width={molW - 8} height={molH} />
                    ) : null}
                    <div
                      style={{
                        color: m.role === "product" ? "#86EFAC" : "#94A3B8",
                        fontWeight: 600,
                        fontSize: 12,
                        marginTop: 4,
                        textAlign: "center",
                        lineHeight: 1.3,
                        whiteSpace: "normal",
                        wordBreak: "break-word",
                        maxWidth: molW,
                      }}
                    >
                      {m.label || m.role || ""}
                    </div>
                  </div>
                  {i < pathMols.length - 1 ? (
                    <div
                      style={{
                        flexShrink: 0,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        minWidth: 88,
                        maxWidth: 160,
                        opacity: i < focusIdx ? 1 : 0.35,
                        padding: "0 4px",
                      }}
                    >
                      <div
                        style={{
                          color: "#FECACA",
                          fontSize: 11,
                          fontWeight: 700,
                          textAlign: "center",
                          lineHeight: 1.25,
                          maxHeight: 64,
                          overflow: "hidden",
                          whiteSpace: "pre-line",
                          marginBottom: 2,
                        }}
                      >
                        {reagent || `(${i + 1})`}
                      </div>
                      <div style={{ color: "#FBBF24", fontSize: 22, fontWeight: 900 }}>→</div>
                    </div>
                  ) : null}
                </React.Fragment>
              );
            })}
          </div>

          {/* Options — only structures with bonds; skip empty boxes */}
          {optionsWithBonds.length > 0 ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: `repeat(${Math.min(4, optionsWithBonds.length)}, 1fr)`,
                gap: 8,
                opacity: optsOpacity,
                minHeight: 0,
                flex: reveal.showOptions ? 1 : "0 0 auto",
                maxHeight: reveal.showOptions ? 220 : 0,
                overflow: "hidden",
              }}
            >
              {optionsWithBonds.slice(0, 4).map((m, i) => {
                const letter =
                  (m.label || "").match(/[A-D]/i)?.[0]?.toUpperCase() ||
                  String.fromCharCode(65 + i);
                // Mark correct ONLY on answer beat — never spoil early
                const isCorrect =
                  reveal.answerPulse &&
                  (m.correct || (correctLetter && letter === correctLetter));
                return (
                  <div
                    key={m.id || i}
                    style={{
                      background: "transparent",
                      border: isCorrect ? "2px solid #4ADE80" : "1px solid #334155",
                      borderRadius: 10,
                      padding: 4,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      minHeight: 0,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        alignSelf: "flex-start",
                        color: isCorrect ? "#86EFAC" : "#F8FAFC",
                        fontWeight: 800,
                        fontSize: 13,
                      }}
                    >
                      ({letter}){isCorrect ? " ✓" : ""}
                    </div>
                    <SmilesCanvas smiles={m.smiles!} width={170} height={110} />
                  </div>
                );
              })}
            </div>
          ) : null}
        </>
      ) : (
        /* Simple MCQ-only (no multi-step path) */
        <div
          style={{
            display: "grid",
            gridTemplateColumns: options.length ? "0.9fr 1.1fr" : "1fr",
            gap: 12,
            flex: 1,
            minHeight: 0,
            opacity: showMain,
          }}
        >
          {pathMols[0]?.smiles ? (
            <div
              style={{
                background: "transparent",
                border: "none",
                padding: 8,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
            >
              <SmilesCanvas smiles={pathMols[0].smiles} width={300} height={200} />
              <div style={{ color: "#94A3B8", fontWeight: 600, fontSize: 14, marginTop: 6 }}>
                {pathMols[0].label || "Structure"}
              </div>
            </div>
          ) : null}
          {optionsWithBonds.length > 0 ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gridTemplateRows: "1fr 1fr",
                gap: 8,
              }}
            >
              {optionsWithBonds.slice(0, 4).map((m, i) => {
                const letter =
                  (m.label || "").match(/[A-D]/i)?.[0]?.toUpperCase() ||
                  String.fromCharCode(65 + i);
                const isCorrect =
                  reveal.answerPulse &&
                  (m.correct || (correctLetter && letter === correctLetter));
                return (
                  <div
                    key={m.id || i}
                    style={{
                      background: "transparent",
                      border: isCorrect ? "2px solid #4ADE80" : "1px solid #334155",
                      borderRadius: 12,
                      padding: 6,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        alignSelf: "flex-start",
                        color: isCorrect ? "#86EFAC" : "#F8FAFC",
                        fontWeight: 800,
                        fontSize: 14,
                      }}
                    >
                      ({letter}){isCorrect ? " ✓" : ""}
                    </div>
                    <SmilesCanvas smiles={m.smiles!} width={180} height={110} />
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};
