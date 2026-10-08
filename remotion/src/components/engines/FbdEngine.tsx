import React, { useMemo } from "react";
import { interpolate, useCurrentFrame } from "remotion";

/** Data-driven exam figure — ONE renderer for ANY question diagram. */
export type DiagramElement = {
  id?: string;
  type: string;
  x?: number;
  y?: number;
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
  cx?: number;
  cy?: number;
  r?: number;
  width?: number;
  height?: number;
  rx?: number;
  points?: Array<[number, number] | number[]>;
  d?: string;
  text?: string;
  /** AI often puts caption here instead of text */
  label?: string;
  stroke?: string;
  fill?: string;
  strokeWidth?: number;
  dash?: string;
  fontSize?: number;
  fontWeight?: number | string;
  opacity?: number;
  reveal?: number;
  group?: string;
  animate?: string;
};

export type DiagramPhase = {
  id?: string;
  groups?: string[];
  see?: string;
  say?: string;
};

export type DiagramSpec = {
  title?: string;
  kind?: string;
  viewBox?: number[];
  elements?: DiagramElement[];
  phases?: DiagramPhase[];
  rebuildFromQuestion?: boolean;
};

type Props = {
  progress: number;
  spec?: DiagramSpec | null;
  /** Current visualBeat.see — maps to phase groups when possible */
  activeSee?: string;
};

/** Gemini sometimes returns points as a string / object — always coerce to [x,y][]. */
function normalizePoints(points: unknown): Array<[number, number]> {
  if (!points) return [];
  if (typeof points === "string") {
    const pairs = [...points.matchAll(/(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)/g)];
    return pairs.map((m) => [Number(m[1]), Number(m[2])] as [number, number]);
  }
  if (!Array.isArray(points)) return [];
  const out: Array<[number, number]> = [];
  for (const p of points) {
    if (Array.isArray(p) && p.length >= 2) {
      out.push([Number(p[0]), Number(p[1])]);
    } else if (p && typeof p === "object" && "x" in (p as object) && "y" in (p as object)) {
      const o = p as { x: number; y: number };
      out.push([Number(o.x), Number(o.y)]);
    }
  }
  return out.filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
}

function polyPoints(points?: DiagramElement["points"] | unknown): string {
  const pts = normalizePoints(points);
  if (!pts.length) return "";
  return pts.map((p) => `${p[0]},${p[1]}`).join(" ");
}

function pathLenEstimate(points?: DiagramElement["points"] | unknown): number {
  const pts = normalizePoints(points);
  if (pts.length < 2) return 1000;
  let len = 0;
  for (let i = 1; i < pts.length; i++) {
    const dx = pts[i][0] - pts[i - 1][0];
    const dy = pts[i][1] - pts[i - 1][1];
    len += Math.hypot(dx, dy);
  }
  return Math.max(len, 200);
}

function arrowHead(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  color: string,
  size = 10
) {
  const ang = Math.atan2(y2 - y1, x2 - x1);
  const a1 = ang + Math.PI * 0.85;
  const a2 = ang - Math.PI * 0.85;
  const p1 = `${x2},${y2}`;
  const p2 = `${x2 + size * Math.cos(a1)},${y2 + size * Math.sin(a1)}`;
  const p3 = `${x2 + size * Math.cos(a2)},${y2 + size * Math.sin(a2)}`;
  return <polygon points={`${p1} ${p2} ${p3}`} fill={color} />;
}

