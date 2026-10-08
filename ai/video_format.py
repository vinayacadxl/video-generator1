"""Canonical lesson video format — one template for every question.

UI (Visual Audit + Format tab) and enrich_* steps enforce this order.
"""

from __future__ import annotations

from typing import Any, Dict, List

# What the student should see vs hear at each stage (no topic hardcode)
LESSON_FORMAT: List[Dict[str, Any]] = [
    {
        "order": 1,
        "sceneType": "HOOK",
        "purpose": "Question samajhna — answer spoil nahi",
        "screenShows": [
            "Title + topic",
            "Question figure (start reactant SMILES) — paper se relate",
            "Full question text (question beat pe)",
            "Given chips — ek-ek karke, jo bol rahe ho wahi",
            "Find badge (target only, not answer value)",
        ],
        "screenHides": [
            "Final answer",
            "Correct option tick",
            "Equation list",
            "Full solved scheme product as answer",
        ],
        "voiceRule": "Structure dikhao to usi ka naam bolo — text-only 'image displays' mat chhodo",
        "captionRule": "Sirf bottom subtitle — upar duplicate mat likho",
        "engine": "remotion_2d",
    },
    {
        "order": 2,
        "sceneType": "INTUITION",
        "purpose": "Concept / intuition (2D figure ya short idea)",
        "screenShows": ["Figure ya 1–2 idea bullets synced to beat"],
        "screenHides": ["Full answer", "All MCQ options solved"],
        "voiceRule": "Naya idea — repeat mat karo",
        "engine": "fbd_diagram | remotion_2d",
    },
    {
        "order": 3,
        "sceneType": "DIAGRAM",
        "purpose": "Question figure step-by-step",
        "screenShows": [
            "Scheme path (SMILES) OR diagramSpec phases - cumulative",
            "Har arrow pe reagent",
        ],
        "screenHides": ["Duplicate long title under CHEMISTRY", "Stub 'Scheme start'"],
        "voiceRule": "Har step: reagent + WHY (kyun ye reagent) - sirf structure naam mat padho",
        "engine": "smiles_scheme | fbd_diagram",
    },
    {
        "order": 4,
        "sceneType": "EXPLANATION",
        "purpose": "Flow / process map",
        "screenShows": ["Flowchart nodes one-by-one"],
        "screenHides": ["Side column duplicate formulas (board only)"],
        "voiceRule": "Node highlight ke saath short reason",
        "engine": "dagre_flow",
    },
    {
        "order": 5,
        "sceneType": "BREAKDOWN | CALCULATION",
        "purpose": "Steps + equations progressively",
        "screenShows": ["One equation per beat"],
        "screenHides": ["Pehle se saara answer"],
        "engine": "remotion_2d",
    },
    {
        "order": 6,
        "sceneType": "CONCLUSION | RECAP",
        "purpose": "Answer + takeaway",
        "screenShows": ["Final answer", "Key takeaway"],
        "engine": "remotion_2d",
    },
]


def format_blueprint_for_ui() -> List[Dict[str, Any]]:
    return [dict(x) for x in LESSON_FORMAT]


def attach_format_to_plan(plan: dict) -> dict:
    plan = dict(plan or {})
    video = plan.setdefault("video", {})
    video["formatBlueprint"] = format_blueprint_for_ui()
    video["formatVersion"] = "lesson-v1"
    return plan


def scene_format_checklist(scenes: List[dict]) -> List[Dict[str, Any]]:
    """Map actual scenes to format slots for UI debug."""
    out = []
    for i, sc in enumerate(scenes or []):
        if not isinstance(sc, dict):
            continue
        st = str(sc.get("type") or "").upper()
        eng = str(sc.get("engine") or "")
        on = sc.get("onScreen") or {}
        issues = []
        if st == "HOOK":
            if on.get("answer"):
                issues.append("HOOK must not set onScreen.answer")
            if on.get("equations") or on.get("equationBeats"):
                issues.append("HOOK must not show equation list")
            if (on.get("bullets") or []) and len(on.get("bullets") or []) > 2:
                issues.append("HOOK bullets should be empty or minimal")
            if not on.get("questionAnchor") and not on.get("questionText"):
                issues.append("HOOK should show question text and/or question figure anchor")
        if st not in ("CONCLUSION", "RECAP") and on.get("answer"):
            issues.append(f"{st} must not show final answer early")
        if eng in ("dagre_flow", "smiles_scheme"):
            beats = sc.get("visualBeats") or []
            stub = ("flow start", "next node", "end node", "scheme start", "focus structure", "product / end")
            if any(str(b.get("say") or "").lower().strip() in stub for b in beats):
                issues.append("Scheme/flow still has stub beats — need reagent + WHY lines")
            if eng == "smiles_scheme" and beats and not any(
                "why" in str(b.get("say") or "").lower()
                or "kyun" in str(b.get("say") or "").lower()
                or "se " in str(b.get("say") or "").lower()
                or "banata" in str(b.get("say") or "").lower()
                or "cleave" in str(b.get("say") or "").lower()
                or "reduce" in str(b.get("say") or "").lower()
                or "oxid" in str(b.get("say") or "").lower()
                for b in beats
            ):
                issues.append("Scheme beats missing WHY / reason lines")
        if st == "HOOK" and len(str(sc.get("narration") or "")) > 400:
            issues.append("HOOK narration too long for one screen — use beat lines")
        out.append(
            {
                "index": i,
                "id": sc.get("id"),
                "type": st,
                "engine": eng,
                "duration": sc.get("duration"),
                "beats": len(sc.get("visualBeats") or []),
                "issues": issues,
                "ok": len(issues) == 0,
            }
        )
    return out
