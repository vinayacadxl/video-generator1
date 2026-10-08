import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { formatMath } from "../lib/formatMath";

export const FadeIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
  duration?: number;
}> = ({ children, delay = 0, duration = 20 }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [delay, delay + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <div style={{ opacity }}>{children}</div>;
};

export const PopIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
}> = ({ children, delay = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = spring({
    frame: Math.max(0, frame - delay),
    fps,
    config: { damping: 14, stiffness: 120 },
  });
  return <div style={{ transform: `scale(${Math.max(scale, 0.01)})` }}>{children}</div>;
};

export const KineticText: React.FC<{
  text: string;
  delay?: number;
  style?: React.CSSProperties;
}> = ({ text, delay = 0, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({
    frame: Math.max(0, frame - delay),
    fps,
    config: { damping: 200 },
  });
  const y = interpolate(progress, [0, 1], [20, 0]);
  const opacity = interpolate(progress, [0, 1], [0, 1]);
  return (
    <div
      style={{
        transform: `translateY(${y}px)`,
        opacity,
        overflow: "visible",
        whiteSpace: "normal",
        wordBreak: "break-word",
        ...style,
      }}
    >
      {text}
    </div>
  );
};

export const EquationCard: React.FC<{
  equation: string;
  label?: string;
  delay?: number;
  highlight?: boolean;
  compact?: boolean;
}> = ({ equation, label, delay = 0, highlight, compact }) => {
  const pretty = formatMath(equation);
  return (
    <FadeIn delay={delay}>
      <div
        style={{
          background: highlight
            ? "linear-gradient(135deg, rgba(34,197,94,0.2), rgba(14,165,233,0.16))"
            : "rgba(15, 23, 42, 0.92)",
          border: highlight
            ? "1px solid rgba(74, 222, 128, 0.55)"
            : "1px solid rgba(148, 163, 184, 0.28)",
          borderRadius: 16,
          padding: compact ? "14px 18px" : "16px 20px",
          boxShadow: "0 14px 36px rgba(0,0,0,0.35)",
          maxWidth: "100%",
          overflow: "hidden",
        }}
      >
        {label ? (
          <div
            style={{
              color: "#94A3B8",
              fontSize: 14,
              marginBottom: 6,
              letterSpacing: 1.1,
              textTransform: "uppercase",
              fontWeight: 700,
            }}
          >
            {label}
          </div>
        ) : null}
        <div
          style={{
            color: "#F8FAFC",
            fontSize: compact
              ? pretty.length > 220
                ? 18
                : pretty.length > 120
                  ? 20
                  : 24
              : pretty.length > 180
                ? 22
                : 30,
            lineHeight: 1.4,
            fontFamily: "Georgia, 'Times New Roman', serif",
            fontWeight: 600,
            whiteSpace: "normal",
            wordBreak: "break-word",
            overflowWrap: "anywhere",
            overflow: "visible",
          }}
        >
          {pretty}
        </div>
      </div>
    </FadeIn>
  );
};

export const Arrow2D: React.FC<{
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color?: string;
  label?: string;
  delay?: number;
}> = ({ x1, y1, x2, y2, color = "#38BDF8", label, delay = 0 }) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [delay, delay + 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const mx = x1 + (x2 - x1) * progress;
  const my = y1 + (y2 - y1) * progress;
  const id = `arrow-${color.replace("#", "")}`;
  return (
    <svg
      width="100%"
      height="100%"
      style={{ position: "absolute", inset: 0, overflow: "visible", pointerEvents: "none" }}
    >
      <defs>
        <marker id={id} markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
          <path d="M0,0 L0,6 L9,3 z" fill={color} />
        </marker>
      </defs>
      <line
        x1={x1}
        y1={y1}
        x2={mx}
        y2={my}
        stroke={color}
        strokeWidth={4}
        markerEnd={`url(#${id})`}
      />
      {label && progress > 0.85 ? (
        <text x={x2 + 10} y={y2 - 10} fill={color} fontSize={20} fontWeight={700}>
          {label}
        </text>
      ) : null}
    </svg>
  );
};

export const SceneChrome: React.FC<{
  subject?: string;
  topic?: string;
  sceneType?: string;
  children: React.ReactNode;
}> = ({ subject, topic, sceneType, children }) => {
  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(1200px 700px at 18% 12%, #12203a 0%, #070B14 55%, #05070d 100%)",
        fontFamily:
          "Segoe UI, ui-sans-serif, system-ui, -apple-system, sans-serif",
        color: "#E2E8F0",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 28,
          left: 40,
          right: 40,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          zIndex: 5,
        }}
      >
        <div
          style={{
            fontSize: 15,
            letterSpacing: 1.6,
            color: "#7DD3FC",
            textTransform: "uppercase",
            fontWeight: 700,
          }}
        >
          {subject || topic || "Lesson"}
        </div>
        <div style={{ color: "#94A3B8", fontSize: 15 }}>
          {sceneType || "SCENE"}
          {topic && topic !== subject ? ` · ${topic}` : ""}
        </div>
      </div>
      {children}
    </AbsoluteFill>
  );
};