/** Circuit inductor / coil — AI often emits type=inductor which previously rendered as nothing. */
function inductorSymbol(
  x: number,
  y: number,
  width: number,
  height: number,
  stroke: string,
  sw: number,
  label?: string
) {
  const w = Math.max(width || 120, 60);
  const h = Math.max(height || 40, 24);
  const bumps = Math.max(3, Math.min(8, Math.round(w / 28)));
  const r = Math.min(h * 0.45, w / (bumps * 2.2));
  let d = `M ${x} ${y}`;
  for (let i = 0; i < bumps; i++) {
    const cx = x + r + i * 2 * r;
    d += ` A ${r} ${r} 0 0 1 ${cx + r} ${y}`;
  }
  const endX = x + bumps * 2 * r;
  return (
    <g>
      <path d={d} fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" />
      {/* lead stubs if width longer than coils */}
      {endX < x + w - 2 ? (
        <line x1={endX} y1={y} x2={x + w} y2={y} stroke={stroke} strokeWidth={sw} />
      ) : null}
      {label ? (
        <text
          x={x + w / 2}
          y={y - h * 0.55}
          fill={stroke}
          fontSize={Math.max(16, Math.min(28, h * 0.55))}
          fontWeight={800}
          textAnchor="middle"
        >
          {label}
        </text>
      ) : null}
    </g>
  );
}

function resistorSymbol(
  x: number,
  y: number,
  width: number,
  height: number,
  stroke: string,
  sw: number,
  label?: string
) {
  const w = Math.max(width || 100, 50);
  const h = Math.max(height || 28, 16);
  const zig = 6;
  const amp = h * 0.45;
  let d = `M ${x} ${y}`;
  const step = w / zig;
  for (let i = 0; i < zig; i++) {
    const nx = x + (i + 1) * step;
    const ny = y + (i % 2 === 0 ? -amp : amp);
    d += ` L ${nx} ${ny}`;
  }
  d += ` L ${x + w} ${y}`;
  return (
    <g>
      <path d={d} fill="none" stroke={stroke} strokeWidth={sw} strokeLinejoin="round" />
      {label ? (
        <text x={x + w / 2} y={y - h * 0.6} fill={stroke} fontSize={18} fontWeight={800} textAnchor="middle">
          {label}
        </text>
      ) : null}
    </g>
  );
}

/** Dark-background palette — never black/dark grey lines (invisible on navy UI). */
const LIGHT_STROKES = ["#38BDF8", "#F8FAFC", "#F87171", "#A78BFA", "#4ADE80", "#FBBF24", "#F472B6", "#22D3EE"];
const LIGHT_FILLS = ["#7DD3FC", "#F1F5F9", "#FCA5A5", "#C4B5FD", "#86EFAC", "#FDE68A", "#F9A8D4"];

function parseRgb(color?: string): { r: number; g: number; b: number; a: number } | null {
  if (!color) return null;
  const c = color.trim().toLowerCase();
  if (c === "none" || c === "transparent") return null;
  if (c === "black" || c === "#000" || c === "#000000") return { r: 0, g: 0, b: 0, a: 1 };
  if (c === "white" || c === "#fff" || c === "#ffffff") return { r: 255, g: 255, b: 255, a: 1 };
  const hex = c.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    let h = hex[1];
    if (h.length === 3) h = h.split("").map((ch) => ch + ch).join("");
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
      a: 1,
    };
  }
  const rgb = c.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/);
  if (rgb) {
    return {
      r: Number(rgb[1]),
      g: Number(rgb[2]),
      b: Number(rgb[3]),
      a: rgb[4] !== undefined ? Number(rgb[4]) : 1,
    };
  }
  return null;
}

