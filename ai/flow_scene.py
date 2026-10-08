"""Flowchart scene beats synced to TeachingDocument stages (not 'Flow start' stubs)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from tts.pronounce import speakable


def _flow_doc(sc: dict, solution: dict) -> dict:
    override = sc.get("teachingDocumentOverride") or {}
    if override.get("stages"):
        return override
    td = solution.get("teachingDocument") or {}
    if td.get("stages"):
        return td
    return {}


def _edge_src(e: dict) -> str:
    return str(e.get("from") or e.get("source") or "")


def _edge_tgt(e: dict) -> str:
    return str(e.get("to") or e.get("target") or "")


def _clean_reagent(label: str) -> str:
    """'(1) O3, Zn, H2O' → 'O3, Zn, H2O' for voice."""
    t = (label or "").strip()
    t = re.sub(r"^\(\d+\)\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:80]


def _short_product(label: str) -> str:
    """Keep screen-friendly short name; long IUPAC still OK for say after speakable()."""
    t = (label or "").strip()
    if len(t) > 48:
        # Prefer last meaningful chunk (acid / aldehyde / product)
        for key in ("acid", "aldehyde", "alcohol", "product", "lactone"):
            if key in t.lower():
                return t
        return t[:45] + "…"
    return t


def _incoming_reagents(stage_id: str, edges: List[dict]) -> Optional[str]:
    labs = []
    for e in edges or []:
        if not isinstance(e, dict):
            continue
        if _edge_tgt(e) == stage_id:
            lab = _clean_reagent(str(e.get("label") or ""))
            if lab:
                labs.append(lab)
    if not labs:
        return None
    return ", ".join(labs[:2])


def build_flow_visual_beats(flow_doc: dict, duration: float = 18.0) -> List[dict]:
    """Short teaching lines: reagent + product. TTS uses speakable; screen caption stays readable."""
    stages = [s for s in (flow_doc.get("stages") or []) if isinstance(s, dict)]
    edges = [e for e in (flow_doc.get("edges") or []) if isinstance(e, dict)]
    if not stages:
        return [
            {
                "at": 0.0,
                "see": "flow_main",
                "say": "Process flow dekhte hain step by step.",
            },
        ]
    n = len(stages)
    # Shorter per-step hold — less dead air, tighter video
    dur = max(float(duration), 2.4 * n + 1.5)
    step = (dur - 1.0) / max(n, 1)
    beats = []
    for i, st in enumerate(stages):
        sid = str(st.get("id") or f"s{i}")
        product = _short_product(str(st.get("label") or sid))
        reagents = _incoming_reagents(sid, edges)
        if i == 0:
            say = f"Start: {product}."
        elif reagents:
            say = f"Reagent: {reagents}. Product: {product}."
        else:
            say = f"Next: {product}."
        beats.append(
            {
                "at": round(i * step, 1),
                "see": f"flow_{sid}",
                "say": say,
            }
        )
    return beats


def enrich_flow_scenes(plan: dict, solution: dict) -> dict:
    """Replace generic flow toolkit beats with stage-synced teaching."""
    plan = dict(plan or {})
    solution = dict(solution or {})
    scenes = list(plan.get("scenes") or [])
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        if str(sc.get("engine") or "") != "dagre_flow":
            continue
        doc = _flow_doc(sc, solution)
        dur = float(sc.get("duration") or 18.0)
        n_stages = len(doc.get("stages") or [])
        if n_stages >= 3:
            dur = max(dur, 2.4 * n_stages + 1.5)
        beats = build_flow_visual_beats(doc, dur)
        # TTS-safe joined narration (reagents as names, not letter spam)
        nar = speakable(" ".join(b["say"] for b in beats))[:520]
        on = dict(sc.get("onScreen") or {})
        on["bullets"] = []
        on["equations"] = []
        on["equationBeats"] = []
        on["answer"] = None
        on["progressiveReveal"] = True
        on["boardOnly"] = True
        scenes[i] = {
            **sc,
            "duration": dur,
            "visualBeats": beats,
            "narration": nar or sc.get("narration"),
            "onScreen": on,
            "boardLayout": "flowchart",
        }
    plan["scenes"] = scenes
    return plan
