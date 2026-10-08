import React from "react";
import { interpolate } from "remotion";

export type BioPart = { id?: string; label?: string };
export type BioFigure = {
  type?: string;
  title?: string;
  highlight?: string;
  parts?: BioPart[];
};

type Props = {
  progress: number;
  figure?: BioFigure | null;
  activeSee?: string;
};

const COLORS = {
  stroke: "#38BDF8",
  fill: "rgba(56,189,248,0.2)",
  accent: "#F87171",
  label: "#F8FAFC",
  soft: "#A78BFA",
  green: "#4ADE80",
  yellow: "#FBBF24",
};

function Flower({ highlight, progress }: { highlight?: string; progress: number }) {
  const cx = 400;
  const cy = 260;
  const petals = 5;
  const reveal = interpolate(progress, [0, 0.4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <g opacity={reveal}>
      {Array.from({ length: petals }).map((_, i) => {
        const a = (i / petals) * Math.PI * 2 - Math.PI / 2;
        const px = cx + Math.cos(a) * 70;
        const py = cy + Math.sin(a) * 70;
        const on = highlight === "petal";
        return (
          <ellipse
            key={i}
            cx={px}
            cy={py}
            rx={48}
            ry={28}
            transform={`rotate(${(a * 180) / Math.PI} ${px} ${py})`}
            fill={on ? "rgba(248,113,113,0.45)" : "rgba(244,114,182,0.35)"}
            stroke={on ? COLORS.accent : "#F9A8D4"}
            strokeWidth={3}
          />
        );
      })}
      <circle cx={cx} cy={cy} r={36} fill={COLORS.yellow} stroke="#FDE68A" strokeWidth={3} />
      <circle
        cx={cx}
        cy={cy - 8}
        r={8}
        fill={highlight === "stigma" ? COLORS.accent : "#F8FAFC"}
        stroke="#fff"
        strokeWidth={2}
      />
      <line x1={cx} y1={cy + 36} x2={cx} y2={cy + 140} stroke={COLORS.green} strokeWidth={8} />
      <ellipse cx={cx - 50} cy={cy + 100} rx={40} ry={16} fill="rgba(74,222,128,0.5)" stroke={COLORS.green} strokeWidth={2} />
      <ellipse cx={cx + 50} cy={cy + 110} rx={40} ry={16} fill="rgba(74,222,128,0.5)" stroke={COLORS.green} strokeWidth={2} />
      <circle
        cx={cx}
        cy={cy + 155}
        r={18}
        fill={highlight === "ovary" ? COLORS.accent : "rgba(167,139,250,0.5)"}
        stroke={COLORS.soft}
        strokeWidth={3}
      />
      <g>
        <line x1={cx + 30} y1={cy - 10} x2={cx + 90} y2={cy - 50} stroke="#FDE68A" strokeWidth={3} />
        <circle
          cx={cx + 95}
          cy={cy - 55}
          r={12}
          fill={highlight === "anther" ? COLORS.accent : "#FBBF24"}
          stroke="#fff"
          strokeWidth={2}
        />
      </g>
    </g>
  );
}

function Amoeba({ highlight, progress }: { highlight?: string; progress: number }) {
  const reveal = interpolate(progress, [0, 0.35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const blob =
    "M 320 220 C 260 160, 420 120, 500 170 C 580 210, 620 280, 560 340 C 500 400, 360 390, 300 330 C 250 280, 280 240, 320 220 Z";
  return (
    <g opacity={reveal}>
      <path
        d={blob}
        fill="rgba(56,189,248,0.25)"
        stroke={highlight === "pseudopodia" ? COLORS.accent : COLORS.stroke}
        strokeWidth={4}
      />
      {/* pseudopodia bumps */}
      <ellipse cx={250} cy={200} rx={40} ry={22} fill="rgba(56,189,248,0.3)" stroke={COLORS.stroke} strokeWidth={3} />
      <ellipse cx={580} cy={250} rx={45} ry={24} fill="rgba(56,189,248,0.3)" stroke={COLORS.stroke} strokeWidth={3} />
      <circle
        cx={420}
        cy={250}
        r={28}
        fill={highlight === "nucleus" ? COLORS.accent : COLORS.soft}
        stroke="#fff"
        strokeWidth={3}
      />
      <circle
        cx={480}
        cy={310}
        r={18}
        fill={highlight === "food_vacuole" ? COLORS.yellow : "rgba(251,191,36,0.5)"}
        stroke="#FDE68A"
        strokeWidth={2}
      />
      <circle
        cx={360}
        cy={300}
        r={14}
        fill={highlight === "contractile" ? COLORS.accent : "rgba(125,211,252,0.6)"}
        stroke="#7DD3FC"
        strokeWidth={2}
      />
    </g>
  );
}

function AnimalCell({ highlight, progress }: { highlight?: string; progress: number }) {
  const reveal = interpolate(progress, [0, 0.35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <g opacity={reveal}>
      <ellipse
        cx={420}
        cy={270}
        rx={200}
        ry={150}
        fill="rgba(56,189,248,0.12)"
        stroke={highlight === "membrane" ? COLORS.accent : COLORS.stroke}
        strokeWidth={4}
      />
      <circle
        cx={400}
        cy={260}
        r={55}
        fill={highlight === "nucleus" ? "rgba(248,113,113,0.45)" : "rgba(167,139,250,0.35)"}
        stroke={highlight === "nucleus" ? COLORS.accent : COLORS.soft}
        strokeWidth={3}
      />
      <ellipse
        cx={520}
        cy={300}
        rx={35}
        ry={20}
        fill={highlight === "mitochondria" ? COLORS.accent : "rgba(251,191,36,0.45)"}
        stroke={COLORS.yellow}
        strokeWidth={2}
      />
      <ellipse cx={300} cy={300} rx={30} ry={18} fill="rgba(251,191,36,0.35)" stroke={COLORS.yellow} strokeWidth={2} />
    </g>
  );
}

function PlantCell({ highlight, progress }: { highlight?: string; progress: number }) {
  const reveal = interpolate(progress, [0, 0.35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <g opacity={reveal}>
      <rect
        x={200}
        y={130}
        width={440}
        height={280}
        rx={18}
        fill="rgba(74,222,128,0.1)"
        stroke={highlight === "cell_wall" ? COLORS.accent : COLORS.green}
        strokeWidth={5}
      />
      <rect
        x={220}
        y={150}
        width={400}
        height={240}
        rx={14}
        fill="rgba(56,189,248,0.08)"
        stroke={COLORS.stroke}
        strokeWidth={3}
      />
      <ellipse
        cx={480}
        cy={260}
        rx={70}
        ry={90}
        fill={highlight === "vacuole" ? "rgba(125,211,252,0.5)" : "rgba(125,211,252,0.25)"}
        stroke="#7DD3FC"
        strokeWidth={3}
      />
      <ellipse
        cx={300}
        cy={220}
        rx={40}
        ry={22}
        fill={highlight === "chloroplast" ? COLORS.accent : "rgba(74,222,128,0.55)"}
        stroke={COLORS.green}
        strokeWidth={2}
      />
      <circle
        cx={340}
        cy={300}
        r={36}
        fill={highlight === "nucleus" ? "rgba(248,113,113,0.4)" : "rgba(167,139,250,0.35)"}
        stroke={COLORS.soft}
        strokeWidth={3}
      />
    </g>
  );
}

function Neuron({ highlight, progress }: { highlight?: string; progress: number }) {
  const reveal = interpolate(progress, [0, 0.35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <g opacity={reveal}>
      <circle
        cx={280}
        cy={260}
        r={50}
        fill={highlight === "soma" ? "rgba(248,113,113,0.4)" : "rgba(56,189,248,0.25)"}
        stroke={COLORS.stroke}
        strokeWidth={4}
      />
      {[ -50, -20, 20, 50].map((dy, i) => (
        <line
          key={i}
          x1={240}
          y1={260}
          x2={160}
          y2={260 + dy}
          stroke={highlight === "dendrite" ? COLORS.accent : COLORS.soft}
          strokeWidth={4}
        />
      ))}
      <line
        x1={330}
        y1={260}
        x2={700}
        y2={260}
        stroke={highlight === "axon" ? COLORS.accent : COLORS.yellow}
        strokeWidth={8}
        strokeLinecap="round"
      />
      <polygon points="700,260 670,245 670,275" fill={highlight === "axon" ? COLORS.accent : COLORS.yellow} />
    </g>
  );
}

function Nephron({ highlight, progress }: { highlight?: string; progress: number }) {
  const reveal = interpolate(progress, [0, 0.35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <g opacity={reveal}>
      <circle
        cx={320}
        cy={220}
        r={55}
        fill="none"
        stroke={highlight === "bowman" ? COLORS.accent : COLORS.stroke}
        strokeWidth={4}
      />
      <circle
        cx={320}
        cy={220}
        r={28}
        fill={highlight === "glomerulus" ? "rgba(248,113,113,0.45)" : "rgba(244,114,182,0.35)"}
        stroke="#F9A8D4"
        strokeWidth={3}
      />
      <path
        d="M 370 240 C 450 260, 480 320, 520 300 C 580 270, 620 340, 700 320"
        fill="none"
        stroke={highlight === "tubule" ? COLORS.accent : COLORS.yellow}
        strokeWidth={10}
        strokeLinecap="round"
      />
    </g>
  );
}

function CustomBlob({ progress }: { progress: number }) {
  const reveal = interpolate(progress, [0, 0.4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <g opacity={reveal}>
      <ellipse cx={420} cy={270} rx={180} ry={120} fill="rgba(56,189,248,0.2)" stroke={COLORS.stroke} strokeWidth={4} />
      <text x={360} y={275} fill={COLORS.label} fontSize={22} fontWeight={800}>
        Structure
      </text>
    </g>
  );
}

/** Parametric biology diagrams — flower, amoeba, cell, etc. (no question photo). */
/** Layout engine for TeachingDocument layout=figure (parametric bio templates). */
export const FigureEngine: React.FC<Props> = ({ progress, figure, activeSee }) => {
  const type = String(figure?.type || "custom").toLowerCase().replace(/\s+/g, "_");
  const parts = figure?.parts || [];
  let highlight = figure?.highlight || parts[0]?.id;
  if (activeSee) {
    const hit = parts.find((p) => activeSee.toLowerCase().includes(String(p.id || "").toLowerCase()) || activeSee.toLowerCase().includes(String(p.label || "").toLowerCase()));
    if (hit?.id) highlight = hit.id;
  }

  const labelReveal = interpolate(progress, [0.35, 0.85], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <svg width="100%" height="100%" viewBox="0 0 1000 520" style={{ display: "block" }}>
      <text x={40} y={40} fill="#F8FAFC" fontSize={26} fontWeight={800}>
        {figure?.title || "Biology diagram"}
      </text>
      <text x={40} y={68} fill="#94A3B8" fontSize={15} fontWeight={600}>
        {type.replace(/_/g, " ")} · labeled teaching figure
      </text>

      {type === "flower" ? <Flower highlight={highlight} progress={progress} /> : null}
      {type === "amoeba" ? <Amoeba highlight={highlight} progress={progress} /> : null}
      {type === "animal_cell" ? <AnimalCell highlight={highlight} progress={progress} /> : null}
      {type === "plant_cell" ? <PlantCell highlight={highlight} progress={progress} /> : null}
      {type === "neuron" ? <Neuron highlight={highlight} progress={progress} /> : null}
      {type === "nephron" ? <Nephron highlight={highlight} progress={progress} /> : null}
      {!["flower", "amoeba", "animal_cell", "plant_cell", "neuron", "nephron"].includes(type) ? (
        <CustomBlob progress={progress} />
      ) : null}

      {/* Legend */}
      <g opacity={labelReveal}>
        {parts.slice(0, 6).map((p, i) => {
          const on = p.id === highlight;
          return (
            <g key={p.id || i}>
              <rect
                x={720}
                y={100 + i * 52}
                width={240}
                height={42}
                rx={10}
                fill={on ? "rgba(248,113,113,0.25)" : "rgba(15,23,42,0.85)"}
                stroke={on ? COLORS.accent : "#38BDF8"}
                strokeWidth={on ? 3 : 1.5}
              />
              <text x={738} y={128 + i * 52} fill="#F8FAFC" fontSize={18} fontWeight={700}>
                {p.label || p.id}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
};