function luminance(color?: string): number {
  const rgb = parseRgb(color);
  if (!rgb) return 1;
  return (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
}

function isDarkColor(color?: string): boolean {
  if (!color) return true;
  const c = color.trim().toLowerCase();
  if (c === "none" || c === "transparent") return false;
  if (["black", "#000", "#000000", "#111", "#111111", "#0f172a", "#020617", "#070b14"].includes(c)) {
    return true;
  }
  return luminance(c) < 0.45;
}

/** Map AI/black strokes to light blue / white / red / etc. for dark video background. */
function lightStroke(color: string | undefined, salt = 0): string {
  if (color && !isDarkColor(color)) return color;
  return LIGHT_STROKES[Math.abs(salt) % LIGHT_STROKES.length];
}

function lightFill(color: string | undefined, salt = 0, allowNone = true): string {
  if (!color || color === "none" || color === "transparent") {
    return allowNone ? "none" : LIGHT_FILLS[Math.abs(salt) % LIGHT_FILLS.length];
  }
  if (!isDarkColor(color)) return color;
  // Keep near-black fills as translucent dark panels only for rect backgrounds
  return LIGHT_FILLS[Math.abs(salt) % LIGHT_FILLS.length];
}

function lightTextFill(color: string | undefined, salt = 0): string {
  if (color && !isDarkColor(color)) return color;
  return LIGHT_STROKES[Math.abs(salt) % LIGHT_STROKES.length];
}

const HEADER_TOP = 78;
const CONTENT = { x: 36, y: HEADER_TOP, w: 1028, h: 400 };

function collectBounds(elements: DiagramElement[]) {
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  const hit = (x?: number, y?: number) => {
    if (typeof x !== "number" || typeof y !== "number" || Number.isNaN(x) || Number.isNaN(y)) return;
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  };
  for (const el of elements) {
    hit(el.x, el.y);
    hit(el.x1, el.y1);
    hit(el.x2, el.y2);
    hit(el.cx, el.cy);
    if (el.cx != null && el.r != null) {
      hit(el.cx - el.r, el.cy! - el.r);
      hit(el.cx + el.r, el.cy! + el.r);
    }
    if (el.x != null && el.width != null && el.y != null && el.height != null) {
      hit(el.x + el.width, el.y + el.height);
    }
    for (const p of normalizePoints(el.points)) hit(p[0], p[1]);
  }
  if (!Number.isFinite(minX)) {
    return { minX: 0, minY: 0, maxX: 1100, maxY: 520 };
  }
  return { minX, minY, maxX, maxY };
}

/** Fit all elements into content box below the title — kills header overlap + tiny corner clusters. */
function layoutElements(elements: DiagramElement[]): DiagramElement[] {
  if (!elements.length) return elements;
  const b = collectBounds(elements);
  const bw = Math.max(b.maxX - b.minX, 40);
  const bh = Math.max(b.maxY - b.minY, 40);
  const pad = 28;
  const scale = Math.min((CONTENT.w - pad * 2) / bw, (CONTENT.h - pad * 2) / bh, 1.35);
  const ox = CONTENT.x + pad + (CONTENT.w - pad * 2 - bw * scale) / 2;
  const oy = CONTENT.y + pad + (CONTENT.h - pad * 2 - bh * scale) / 2;
  const mapX = (x: number) => ox + (x - b.minX) * scale;
  const mapY = (y: number) => oy + (y - b.minY) * scale;

  return elements.map((el) => {
    const e = { ...el };
    if (e.x != null) e.x = mapX(e.x);
    if (e.y != null) e.y = mapY(e.y);
    if (e.x1 != null) e.x1 = mapX(e.x1);
    if (e.y1 != null) e.y1 = mapY(e.y1);
    if (e.x2 != null) e.x2 = mapX(e.x2);
    if (e.y2 != null) e.y2 = mapY(e.y2);
    if (e.cx != null) e.cx = mapX(e.cx);
    if (e.cy != null) e.cy = mapY(e.cy);
    if (e.r != null) e.r = Math.max(e.r * scale, 4);
    if (e.width != null) e.width = e.width * scale;
    if (e.height != null) e.height = e.height * scale;
    if (e.points) {
      e.points = normalizePoints(e.points).map(([x, y]) => [mapX(x), mapY(y)]);
    }
    if (e.type === "text" || e.type === "label") {
      e.fontSize = Math.max(Number(e.fontSize) || 18, 18) * Math.min(Math.max(scale, 0.9), 1.25);
      // Keep labels out of header band
      if (e.y != null && e.y < HEADER_TOP + 8) e.y = HEADER_TOP + 18;
      if (typeof e.text === "string" && e.text.length > 42) {
        e.text = e.text.slice(0, 40) + "…";
      }
    }
    return e;
  });
}

/** Layout engine for TeachingDocument layout=fbd|plot-fallback (typed primitives). */
export const FbdEngine: React.FC<Props> = ({ progress, spec, activeSee }) => {
  const frame = useCurrentFrame();
  const elements = useMemo(
    () => layoutElements(spec?.elements || []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(spec?.elements || [])]
  );
  const phases = spec?.phases || [];
  const viewBox = "0 0 1100 520";

  const maxReveal = useMemo(
    () => Math.max(0, ...elements.map((e) => Number(e.reveal ?? 0))),
    [elements]
  );

  // Cumulative phase teach: once a group appears it STAYS (better explanation)
  const activeGroups = useMemo(() => {
    if (!phases.length) return null;
    let phaseIdx = Math.min(
      phases.length - 1,
      Math.floor(progress * phases.length)
    );
    if (activeSee) {
      const want = activeSee.toLowerCase();
      const found = phases.findIndex((p) => {
        const see = String(p.see || p.id || "").toLowerCase();
        const id = String(p.id || "").toLowerCase();
        return (
          (see && (want.includes(see) || see.includes(want.replace(/^diagram_/, "")))) ||
          (id && want.includes(id))
        );
      });
      if (found >= 0) {
        phaseIdx = found;
      } else if (/mark|tip|formula|concept|highlight|meaning|current|aid/.test(want)) {
        // Concept beats: keep full figure visible while explaining meaning
        phaseIdx = phases.length - 1;
      }
    }
    const cum = new Set<string>();
    for (let i = 0; i <= phaseIdx; i++) {
      (phases[i].groups || []).forEach((g) => cum.add(String(g)));
    }
    // If phases don't cover an element's group, still show it late
    if (progress > 0.85) {
      elements.forEach((e) => {
        if (e.group) cum.add(String(e.group));
      });
    }
    return cum.size ? cum : null;
  }, [activeSee, phases, progress, elements]);

  const revealCap = interpolate(progress, [0.05, 0.92], [0, maxReveal + 0.01], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const pulse = 1 + 0.015 * Math.sin(frame / 10);

  if (!elements.length) {
    return (
      <div style={{ color: "#94A3B8", padding: 40, fontSize: 22 }}>
        No diagramSpec — figure missing
      </div>
    );
  }

  const title = (spec?.title || "Question figure").slice(0, 48);

  return (
    <svg
      width="100%"
      height="100%"
      viewBox={viewBox}
      preserveAspectRatio="xMidYMid meet"
      style={{ display: "block", overflow: "hidden" }}
    >
      {/* Reserved header — never draw figure content here */}
      <rect x={0} y={0} width={1100} height={HEADER_TOP - 6} fill="#070B14" />
      <text x={40} y={34} fill="#F8FAFC" fontSize={26} fontWeight={800}>
        {title}
      </text>
      {spec?.kind ? (
        <text x={900} y={34} fill="#64748B" fontSize={13} fontWeight={600} textAnchor="end">
          {String(spec.kind).slice(0, 16)}
        </text>
      ) : null}
      <line x1={36} y1={HEADER_TOP - 10} x2={1064} y2={HEADER_TOP - 10} stroke="#1E293B" strokeWidth={2} />

      {elements.map((el, idx) => {
        const rev = Number(el.reveal ?? 0);
        const groupOk = activeGroups ? activeGroups.has(String(el.group || "main")) : rev <= revealCap;
        if (!groupOk && activeGroups) {
          // still show earlier groups if phase includes them only — already handled
        }
        const showByProgress = rev <= revealCap + 0.05;
        const visible = activeGroups ? groupOk : showByProgress;
        if (!visible) return null;

        const local = interpolate(
          progress,
          [Math.max(0, rev / (maxReveal + 1) - 0.02), Math.min(1, (rev + 1) / (maxReveal + 1) + 0.15)],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );
        const op = (el.opacity ?? 1) * (el.animate === "fade" || !el.animate ? local : Math.max(local, 0.85));
        const salt = idx + String(el.id || "").length;
        const stroke = lightStroke(el.stroke, salt);
        const t = (el.type || "").toLowerCase();
        // Rect panels may keep a translucent dark fill; lines/curves must be bright
        const fill =
          t === "rect"
            ? el.fill && !isDarkColor(el.fill)
              ? el.fill
              : "rgba(15,23,42,0.55)"
            : t === "text" || t === "label"
              ? lightTextFill(el.fill, salt)
              : lightFill(el.fill, salt, t === "polyline" || t === "curve" || t === "path");
        const baseSw = Math.max(Number(el.strokeWidth) || 3.5, t === "polyline" || t === "curve" || t === "line" || t === "arrow" || t === "dashedline" ? 3.5 : 2.5);
        const sw = baseSw * (el.animate === "pulse" ? pulse : 1);
        const dash = el.dash;
        const key = el.id || `el-${idx}`;

        switch (t) {
          case "line":
            return (
              <line
                key={key}
                x1={el.x1}
                y1={el.y1}
                x2={el.x2}
                y2={el.y2}
                stroke={stroke}
                strokeWidth={sw}
                strokeDasharray={dash}
                opacity={op}
              />
            );
          case "dashedline":
            return (
              <line
                key={key}
                x1={el.x1}
                y1={el.y1}
                x2={el.x2}
                y2={el.y2}
                stroke={stroke}
                strokeWidth={sw}
                strokeDasharray={dash || "8 6"}
                opacity={op}
              />
            );
          case "arrow": {
            const x1 = el.x1 || 0;
            const y1 = el.y1 || 0;
            const x2 = el.x2 || 0;
            const y2 = el.y2 || 0;
            const alabel = el.label || el.text;
            return (
              <g key={key} opacity={op}>
                <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={stroke} strokeWidth={sw} strokeDasharray={dash} />
                {arrowHead(x1, y1, x2, y2, stroke)}
                {alabel ? (
                  <text
                    x={(x1 + x2) / 2 + 10}
                    y={(y1 + y2) / 2 - 8}
                    fill={stroke}
                    fontSize={18}
                    fontWeight={800}
                  >
                    {alabel}
                  </text>
                ) : null}
              </g>
            );
          }
          case "doublearrow": {
            const x1 = el.x1 || 0;
            const y1 = el.y1 || 0;
            const x2 = el.x2 || 0;
            const y2 = el.y2 || 0;
            return (
              <g key={key} opacity={op}>
                <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={stroke} strokeWidth={sw} strokeDasharray={dash} />
                {arrowHead(x1, y1, x2, y2, stroke, 8)}
                {arrowHead(x2, y2, x1, y1, stroke, 8)}
              </g>
            );
          }
          case "polyline":
          case "curve": {
            const pts = normalizePoints(el.points);
            if (pts.length < 2) return null;
            const plen = pathLenEstimate(pts);
            const draw = el.animate === "draw" ? local : 1;
            return (
              <polyline
                key={key}
                points={polyPoints(pts)}
                fill="none"
                stroke={stroke}
                strokeWidth={sw}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={`${plen}`}
                strokeDashoffset={plen * (1 - draw)}
                opacity={op}
              />
            );
          }
          case "path": {
            const plen = 1200;
            const draw = el.animate === "draw" ? local : 1;
            return (
              <path
                key={key}
                d={el.d || ""}
                fill={fill === "none" ? "none" : fill}
                stroke={stroke}
                strokeWidth={sw}
                strokeDasharray={`${plen}`}
                strokeDashoffset={plen * (1 - draw)}
                opacity={op}
              />
            );
          }
          case "circle":
            return (
              <circle
                key={key}
                cx={el.cx}
                cy={el.cy}
                r={(el.r || 10) * (el.animate === "pulse" ? pulse : 1)}
                fill={fill === "none" ? "#38BDF8" : fill}
                stroke={stroke}
                strokeWidth={sw}
                opacity={op}
              />
            );
          case "point":
            return (
              <circle
                key={key}
                cx={el.cx ?? el.x}
                cy={el.cy ?? el.y}
                r={el.r || 7}
                fill={fill === "none" ? "#F87171" : fill}
                stroke="#F8FAFC"
                strokeWidth={Math.max(sw, 2)}
                opacity={op}
              />
            );
          case "rect":
            return (
              <rect
                key={key}
                x={el.x}
                y={el.y}
                width={el.width}
                height={el.height}
                rx={el.rx || 8}
                fill={fill}
                stroke={stroke}
                strokeWidth={sw}
                opacity={op}
              />
            );
          case "text":
          case "label":
            return (
              <text
                key={key}
                x={el.x ?? el.cx}
                y={el.y ?? el.cy}
                fill={fill}
                fontSize={el.fontSize || 20}
                fontWeight={el.fontWeight || 800}
                opacity={op}
              >
                {el.text || el.label || ""}
              </text>
            );
          case "inductor":
          case "coil":
            return (
              <g key={key} opacity={op}>
                {inductorSymbol(
                  Number(el.x ?? el.x1 ?? 0),
                  Number(el.y ?? el.y1 ?? 0),
                  Number(el.width ?? (el.x2 != null && el.x1 != null ? el.x2 - el.x1 : 160)),
                  Number(el.height ?? 48),
                  stroke,
                  sw,
                  el.label || el.text
                )}
              </g>
            );
          case "resistor":
            return (
              <g key={key} opacity={op}>
                {resistorSymbol(
                  Number(el.x ?? 0),
                  Number(el.y ?? 0),
                  Number(el.width ?? 120),
                  Number(el.height ?? 32),
                  stroke,
                  sw,
                  el.label || el.text
                )}
              </g>
            );
          case "capacitor": {
            const cx = Number(el.x ?? el.cx ?? 0);
            const cy = Number(el.y ?? el.cy ?? 0);
            const hh = Math.max(Number(el.height ?? 40), 24);
            const gap = 10;
            return (
              <g key={key} opacity={op}>
                <line x1={cx - gap} y1={cy - hh / 2} x2={cx - gap} y2={cy + hh / 2} stroke={stroke} strokeWidth={sw} />
                <line x1={cx + gap} y1={cy - hh / 2} x2={cx + gap} y2={cy + hh / 2} stroke={stroke} strokeWidth={sw} />
                {(el.label || el.text) && (
                  <text x={cx} y={cy - hh / 2 - 8} fill={stroke} fontSize={18} fontWeight={800} textAnchor="middle">
                    {el.label || el.text}
                  </text>
                )}
              </g>
            );
          }
          case "battery":
          case "cell": {
            const bx = Number(el.x ?? 0);
            const by = Number(el.y ?? 0);
            const hh = Math.max(Number(el.height ?? 36), 20);
            return (
              <g key={key} opacity={op}>
                <line x1={bx} y1={by - hh / 2} x2={bx} y2={by + hh / 2} stroke={stroke} strokeWidth={sw * 1.4} />
                <line
                  x1={bx + 14}
                  y1={by - hh * 0.28}
                  x2={bx + 14}
                  y2={by + hh * 0.28}
                  stroke={stroke}
                  strokeWidth={sw * 0.7}
                />
                {(el.label || el.text) && (
                  <text x={bx + 7} y={by - hh / 2 - 8} fill={stroke} fontSize={16} fontWeight={800} textAnchor="middle">
                    {el.label || el.text}
                  </text>
                )}
              </g>
            );
          }
          default:
            // Unknown AI types: draw a labeled placeholder so the figure is never empty
            if (el.x != null && el.y != null && (el.width || el.height || el.label || el.text)) {
              const pw = Number(el.width ?? 80);
              const ph = Number(el.height ?? 36);
              return (
                <g key={key} opacity={op}>
                  <rect
                    x={el.x}
                    y={(el.y || 0) - ph / 2}
                    width={pw}
                    height={ph}
                    rx={6}
                    fill="rgba(15,23,42,0.7)"
                    stroke={stroke}
                    strokeWidth={sw}
                  />
                  <text
                    x={(el.x || 0) + pw / 2}
                    y={(el.y || 0) + 5}
                    fill={stroke}
                    fontSize={14}
                    fontWeight={700}
                    textAnchor="middle"
                  >
                    {(el.label || el.text || el.type || "?").slice(0, 18)}
                  </text>
                </g>
              );
            }
            return null;
        }
      })}
    </svg>
  );
};
