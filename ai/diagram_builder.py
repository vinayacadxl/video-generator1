"""Generic question-figure → diagramSpec (JSON) for Remotion GenericDiagram.

Architecture (do NOT add a new React file per question):
  Question image/text → Gemini extracts diagramSpec → GenericDiagram.tsx animates it.

diagramSpec can describe ANY exam figure: graphs, free-body, circuits, geometry,
molecules (as shapes), PE curves, cavities, etc.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .gemini import GeminiClient


DIAGRAM_EXTRACT_PROMPT = """You rebuild the QUESTION FIGURE as a teachable animated diagram.

Pipeline: Question image/text → YOUR diagramSpec JSON → Remotion GenericDiagram (ONE renderer for ALL figures).

CRITICAL:
1. Look at the attached image(s) if present. Rebuild WHATEVER figure is there — graph, FBD, circuit,
   geometry, molecule sketch, PE curve, sphere/cavity, rays, etc. Do NOT invent a different figure.
2. Do NOT write React/Remotion code. Only JSON matching the schema below.
3. Coordinates use viewBox 0..1100 x 0..520 (x right, y DOWN). Keep margins ~40px.
4. Put animation order in element.reveal (0 = first, then 1, 2, ...). Group related parts with "group".
5. Prefer vector primitives: axes, curve/polyline, line, dashedLine, arrow, circle, rect, text, point, doubleArrow.
6. For PE vs distance graphs: axes + polyline/curve + E0 dashed horizontal + d0 dashed vertical + atom pair + labels.
7. For organic structures: prefer returning atoms/bonds style via elements type "circle"+"line"+"text", OR leave
   structure to structureDiagram — still fill diagramSpec if the figure is a graph/schematic.
8. phases[] drive teaching beats (see tags the planner will use).
9. COLORS ARE CRITICAL — video background is DARK navy/black.
   NEVER use black, #000, #111, dark grey, or near-black for stroke/fill/text.
   ALWAYS use LIGHT colors: #38BDF8 (light blue), #F8FAFC (white), #F87171 (red),
   #A78BFA (violet), #4ADE80 (green), #FBBF24 (yellow), #F472B6 (pink).
   strokeWidth for axes/lines/curves: at least 3.5.

Return ONLY JSON:
{
  "title": "<short figure title>",
  "kind": "graph|schematic|fbd|circuit|geometry|molecule|mixed",
  "viewBox": [0, 0, 1100, 520],
  "rebuildFromQuestion": true,
  "elements": [
    {
      "id": "x_axis",
      "type": "arrow",
      "x1": 120, "y1": 400, "x2": 900, "y2": 400,
      "stroke": "#64748B", "strokeWidth": 3,
      "reveal": 0, "group": "axes", "animate": "fade"
    },
    {
      "id": "curve",
      "type": "polyline",
      "points": [[140,120],[200,300],[400,380],[700,300],[880,220]],
      "stroke": "#F8FAFC", "strokeWidth": 3.5, "fill": "none",
      "reveal": 1, "group": "curve", "animate": "draw"
    },
    {
      "id": "label_E0",
      "type": "text",
      "x": 140, "y": 260, "text": "E0",
      "fill": "#F9A8D4", "fontSize": 22, "fontWeight": 800,
      "reveal": 3, "group": "markers", "animate": "fade"
    }
  ],
  "phases": [
    {"id": "axes", "groups": ["axes"], "see": "diagram_axes", "say": "Pehle figure ke axes."},
    {"id": "main", "groups": ["axes","curve"], "see": "diagram_main", "say": "Ab main curve/shape."},
    {"id": "marks", "groups": ["axes","curve","markers"], "see": "diagram_marks", "say": "Important marks highlight."}
  ]
}

Allowed element.type (use whatever the FIGURE needs — do not invent topic rules):
  line | dashedLine | arrow | doubleArrow | polyline | path | circle | rect | text | point | label
  | inductor | coil | resistor | capacitor | battery | cell
Copy topology, labels, arrows, and component count FROM THE IMAGE. Never invent a different figure.
Optional fields: x,y,x1,y1,x2,y2,cx,cy,r,width,height,points,d,text,label,stroke,fill,strokeWidth,dash,fontSize,fontWeight,opacity,reveal,group,animate
"""

DIAGRAM_REPAIR_PROMPT = """You are a diagram QA critic for educational videos.

You receive:
1) the question IMAGE (ground truth figure)
2) a candidate diagramSpec JSON

