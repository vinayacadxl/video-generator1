"""Scheme (SMILES path) beats: show structure + explain WHY each reagent is used."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from tts.pronounce import speakable


# Generic chemistry reasons — not topic-hardcoded products
_REAGENT_WHY: List[Tuple[str, str]] = [
    (
        r"O3|ozon",
        "Yahan double bond cleave hoti hai - ozonolysis se carbonyl compounds bante hain.",
    ),
    (
        r"Ag2O|NH4OH|Tollen",
        "Aldehyde selectively acid banata hai; ketone is step me safe rehta hai.",
    ),
    (
        r"NaBH4|borohydride",
        "Ketone reduce hoke alcohol banta hai - selective reduction.",
    ),
    (
        r"LiAlH4|lithium aluminium",
        "Strong reduction - carbonyl alcohol me jaata hai.",
    ),
    (
        r"H\+|H⁺|acid work|H3O",
        "Acid se ring close / workup - final cyclic product banta hai.",
    ),
    (
        r"KMnO4|permanganate",
        "Oxidative cleavage / oxidation is reagent se hoti hai.",
    ),
    (
        r"Zn.*H2O|H2O.*Zn|reductive work",
        "Reductive workup se aldehydes/ketones milte hain, over-oxidation nahi.",
    ),
]


def _scheme_doc(sc: dict, solution: dict) -> dict:
    override = sc.get("teachingDocumentOverride") or {}
    if override.get("stages") or override.get("edges"):
        return override
    td = solution.get("teachingDocument") or {}
    if td.get("stages") or td.get("edges"):
        return td
    return {}


def _clean_reagent(label: str) -> str:
    t = (label or "").strip()
    t = re.sub(r"^\(\d+\)\s*", "", t)
    return re.sub(r"\s+", " ", t).strip()[:80]


def _why_for_reagent(reagent: str, callout: str = "", step_hint: str = "") -> str:
    if (callout or "").strip():
        return callout.strip()[:160]
    if (step_hint or "").strip():
        return step_hint.strip()[:160]
    blob = reagent or ""
    for pat, reason in _REAGENT_WHY:
        if re.search(pat, blob, re.I):
            return reason
    if reagent:
        return f"Is reagent se next structure banata hai - bond change screen pe dekho."
    return "Next intermediate - structure carefully dekho."


def _path_stages(doc: dict) -> List[dict]:
    stages = [s for s in (doc.get("stages") or []) if isinstance(s, dict)]
    path = [
        s
        for s in stages
        if str(s.get("role") or "").lower() in ("start", "mid", "end", "reactant", "intermediate", "product", "")
        and str(s.get("kind") or "").lower() != "option"
        and not re.match(r"^opt", str(s.get("id") or ""), re.I)
    ]
    if not path:
        path = [s for s in stages if str(s.get("kind") or "").lower() != "option"]
    return path


def _edge_into(stage_id: str, edges: List[dict]) -> str:
    for e in edges or []:
        if not isinstance(e, dict):
            continue
        tgt = str(e.get("to") or e.get("target") or "")
        if tgt == stage_id:
            return _clean_reagent(str(e.get("label") or ""))
    return ""


def _step_hints(solution: dict) -> List[str]:
    hints: List[str] = []
    for step in solution.get("steps") or []:
        if isinstance(step, str):
            hints.append(step[:140])
        elif isinstance(step, dict):
            t = step.get("explanation") or step.get("say") or step.get("title") or ""
            if t:
                hints.append(str(t)[:140])
    return hints


def build_scheme_visual_beats(scheme_doc: dict, solution: dict | None = None, duration: float = 18.0) -> List[dict]:
    """One beat per path molecule: reagent + WHY (not 'Scheme start')."""
    solution = solution or {}
    path = _path_stages(scheme_doc)
    edges = [e for e in (scheme_doc.get("edges") or []) if isinstance(e, dict)]
    hints = _step_hints(solution)

    if not path:
        return [
            {
                "at": 0.0,
                "see": "mol_path",
                "say": "Reaction scheme dekhte hain — har arrow ka reason samajhte hain.",
            }
        ]

    n = len(path)
    dur = max(float(duration), 3.2 * n + 2.0)
    step = (dur - 1.5) / max(n, 1)
    beats: List[dict] = []

    for i, st in enumerate(path):
        sid = str(st.get("id") or f"m{i}")
        label = str(st.get("label") or sid).strip()[:60]
        callout = str(st.get("callout") or "")
        reagent = _edge_into(sid, edges)
        hint = hints[i] if i < len(hints) else (hints[i - 1] if i and i - 1 < len(hints) else "")

        if i == 0:
            say = f"Start: {label}. Yeh reactant se scheme shuru."
        else:
            why = _why_for_reagent(reagent, callout, hint)
            if reagent:
                say = f"Reagent: {reagent}. {why}"
            else:
                say = why
            # Keep product name short at end of line if space
            if label and label.lower() not in say.lower() and len(say) < 120:
                say = f"{say} Product: {label}."

        beats.append(
            {
                "at": round(i * step, 1),
                "see": f"mol_{sid}",
                "say": say[:220],
            }
        )
    return beats


def enrich_scheme_scenes(plan: dict, solution: dict) -> dict:
    """Replace stub scheme beats with step + reason teaching."""
    plan = dict(plan or {})
    solution = dict(solution or {})
    scenes = list(plan.get("scenes") or [])
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        eng = str(sc.get("engine") or "")
        layout = str(sc.get("boardLayout") or "").lower()
        if eng != "smiles_scheme" and layout != "scheme":
            continue
        doc = _scheme_doc(sc, solution)
        n = len(_path_stages(doc)) or max(1, len(doc.get("edges") or []))
        dur = max(float(sc.get("duration") or 16.0), 3.2 * n + 2.0)
        beats = build_scheme_visual_beats(doc, solution, dur)
        nar = speakable(" ".join(b["say"] for b in beats))[:560]
        on = dict(sc.get("onScreen") or {})
        on["bullets"] = []
        on["equations"] = []
        on["equationBeats"] = []
        on["answer"] = None
        on["progressiveReveal"] = True
        on["boardOnly"] = True
        # Avoid duplicating long title under CHEMISTRY chrome
        if on.get("title") and len(str(on.get("title"))) > 40:
            on.pop("title", None)
        scenes[i] = {
            **sc,
            "duration": dur,
            "visualBeats": beats,
            "narration": nar or sc.get("narration"),
            "onScreen": on,
            "boardLayout": "scheme",
            "engine": sc.get("engine") or "smiles_scheme",
        }
    plan["scenes"] = scenes
    return plan
