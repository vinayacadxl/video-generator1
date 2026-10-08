import React from "react";
import { Composition, staticFile } from "remotion";
import { LessonVideo, defaultLessonProps } from "./LessonVideo";
import { SceneClip, defaultSceneClipProps } from "./SceneClip";
import type { LessonVideoProps, SceneClipProps } from "./lib/types";

const FPS = 30;

function sceneFrames(props: SceneClipProps) {
  return Math.max(1, Math.round((props.durationInSeconds || 6) * (props.fps || FPS)));
}

function lessonFrames(props: LessonVideoProps) {
  const fps = props.fps || FPS;
  if (props.timeline?.length) {
    const last = props.timeline[props.timeline.length - 1] as {
      startTime?: number;
      duration?: number;
    };
    const start = last.startTime || 0;
    const dur = last.duration || 6;
    return Math.max(1, Math.round((start + dur) * fps));
  }
  const total = (props.lesson?.scenes || []).reduce(
    (sum, s) => sum + (s.duration || 6),
    0
  );
  return Math.max(1, Math.round(total * fps));
}

async function loadLiveLessonProps(fallback: LessonVideoProps): Promise<LessonVideoProps> {
  try {
    const res = await fetch(staticFile("live-lesson.json"));
    if (!res.ok) return fallback;
    const live = await res.json();
    if (!live?.lesson) return fallback;
    return {
      ...fallback,
      ...live,
      lesson: live.lesson,
      fps: live.fps || fallback.fps || FPS,
      timeline: live.timeline || [],
    };
  } catch {
    return fallback;
  }
}

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SceneClip"
        component={SceneClip}
        durationInFrames={sceneFrames(defaultSceneClipProps)}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={defaultSceneClipProps}
        calculateMetadata={async ({ props }) => ({
          durationInFrames: sceneFrames(props as SceneClipProps),
          fps: (props as SceneClipProps).fps || FPS,
        })}
      />
      <Composition
        id="LessonVideo"
        component={LessonVideo}
        durationInFrames={lessonFrames(defaultLessonProps)}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={defaultLessonProps}
        calculateMetadata={async ({ props }) => {
          const next = await loadLiveLessonProps(props as LessonVideoProps);
          return {
            props: next,
            durationInFrames: lessonFrames(next),
            fps: next.fps || FPS,
          };
        }}
      />
    </>
  );
};
