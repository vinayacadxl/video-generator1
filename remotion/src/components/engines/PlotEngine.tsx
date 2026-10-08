import React, { useMemo } from "react";
import { interpolate } from "remotion";
import type { TeachingDocument } from "../../lib/teachingDocument";

type Props = {
  progress: number;
  doc: TeachingDocument;
  activeSee?: string;
};

const W = 1000;
const H = 420;
const PAD = { l: 70, r: 40, t: 40, b: 55 };

function scaleX(x: number, xMin: number, xMax: number) {
  return PAD.l + ((x - xMin) / Math.max(xMax - xMin, 1e-9)) * (W - PAD.l - PAD.r);
}
function scaleY(y: number, yMin: number, yMax: number) {
  return PAD.t + (1 - (y - yMin) / Math.max(yMax - yMin, 1e-9)) * (H - PAD.t - PAD.b);
}

export const PlotEngine: React.FC<Props> = ({ progress, doc, activeSee = "" }) => {
  const plot = doc.plot;
  const xMin = plot?.xMin ?? 0;
  const xMax = plot?.xMax ?? 10;
  const yMin = plot?.yMin ?? -10;
  const yMax = plot?.yMax ?? 10;

  const draw = interpolate(progress, [0.05, 0.55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const marksOn = interpolate(progress, [0.5, 0.75], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const paths = useMemo(() => {
    return (plot?.series || []).map((s) => {
      const pts = (s.points || []).filter((p) => p.length >= 2);
      if (pts.length < 2) return { id: s.id || "s", d: "", color: s.color || "#38BDF8", label: s.label || "" };
      const d = pts
        .map((p, i) => {
          const x = scaleX(p[0], xMin, xMax);
          const y = scaleY(p[1], yMin, yMax);
          return `${i === 0 ? "M" : "L"}${x},${y}`;
        })
        .join(" ");
      return { id: s.id || "s", d, color: s.color || "#38BDF8", label: s.label || "" };
    });
  }, [plot, xMin, xMax, yMin, yMax]);

  const focusMark = (activeSee || "").toLowerCase().replace(/^plot_/, "");

  if (!plot || (!(plot.series || []).length && !(plot.marks || []).length)) {
    return (
      <div style={{ color: "#94A3B8", padding: 16 }}>
        Plot data missing — TeachingDocument.plot.series required.
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", gap: 6, minHeight: 0 }}>
      <div style={{ color: "#F8FAFC", fontSize: 22, fontWeight: 800 }}>
        {(doc.title || plot.title || "Graph").slice(0, 56)}
      </div>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} style={{ flex: 1, minHeight: 0 }}>
        {/* axes */}
        <line x1={PAD.l} y1={H - PAD.b} x2={W - PAD.r} y2={H - PAD.b} stroke="#64748B" strokeWidth={2} />
        <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={H - PAD.b} stroke="#64748B" strokeWidth={2} />
        <text x={W / 2} y={H - 12} fill="#94A3B8" fontSize={14} textAnchor="middle">
          {plot.xLabel || "x"}
        </text>
        <text
          x={18}
          y={H / 2}
          fill="#94A3B8"
          fontSize={14}
          textAnchor="middle"
          transform={`rotate(-90 18 ${H / 2})`}
        >
          {plot.yLabel || "y"}
        </text>

        {paths.map((p) => {
          const len = 2000;
          return (
            <path
              key={p.id}
              d={p.d}
              fill="none"
              stroke={p.color}
              strokeWidth={3}
              strokeDasharray={len}
              strokeDashoffset={len * (1 - draw)}
              strokeLinecap="round"
            />
          );
        })}

        {(plot.marks || []).map((m, i) => {
          if (m.x == null || m.y == null) return null;
          const hot = focusMark && (m.id || "").toLowerCase() === focusMark;
          const cx = scaleX(m.x, xMin, xMax);
          const cy = scaleY(m.y, yMin, yMax);
          return (
            <g key={m.id || i} opacity={marksOn}>
              <circle cx={cx} cy={cy} r={hot ? 8 : 6} fill={hot ? "#FBBF24" : "#F87171"} />
              <text x={cx + 10} y={cy - 8} fill="#F8FAFC" fontSize={13} fontWeight={700}>
                {m.label || m.id}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
