import React from "react";
import { AbsoluteFill } from "remotion";
import type { SceneClipProps } from "../lib/types";
import { TwoDScene } from "../engines/TwoDScene";
import { ThreeDScene } from "../engines/ThreeDScene";

type LessonSceneExt = SceneClipProps["scene"] & {
  force3D?: boolean;
  engine?: string;
  boardLayout?: string;
};

/** Data-driven: any rebuilt exam figure stays on Remotion 2D. */
function hasQuestionFigure(props: SceneClipProps): boolean {
  return (props.solution?.diagramSpec?.elements?.length || 0) >= 2;
}

function wantsSpatialThreeJs(props: SceneClipProps): boolean {
  const sim = String(props.solution?.simulation?.type || "").toLowerCase();
  return ["projectile", "rocket", "vehicle", "earth"].includes(sim);
}

/**
 * Scene Director — routes by DATA, not topic keywords.
 * diagramSpec present → 2D figure. Explicit spatial sim → 3D. Else scene.visualMode.
 */
function wantsThreeJs(props: SceneClipProps): boolean {
  const scene = props.scene as LessonSceneExt;
  const layout = String(scene?.boardLayout || "").toLowerCase();
  if (layout && layout !== "fbd") return false;

  if (hasQuestionFigure(props) && !wantsSpatialThreeJs(props)) {
    return false;
  }

  // Only real spatial sims get Three.js — never fall back to projectile for fluid/etc.
  if (scene?.force3D || String(scene?.engine || "").toLowerCase() === "threejs") {
    return wantsSpatialThreeJs(props);
  }

  const mode = (scene?.visualMode || "2D").toUpperCase();
  if (mode !== "3D") return false;
  return wantsSpatialThreeJs(props);
}

export const SceneDirector: React.FC<SceneClipProps> = (props) => {
  const use3D = wantsThreeJs(props);

  return (
    <AbsoluteFill style={{ backgroundColor: "#070B14" }}>
      {use3D ? <ThreeDScene {...props} /> : <TwoDScene {...props} />}
    </AbsoluteFill>
  );
};
