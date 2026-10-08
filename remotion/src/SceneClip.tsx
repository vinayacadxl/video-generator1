import React from "react";
import { AbsoluteFill } from "remotion";
import { SceneDirector } from "./director/SceneDirector";
import type { SceneClipProps } from "./lib/types";

export const SceneClip: React.FC<SceneClipProps> = (props) => {
  return (
    <AbsoluteFill>
      <SceneDirector {...props} />
    </AbsoluteFill>
  );
};

export const defaultSceneClipProps: SceneClipProps = {
  fps: 30,
  durationInSeconds: 8,
  title: "Projectile Motion",
  subject: "Physics",
  topic: "Projectile Motion",
  solution: {
    formula: "R = u² sin(2θ) / g",
    answer: "R = u² / g (for θ = 45°)",
    steps: [
      "Resolve velocity into ux = u cosθ and uy = u sinθ",
      "Time of flight T = 2u sinθ / g",
      "Range R = ux · T = u² sin(2θ) / g",
    ],
  },
  scene: {
    id: "scene_demo",
    type: "HOOK",
    visualMode: "2D",
    duration: 8,
    narration:
      "An object is thrown at an angle. Watch the projectile follow a parabolic path under gravity.",
    visuals: ["projectile", "trajectory"],
    animations: ["launch_projectile", "draw_trajectory"],
    actions: [{ action: "SHOW_EQUATION", equation: "R = u² sin(2θ) / g" }],
  },
};