Task: If the candidate is missing parts, wrong topology, or too sparse vs the image,
return a FIXED full diagramSpec JSON that matches the image.
If the candidate already matches well, return it unchanged.

Rules:
- Output ONLY diagramSpec JSON (same schema as extract).
- Do NOT invent a different problem figure.
- Prefer light colors on dark background (#38BDF8 #F8FAFC #F87171 #A78BFA #4ADE80 #FBBF24).
- strokeWidth >= 3.5 for lines.
- Use inductor/coil/resistor/etc. only when those symbols appear in the image.
"""

# Primitives the Remotion FbdEngine can actually draw
_DRAWABLE = {
    "line",
    "dashedline",
    "arrow",
    "doublearrow",
    "polyline",
    "curve",
    "path",
    "circle",
    "point",
    "rect",
    "text",
    "label",
    "inductor",
    "coil",
    "resistor",
    "capacitor",
    "battery",
    "cell",
}


def diagram_quality(spec: Optional[dict]) -> Dict[str, Any]:
    """Generic quality gate — NO topic keywords. Returns {ok, score, issues}."""
    issues: List[str] = []
    if not spec or not isinstance(spec, dict):
        return {"ok": False, "score": 0.0, "issues": ["missing_spec"]}
    els = [e for e in (spec.get("elements") or []) if isinstance(e, dict)]
    if len(els) < 2:
        issues.append("too_few_elements")
    types = [str(e.get("type") or "").lower() for e in els]
    drawable = sum(1 for t in types if t in _DRAWABLE)
    if drawable < 2:
        issues.append("few_drawable_types")
    # Unknown types that will render as empty → quality hit
    unknown = [t for t in types if t and t not in _DRAWABLE]
    if unknown and drawable < len(els) * 0.5:
        issues.append("many_undrawable_types:" + ",".join(sorted(set(unknown))[:6]))
    # Has at least one shape beyond bare text
    if drawable and all(t in ("text", "label") for t in types):
        issues.append("text_only")
    score = 0.0
    score += min(len(els), 12) / 12.0 * 0.5
    score += min(drawable, 10) / 10.0 * 0.5
    if issues:
        score *= 0.55
    return {"ok": score >= 0.45 and "too_few_elements" not in issues, "score": round(score, 3), "issues": issues}


_LIGHT_STROKES = ["#38BDF8", "#F8FAFC", "#F87171", "#A78BFA", "#4ADE80", "#FBBF24", "#F472B6", "#22D3EE"]


def _is_dark_color(color) -> bool:
    if not color or not isinstance(color, str):
        return True
    c = color.strip().lower()
    if c in ("none", "transparent"):
        return False
    if c in ("black", "#000", "#000000", "#111", "#111111", "#0f172a", "#020617", "#070b14", "#1e293b"):
        return True
    if c.startswith("#") and len(c) in (4, 7):
        h = c[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0 < 0.45
        except ValueError:
            return True
    return False


def _light_stroke(color, salt: int = 0) -> str:
    if color and not _is_dark_color(color):
        return color
    return _LIGHT_STROKES[abs(salt) % len(_LIGHT_STROKES)]


def _normalize_points(points) -> List[List[float]]:
    """Accept list[[x,y]], list[{x,y}], or string 'x,y x,y' from Gemini."""
    if not points:
        return []
    if isinstance(points, str):
        import re

        pairs = re.findall(r"(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)", points)
        return [[float(a), float(b)] for a, b in pairs]
    if not isinstance(points, list):
        return []
    out = []
    for p in points:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                out.append([float(p[0]), float(p[1])])
            except (TypeError, ValueError):
                continue
        elif isinstance(p, dict) and "x" in p and "y" in p:
            try:
                out.append([float(p["x"]), float(p["y"])])
            except (TypeError, ValueError):
                continue
    return out


def normalize_diagram_spec(spec: Optional[dict]) -> Optional[dict]:
    if not isinstance(spec, dict):
        return None
    elements = spec.get("elements")
    if not isinstance(elements, list) or len(elements) < 2:
        return None
    out = {
        "title": spec.get("title") or "Question figure",
        "kind": spec.get("kind") or "schematic",
        "viewBox": spec.get("viewBox") or [0, 0, 1100, 520],
        "rebuildFromQuestion": bool(spec.get("rebuildFromQuestion", True)),
        "elements": [],
        "phases": spec.get("phases") if isinstance(spec.get("phases"), list) else [],
    }
    for i, el in enumerate(elements):
        if not isinstance(el, dict) or not el.get("type"):
            continue
        e = dict(el)
        e.setdefault("id", f"el_{i}")
        e.setdefault("reveal", i)
        e.setdefault("group", "main")
        e.setdefault("animate", "fade")
        e["stroke"] = _light_stroke(e.get("stroke"), i)
        if e.get("fill") and e.get("type") not in ("rect",) and _is_dark_color(e.get("fill")):
            if e.get("type") in ("text", "label", "point", "circle"):
                e["fill"] = _light_stroke(e.get("fill"), i + 3)
        sw = float(e.get("strokeWidth") or 3.5)
        e["strokeWidth"] = max(sw, 3.5)
        if "points" in e:
            e["points"] = _normalize_points(e.get("points"))
            if e["type"] in ("polyline", "curve") and len(e["points"]) < 2:
                continue
        out["elements"].append(e)
    if len(out["elements"]) < 2:
        return None
    if not out["phases"]:
        groups = sorted({e.get("group", "main") for e in out["elements"]})
        out["phases"] = [
            {
                "id": g,
                "groups": groups[: idx + 1],
                "see": f"diagram_{g}",
                "say": f"Figure part: {g}",
            }
            for idx, g in enumerate(groups)
        ]
    return out


def _mini_rdf_curve(ox: float, oy: float, w: float, h: float, peaks: List[tuple], n: int = 40):
    """peaks: list of (center_t 0..1, height 0..1, width). Returns polyline points."""
    pts = []
    for i in range(n + 1):
        t = i / n
        yv = 0.0
        for c, ht, wd in peaks:
            yv += ht * math.exp(-((t - c) / wd) ** 2)
        # Touch axis between peaks (nodes) when height near 0
        x = ox + t * w
        y = oy - yv * h
        pts.append([round(x, 1), round(y, 1)])
    return pts


def rdf_3s_options_diagram_spec() -> dict:
    """4 RDF option plots (A–D); highlight D = 3s (2 radial nodes)."""
    # Layout: 2x2 panels
    panels = [
        # (label, origin_x, origin_y, peaks, nodes_note, correct)
        ("(A)", 80, 230, [(0.22, 0.95, 0.12)], "0 nodes", False),
        ("(B)", 580, 230, [(0.15, 0.25, 0.08), (0.45, 0.9, 0.14)], "1 node", False),
        ("(C)", 80, 460, [(0.35, 0.85, 0.18)], "0 nodes", False),
        ("(D)", 580, 460, [(0.12, 0.22, 0.06), (0.32, 0.35, 0.08), (0.62, 0.85, 0.16)], "2 nodes ✓ 3s", True),
    ]
    elements = [
        {
            "id": "title",
            "type": "text",
            "x": 40,
            "y": 36,
            "text": "Radial distribution plots — find 3s",
            "fill": "#F8FAFC",
            "fontSize": 24,
            "fontWeight": 800,
            "reveal": 0,
            "group": "title",
        },
        {
            "id": "hint",
            "type": "text",
            "x": 40,
            "y": 62,
            "text": "3s: n=3, l=0 → radial nodes = n-l-1 = 2",
            "fill": "#86EFAC",
            "fontSize": 18,
            "fontWeight": 700,
            "reveal": 0,
            "group": "title",
        },
    ]
    for idx, (lab, ox, oy, peaks, note, correct) in enumerate(panels):
        w, h = 380, 140
        stroke = "#4ADE80" if correct else "#E2E8F0"
        g = f"plot_{lab.strip('()')}"
        elements += [
            {
                "id": f"box_{idx}",
                "type": "rect",
                "x": ox - 20,
                "y": oy - h - 30,
                "width": w + 50,
                "height": h + 55,
                "rx": 12,
                "fill": "rgba(15,23,42,0.7)",
                "stroke": stroke if correct else "#334155",
                "strokeWidth": 3 if correct else 1.5,
                "reveal": 1 + idx,
                "group": g,
                "animate": "fade",
            },
            {
                "id": f"ax_{idx}",
                "type": "arrow",
                "x1": ox,
                "y1": oy,
                "x2": ox + w,
                "y2": oy,
                "stroke": "#64748B",
                "strokeWidth": 2,
                "reveal": 1 + idx,
                "group": g,
            },
            {
                "id": f"ay_{idx}",
                "type": "arrow",
                "x1": ox,
                "y1": oy,
                "x2": ox,
                "y2": oy - h,
                "stroke": "#64748B",
                "strokeWidth": 2,
                "reveal": 1 + idx,
                "group": g,
            },
            {
                "id": f"curve_{idx}",
                "type": "polyline",
                "points": _mini_rdf_curve(ox, oy, w, h, peaks),
                "stroke": stroke,
                "strokeWidth": 3,
                "fill": "none",
                "reveal": 1 + idx,
                "group": g,
                "animate": "draw",
            },
            {
                "id": f"lab_{idx}",
                "type": "text",
                "x": ox + w - 40,
                "y": oy - h - 8,
                "text": lab,
                "fill": stroke,
                "fontSize": 22,
                "fontWeight": 800,
                "reveal": 1 + idx,
                "group": g,
            },
            {
                "id": f"note_{idx}",
                "type": "text",
                "x": ox + 8,
                "y": oy + 22,
                "text": note,
                "fill": "#94A3B8" if not correct else "#86EFAC",
                "fontSize": 15,
                "fontWeight": 700,
                "reveal": 5,
                "group": "marks",
            },
        ]
    elements.append(
        {
            "id": "answer_banner",
            "type": "text",
            "x": 40,
            "y": 500,
            "text": "Correct plot = (D)  [MCQ option often written as (A) if choices map A→D]",
            "fill": "#FDE68A",
            "fontSize": 18,
            "fontWeight": 800,
            "reveal": 6,
            "group": "marks",
        }
    )
    return normalize_diagram_spec(
        {
            "title": "RDF plots for orbitals (JEE Main)",
            "kind": "graph",
            "viewBox": [0, 0, 1100, 520],
            "rebuildFromQuestion": True,
            "elements": elements,
            "phases": [
                {"id": "title", "groups": ["title"], "see": "diagram_axes", "say": "Yeh 4 RDF plots hain A B C D."},
                {"id": "A", "groups": ["title", "plot_A"], "see": "diagram_main", "say": "Plot A: ek peak, zero radial node."},
                {"id": "B", "groups": ["title", "plot_A", "plot_B"], "see": "diagram_main", "say": "Plot B: do peaks, ek node — 2s jaisa."},
                {"id": "C", "groups": ["title", "plot_A", "plot_B", "plot_C"], "see": "diagram_main", "say": "Plot C: broad single peak, zero node."},
                {"id": "D", "groups": ["title", "plot_A", "plot_B", "plot_C", "plot_D"], "see": "diagram_marks", "say": "Plot D: teen peaks, do nodes — yahi 3s."},
                {"id": "ans", "groups": ["title", "plot_A", "plot_B", "plot_C", "plot_D", "marks"], "see": "diagram_tip", "say": "3s ke liye plot D sahi hai."},
            ],
        }
    )


def h2_pe_curve_diagram_spec() -> dict:
    """Data-only seed for the classic JEE Adv H2 PE figure (NOT a new React component)."""
    ox, oy, w, h = 120, 400, 760, 300

    def pe_at(t: float) -> float:
        r = 0.22 + t * 1.55
        De, a, re = 1.05, 1.55, 0.72
        return De * (1 - math.exp(-a * (r - re))) ** 2 - De * 0.92

    pts = []
    for i in range(81):
        t = i / 80
        x = ox + t * w
        y = oy - ((pe_at(t) + 0.15) / 1.4) * h
        pts.append([round(x, 1), round(y, 1)])

    t_d0 = 0.62
    x_d0 = ox + t_d0 * w
    y_e0 = oy - ((pe_at(t_d0) + 0.15) / 1.4) * h

    return normalize_diagram_spec(
        {
            "title": "H2 PE curve (question figure)",
            "kind": "graph",
            "viewBox": [0, 0, 1100, 520],
            "rebuildFromQuestion": True,
            "elements": [
                {"id": "y_axis", "type": "arrow", "x1": ox, "y1": oy, "x2": ox, "y2": oy - h - 20, "stroke": "#64748B", "strokeWidth": 3, "reveal": 0, "group": "axes", "animate": "fade"},
                {"id": "x_axis", "type": "arrow", "x1": ox, "y1": oy, "x2": ox + w + 40, "y2": oy, "stroke": "#64748B", "strokeWidth": 3, "reveal": 0, "group": "axes", "animate": "fade"},
                {"id": "xlabel", "type": "text", "x": ox + w - 80, "y": oy + 36, "text": "Internuclear distance (d)", "fill": "#94A3B8", "fontSize": 18, "fontWeight": 700, "reveal": 0, "group": "axes"},
                {"id": "ylabel", "type": "text", "x": 28, "y": oy - h / 2, "text": "Potential Energy", "fill": "#94A3B8", "fontSize": 17, "fontWeight": 700, "reveal": 0, "group": "axes"},
                {"id": "curve", "type": "polyline", "points": pts, "stroke": "#F8FAFC", "strokeWidth": 3.5, "fill": "none", "reveal": 1, "group": "curve", "animate": "draw"},
                {"id": "H_left", "type": "circle", "cx": 820, "cy": 110, "r": 22, "fill": "#38BDF8", "stroke": "#7DD3FC", "strokeWidth": 2, "reveal": 2, "group": "atoms", "animate": "fade"},
                {"id": "H_right", "type": "circle", "cx": 910, "cy": 110, "r": 22, "fill": "#38BDF8", "stroke": "#7DD3FC", "strokeWidth": 2, "reveal": 2, "group": "atoms", "animate": "fade"},
                {"id": "H_l", "type": "text", "x": 813, "y": 116, "text": "H", "fill": "#0F172A", "fontSize": 18, "fontWeight": 800, "reveal": 2, "group": "atoms"},
                {"id": "H_r", "type": "text", "x": 903, "y": 116, "text": "H", "fill": "#0F172A", "fontSize": 18, "fontWeight": 800, "reveal": 2, "group": "atoms"},
                {"id": "d_arrow", "type": "doubleArrow", "x1": 844, "y1": 110, "x2": 886, "y2": 110, "stroke": "#FDE68A", "strokeWidth": 3, "reveal": 2, "group": "atoms"},
                {"id": "d_label", "type": "text", "x": 858, "y": 92, "text": "d", "fill": "#FDE68A", "fontSize": 18, "fontWeight": 800, "reveal": 2, "group": "atoms"},
                {"id": "d0_line", "type": "dashedLine", "x1": x_d0, "y1": y_e0, "x2": x_d0, "y2": oy, "stroke": "#A78BFA", "strokeWidth": 2.5, "dash": "7 6", "reveal": 3, "group": "markers", "animate": "fade"},
                {"id": "d0_label", "type": "text", "x": x_d0 - 12, "y": oy + 32, "text": "d0", "fill": "#C4B5FD", "fontSize": 20, "fontWeight": 800, "reveal": 3, "group": "markers"},
                {"id": "E0_line", "type": "dashedLine", "x1": ox, "y1": y_e0, "x2": x_d0, "y2": y_e0, "stroke": "#F472B6", "strokeWidth": 2.5, "dash": "8 6", "reveal": 4, "group": "markers", "animate": "fade"},
                {"id": "E0_point", "type": "point", "cx": x_d0, "cy": y_e0, "r": 8, "fill": "#F472B6", "stroke": "#FDF2F8", "strokeWidth": 2, "reveal": 4, "group": "markers"},
                {"id": "E0_label", "type": "text", "x": ox + 16, "y": y_e0 - 14, "text": "E0", "fill": "#F9A8D4", "fontSize": 24, "fontWeight": 800, "reveal": 4, "group": "markers"},
                {"id": "tip", "type": "text", "x": 56, "y": 480, "text": "E0 = net PE when ee and nn repulsion are absent", "fill": "#86EFAC", "fontSize": 18, "fontWeight": 700, "reveal": 5, "group": "tip"},
            ],
            "phases": [
                {"id": "axes", "groups": ["axes"], "see": "diagram_axes", "say": "Pehle axes: PE vs internuclear distance d."},
                {"id": "curve", "groups": ["axes", "curve"], "see": "diagram_main", "say": "Ab question wala PE curve draw hota hai."},
                {"id": "atoms", "groups": ["axes", "curve", "atoms"], "see": "diagram_atoms", "say": "Do H atoms, distance d."},
                {"id": "marks", "groups": ["axes", "curve", "atoms", "markers"], "see": "diagram_marks", "say": "d0 aur E0 mark karo."},
                {"id": "tip", "groups": ["axes", "curve", "atoms", "markers", "tip"], "see": "diagram_tip", "say": "Yahi E0 hum calculate karenge."},
            ],
        }
    )


def extract_diagram_from_image(
    question_data: dict,
    images=None,
    gemini_client=None,
    hint: str = "",
) -> Optional[dict]:
    """Ask vision model to rebuild whatever figure is in the question image."""
    images = images or question_data.get("images") or []
    gemini = gemini_client or GeminiClient()
    if not gemini.is_live():
        return None

    payload = {
        "questionText": question_data.get("questionText", ""),
        "subject": question_data.get("subject", ""),
        "topic": question_data.get("topic", ""),
        "hint": hint or "Rebuild the figure exactly as in the question for teaching animation.",
        "images": images,
        "instruction": (
            "Extract / rebuild the diagram from the image into diagramSpec JSON. "
            "If there is NO figure, return {\"elements\":[]}."
        ),
    }
    res = gemini.generate_json_with_retry(DIAGRAM_EXTRACT_PROMPT, payload, max_retries=2, timeout=120)
    return normalize_diagram_spec(res)


def repair_diagram_against_image(
    question_data: dict,
    candidate: dict,
    images,
    gemini_client=None,
) -> Optional[dict]:
    """Generic AI repair: compare candidate JSON to question image — no topic hardcode."""
    if not images:
        return None
    gemini = gemini_client or GeminiClient()
    if not gemini.is_live():
        return None
    q = diagram_quality(candidate)
    payload = {
        "questionText": question_data.get("questionText", ""),
        "qualityIssues": q.get("issues"),
        "candidateDiagramSpec": candidate,
        "images": images,
        "instruction": (
            "Fix candidate diagramSpec so it matches the attached question figure. "
            "Return a complete diagramSpec JSON."
        ),
    }
    res = gemini.generate_json_with_retry(DIAGRAM_REPAIR_PROMPT, payload, max_retries=2, timeout=90)
    fixed = normalize_diagram_spec(res)
    if fixed and diagram_quality(fixed)["score"] >= diagram_quality(candidate)["score"]:
        print(
            f"[diagramSpec] repair OK score {diagram_quality(candidate)['score']} → "
            f"{diagram_quality(fixed)['score']}"
        )
        return fixed
    return None


def ensure_diagram_spec(
    question_data: dict,
    solution: dict,
    images=None,
    gemini_client=None,
) -> dict:
    """
    Automated figure pipeline (topic-agnostic):
      image → extract diagramSpec → quality gate → repair vs image → attach
    No per-question React files. No keyword packs for inductance/PE/etc.
    """
    sol = dict(solution or {})
    q = question_data or {}
    images = images or q.get("images") or []
    gemini = gemini_client or GeminiClient()

    existing = normalize_diagram_spec(sol.get("diagramSpec"))
    chosen = None

    # 1) Vision extract whenever we have the question figure
    if images:
        print("[diagramSpec] vision extract from question image...")
        ai_spec = extract_diagram_from_image(
            q,
            images=images,
            gemini_client=gemini,
            hint="Rebuild EVERY visible part of the figure; match topology and labels exactly.",
        )
        if ai_spec:
            chosen = ai_spec

    # 2) Keep existing only if better / vision failed
    if existing:
        if not chosen or diagram_quality(existing)["score"] > diagram_quality(chosen)["score"]:
            if not chosen:
                chosen = existing

    # 3) Quality gate + one generic repair pass against the image
    if chosen and images:
        qinfo = diagram_quality(chosen)
        if not qinfo["ok"]:
            print(f"[diagramSpec] quality fail {qinfo} — repairing against image...")
            repaired = repair_diagram_against_image(q, chosen, images, gemini_client=gemini)
            if repaired:
                chosen = repaired

    # 4) Fallbacks only when there is NO image (still generic)
    if not chosen:
        struct = sol.get("structureDiagram") or {}
        if struct.get("atoms"):
            chosen = structure_to_diagram_spec(struct)
        else:
            chosen = teaching_flow_diagram_spec(sol)

    sol["diagramSpec"] = chosen
    _tag_visual(sol, chosen)
    # Route teachingDocument to fbd when we have a drawn figure
    td = sol.get("teachingDocument")
    if isinstance(td, dict) and (chosen.get("elements") or []):
        # Don't override organic scheme layouts that already have SMILES
        stages = td.get("stages") or []
        has_smiles = any((s.get("smiles") or "").strip() for s in stages if isinstance(s, dict))
        if not has_smiles:
            td = dict(td)
            td["layout"] = "fbd"
            sol["teachingDocument"] = td
    return sol


def sphere_cavity_diagram_spec() -> dict:
    """Charged sphere + off-center cavity as diagramSpec (no dedicated React file)."""
    cx, cy, R = 520, 280, 160
    ccx, ccy, r = 590, 260, 70
    return normalize_diagram_spec(
        {
            "title": "Charged sphere with cavity",
            "kind": "schematic",
            "elements": [
                {"id": "sphere", "type": "circle", "cx": cx, "cy": cy, "r": R, "fill": "rgba(56,189,248,0.35)", "stroke": "#38BDF8", "strokeWidth": 4, "reveal": 0, "group": "sphere", "animate": "fade"},
                {"id": "sphere_lab", "type": "text", "x": cx - R - 20, "y": cy - R - 10, "text": "+ρ sphere", "fill": "#7DD3FC", "fontSize": 20, "fontWeight": 700, "reveal": 0, "group": "sphere"},
                {"id": "cavity", "type": "circle", "cx": ccx, "cy": ccy, "r": r, "fill": "#0F172A", "stroke": "#F472B6", "strokeWidth": 3, "dash": "8 6", "reveal": 1, "group": "cavity", "animate": "fade"},
                {"id": "cavity_lab", "type": "text", "x": ccx + r + 12, "y": ccy, "text": "cavity", "fill": "#F9A8D4", "fontSize": 18, "fontWeight": 700, "reveal": 1, "group": "cavity"},
                {"id": "center", "type": "point", "cx": cx, "cy": cy, "r": 5, "fill": "#F8FAFC", "reveal": 0, "group": "sphere"},
                {"id": "ccenter", "type": "point", "cx": ccx, "cy": ccy, "r": 5, "fill": "#F472B6", "reveal": 1, "group": "cavity"},
                {"id": "link", "type": "line", "x1": cx, "y1": cy, "x2": ccx, "y2": ccy, "stroke": "#94A3B8", "strokeWidth": 2, "reveal": 1, "group": "cavity"},
                {"id": "E1", "type": "arrow", "x1": ccx - 40, "y1": ccy, "x2": ccx + 30, "y2": ccy, "stroke": "#4ADE80", "strokeWidth": 4, "reveal": 2, "group": "field"},
                {"id": "tip", "type": "text", "x": 40, "y": 480, "text": "Inside cavity: E is uniform (superposition)", "fill": "#86EFAC", "fontSize": 20, "fontWeight": 700, "reveal": 2, "group": "field"},
            ],
            "phases": [
                {"id": "sphere", "groups": ["sphere"], "see": "diagram_axes", "say": "Pehle full charged sphere."},
                {"id": "cavity", "groups": ["sphere", "cavity"], "see": "diagram_main", "say": "Ab off-center cavity."},
                {"id": "field", "groups": ["sphere", "cavity", "field"], "see": "diagram_marks", "say": "Cavity ke andar E uniform hai."},
            ],
        }
    )


def _looks_sphere_cavity(q: dict, sol: dict) -> bool:
    blob = f"{q.get('questionText','')} {q.get('topic','')} {sol.get('concept','')}".lower()
    return any(k in blob for k in ("cavity", "superposition", "charged sphere", "sphere with"))


def _looks_pe_curve(q: dict, sol: dict) -> bool:
    blob = f"{q.get('questionText','')} {q.get('topic','')} {sol.get('concept','')}".lower()
    return any(k in blob for k in ("potential energy", "internuclear", "pe curve", "e0"))


def _looks_rdf_3s(q: dict, sol: dict) -> bool:
    blob = f"{q.get('questionText','')} {q.get('topic','')} {sol.get('concept','')}".lower()
    return ("3s" in blob or "3 s" in blob) and any(
        k in blob for k in ("radial", "distribution", "4πr", "4pir", "orbital")
    )


def _tag_visual(sol: dict, spec: dict):
    vc = sol.setdefault("visualConcept", {})
    if not isinstance(vc, dict):
        return
    vc["primaryVisual"] = "diagram_spec"
    vc["bestEngine"] = "2D"
    vc["rebuildQuestionFigure"] = True
    vc.setdefault("mustShow", [])
    if "diagram_spec" not in vc["mustShow"]:
        vc["mustShow"] = list(vc["mustShow"]) + ["diagram_spec", spec.get("kind") or "figure"]
    sim = sol.setdefault("simulation", {})
    if isinstance(sim, dict):
        sim["type"] = "diagram"
        sim.setdefault("params", {})
        sim["params"]["useDiagramSpec"] = True
        sim["describe"] = sim.get("describe") or f"Animate question figure ({spec.get('title')}) from diagramSpec phases."


def structure_to_diagram_spec(structure: dict) -> dict:
    atoms = structure.get("atoms") or []
    bonds = structure.get("bonds") or []
    by_id = {a["id"]: a for a in atoms if a.get("id")}
    elements: List[Dict[str, Any]] = []
    for i, b in enumerate(bonds):
        a1, a2 = by_id.get(b.get("from")), by_id.get(b.get("to"))
        if not a1 or not a2:
            continue
        elements.append(
            {
                "id": f"bond_{i}",
                "type": "line",
                "x1": a1["x"] + 60,
                "y1": a1["y"] + 80,
                "x2": a2["x"] + 60,
                "y2": a2["y"] + 80,
                "stroke": "#F8FAFC" if (b.get("order") or 1) >= 2 else "#CBD5E1",
                "strokeWidth": 4 if (b.get("order") or 1) >= 2 else 3,
                "reveal": 0,
                "group": "bonds",
                "animate": "draw",
            }
        )
    for i, a in enumerate(atoms):
        kind = (a.get("kind") or "C").lower()
        if kind == "label":
            elements.append(
                {
                    "id": f"lab_{i}",
                    "type": "text",
                    "x": a["x"] + 60,
                    "y": a["y"] + 80,
                    "text": a.get("label") or "",
                    "fill": "#38BDF8",
                    "fontSize": 16,
                    "fontWeight": 800,
                    "reveal": 1,
                    "group": "labels",
                }
            )
        else:
            elements.append(
                {
                    "id": f"atom_{i}",
                    "type": "circle",
                    "cx": a["x"] + 60,
                    "cy": a["y"] + 80,
                    "r": 10 if kind == "h" else 14,
                    "fill": "#38BDF8" if kind == "c" else "#F472B6",
                    "stroke": "#E2E8F0",
                    "strokeWidth": 2,
                    "reveal": 1,
                    "group": "atoms",
                }
            )
            if a.get("label") and kind != "c":
                elements.append(
                    {
                        "id": f"atomlab_{i}",
                        "type": "text",
                        "x": a["x"] + 54,
                        "y": a["y"] + 86,
                        "text": a.get("label"),
                        "fill": "#0F172A",
                        "fontSize": 14,
                        "fontWeight": 800,
                        "reveal": 1,
                        "group": "atoms",
                    }
                )
    return normalize_diagram_spec(
        {
            "title": structure.get("title") or "Structure",
            "kind": "molecule",
            "elements": elements,
            "phases": [
                {"id": "bonds", "groups": ["bonds"], "see": "diagram_main", "say": "Structure ke bonds."},
                {"id": "atoms", "groups": ["bonds", "atoms", "labels"], "see": "diagram_marks", "say": "Atoms aur labels."},
            ],
        }
    )


def teaching_flow_diagram_spec(solution: dict) -> dict:
    given = (solution.get("given") or ["Given"])[0][:40]
    find = (solution.get("find") or "Find")[:40]
    idea = (solution.get("intuition") or "Idea")[:40]
    formula = (solution.get("formula") or "Formula")[:40]
    cards = [
        ("GIVEN", given, "#38BDF8", 60),
        ("IDEA", idea, "#A78BFA", 320),
        ("FIND", find, "#F472B6", 580),
        ("FORMULA", formula, "#4ADE80", 840),
    ]
    elements = []
    for i, (lab, body, color, x) in enumerate(cards):
        elements += [
            {"id": f"card_{i}", "type": "rect", "x": x, "y": 140, "width": 220, "height": 200, "rx": 16, "fill": "rgba(15,23,42,0.9)", "stroke": color, "strokeWidth": 3, "reveal": i, "group": f"card{i}", "animate": "fade"},
            {"id": f"lab_{i}", "type": "text", "x": x + 18, "y": 175, "text": lab, "fill": color, "fontSize": 18, "fontWeight": 800, "reveal": i, "group": f"card{i}"},
            {"id": f"body_{i}", "type": "text", "x": x + 18, "y": 230, "text": body, "fill": "#E2E8F0", "fontSize": 16, "fontWeight": 600, "reveal": i, "group": f"card{i}"},
        ]
    return normalize_diagram_spec(
        {
            "title": solution.get("concept") or "Visual roadmap",
            "kind": "schematic",
            "elements": elements,
            "phases": [
                {"id": f"c{i}", "groups": [f"card{j}" for j in range(i + 1)], "see": "diagram_main", "say": lab}
                for i, (lab, *_rest) in enumerate(cards)
            ],
        }
    )
