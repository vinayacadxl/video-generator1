import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from "remotion";
import { SceneDirector } from "./director/SceneDirector";
import type { LessonVideoProps } from "./lib/types";

function resolveSceneAudio(
  timed?: { audioFile?: string | null; audioPath?: string | null }
): string | null {
  // Only attach when pipeline published a public audioFile (avoids missing-file crashes)
  if (timed?.audioFile) {
    return staticFile(String(timed.audioFile).replace(/^\/+/, ""));
  }
  return null;
}

export const LessonVideo: React.FC<LessonVideoProps> = ({ lesson, fps, timeline }) => {
  const { fps: compFps } = useVideoConfig();
  const rate = fps || compFps || 30;
  const scenes = lesson.scenes || [];

  let cursor = 0;
  const blocks = scenes.map((scene) => {
    const timed = timeline?.find((t) => t.sceneId === scene.id);
    const durationSec = timed?.duration || scene.duration || 6;
    const from = Math.round(cursor * rate);
    const frames = Math.max(1, Math.round(durationSec * rate));
    cursor += durationSec;
    return {
      scene,
      from,
      frames,
      durationSec,
      audioSrc: resolveSceneAudio(timed),
    };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#070B14" }}>
      {blocks.map(({ scene, from, frames, durationSec, audioSrc }) => (
        <Sequence key={scene.id} from={from} durationInFrames={frames}>
          {/* Audio only — visuals unchanged */}
          {audioSrc ? <Audio src={audioSrc} /> : null}
          <SceneDirector
            scene={{ ...scene, duration: durationSec }}
            solution={lesson.solution}
            title={lesson.video?.title}
            subject={lesson.video?.subject}
            topic={lesson.video?.topic}
            durationInSeconds={durationSec}
            fps={rate}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const defaultLessonProps: LessonVideoProps = {
  fps: 30,
  lesson: {
    video: {
      title: "Projectile Motion",
      subject: "Physics",
      topic: "projectile_motion",
      visualMode: "HYBRID",
      targetDuration: 60,
    },
    solution: {
      formula: "R = u² sin(2θ) / g",
      answer: "Maximum range at 45°",
      steps: ["Split velocity", "Apply gravity on uy", "Compute range"],
    },
    scenes: [
      {
        id: "scene_01",
        type: "HOOK",
        visualMode: "2D",
        duration: 6,
        narration: "Welcome students! Today we will understand projectile motion and calculate range.",
        visuals: ["projectile"],
        animations: ["launch_projectile"],
      },
      {
        id: "scene_02",
        type: "EXPLANATION",
        visualMode: "3D",
        duration: 10,
        narration: "Watch the 3D launch. Horizontal and vertical components create a parabola.",
        visuals: ["projectile", "trajectory"],
        animations: ["draw_trajectory", "show_vector"],
      },
      {
        id: "scene_03",
        type: "CALCULATION",
        visualMode: "2D",
        duration: 10,
        narration: "Using R = u squared sin 2θ over g, we substitute and solve for range.",
        actions: [{ action: "SHOW_EQUATION", equation: "R = u² sin(2θ) / g" }],
      },
      {
        id: "scene_04",
        type: "CONCLUSION",
        visualMode: "2D",
        duration: 6,
        narration: "In conclusion, the projectile follows a parabola and range peaks at 45 degrees.",
      },
    ],
  },
};
