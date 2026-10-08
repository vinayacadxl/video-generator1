"""Visual pipeline audit — detect wrong-topic / stale sim / engine mismatches."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


SPATIAL_3D = frozenset({"projectile", "rocket", "vehicle", "earth"})

SIM_KEYWORDS: Dict[str, tuple] = {
    "projectile": (
        "projectile",
        "thrown at an angle",
        "angle of projection",
        "parabolic path",
        "trajectory of a projectile",
        "maximum range of projectile",
        "projected with",
    ),
    "rocket": ("rocket", "thrust", "escape velocity"),
    "vehicle": ("train", "car brakes", "braking", "collision of vehicles"),
    "earth": ("earth orbit", "satellite", "planetary"),
    "free_fall": ("free fall", "dropped from", "falls from rest"),
    "circular": ("circular motion", "centripetal", "uniform circular"),
    "shm": ("simple harmonic", "pendulum", "shm"),
    "wave": ("wavelength", "traveling wave", "standing wave"),
    "molecule": ("molecule", "smiles", "organic", "iupac", "bond angle"),
    "diagram": ("circuit", "inductor", "fluid", "bernoulli", "diagram", "figure"),
}


def _blob(solution: dict, question_data: Optional[dict] = None) -> str:
    qd = question_data or {}
    parts = [
        qd.get("questionText") or "",
        qd.get("topic") or "",
        qd.get("subject") or "",
        solution.get("questionText") or "",
        solution.get("concept") or "",
        solution.get("teachingGoal") or "",
        solution.get("find") or "",
        " ".join(str(g) for g in (solution.get("given") or [])[:6]),
    ]
    return " ".join(parts).lower()


def sim_allowed_for_question(sim_type: str, blob: str) -> bool:
    st = (sim_type or "").lower().strip()
    if not st or st in ("none", "diagram", "pe_curve"):
        return True
    keys = SIM_KEYWORDS.get(st)
    if not keys:
        # Unknown sim types are OK only if not spatial projectile default
        return st not in SPATIAL_3D
    return any(k in blob for k in keys)


def sanitize_simulation(solution: dict, question_data: Optional[dict] = None) -> dict:
    """Drop mismatched sims (e.g. projectile on Fluid Dynamics). Mutates solution."""
    sol = solution if isinstance(solution, dict) else {}
    sim = dict(sol.get("simulation") or {})
    st = str(sim.get("type") or "").lower().strip()
    blob = _blob(sol, question_data)

    if st and not sim_allowed_for_question(st, blob):
        sol["simulation"] = {
            "type": "diagram",
            "params": {"useDiagramSpec": bool((sol.get("diagramSpec") or {}).get("elements"))},
            "describe": (
                f"Reset mismatched sim '{st}' — question does not match that spatial model. "
                "Use diagram / 2D teaching instead."
            ),
            "_sanitizedFrom": st,
        }
        vc = sol.get("visualConcept")
        if isinstance(vc, dict) and str(vc.get("primaryVisual") or "").lower() == "projectile":
            vc["primaryVisual"] = "diagram_spec" if (sol.get("diagramSpec") or {}).get("elements") else "formula"
            vc["bestEngine"] = "2D"
    elif not st:
        # leave empty; enrich_solution will guess
        pass

    # Strip broad false positives: never keep projectile unless keywords match
    st2 = str((sol.get("simulation") or {}).get("type") or "").lower()
    if st2 == "projectile" and not sim_allowed_for_question("projectile", blob):
        sol["simulation"] = {
            "type": "diagram",
            "params": {},
            "describe": "Projectile blocked — question is not projectile motion.",
            "_sanitizedFrom": "projectile",
        }

    return sol


def strip_fake_3d_scenes(plan: dict, solution: dict) -> dict:
    """Demote threejs / force3D scenes when solution has no real spatial sim."""
    plan = dict(plan or {})
    sol = solution or {}
    sim = str((sol.get("simulation") or {}).get("type") or "").lower()
    allow_3d = sim in SPATIAL_3D
    has_fig = bool((sol.get("diagramSpec") or {}).get("elements"))
    scenes = []
    demoted = []
    for sc in plan.get("scenes") or []:
        if not isinstance(sc, dict):
            continue
        eng = str(sc.get("engine") or "").lower()
        mode = str(sc.get("visualMode") or "").upper()
        force = bool(sc.get("force3D"))
        if (eng == "threejs" or force or mode == "3D") and not allow_3d:
            demoted.append(sc.get("id"))
            sc = {
                **sc,
                "visualMode": "2D",
                "engine": "fbd_diagram" if has_fig else "remotion_2d",
                "boardLayout": "fbd" if has_fig else sc.get("boardLayout"),
                "force3D": False,
                "visuals": [
                    v
                    for v in (sc.get("visuals") or [])
                    if "three" not in str(v).lower()
                ]
                + (["diagram_spec", "fbd"] if has_fig else ["remotion_2d"]),
            }
            # Kill the stub title that reveals the fake toolkit scene
            on = dict(sc.get("onScreen") or {})
            if str(on.get("title") or "") in ("3D intuition", "3D Concept"):
                on["title"] = sol.get("concept") or on.get("title")
                on["subtitle"] = "2D concept (no fake projectile 3D)"
                sc["onScreen"] = on
        scenes.append(sc)
    plan["scenes"] = scenes
    plan.setdefault("video", {})["demotedFake3D"] = demoted
    return plan


def build_visual_audit(
    plan: dict,
    solution: dict,
    question_data: Optional[dict] = None,
) -> Dict[str, Any]:
    """Per-scene audit for UI: what engine, what sim, mismatches."""
    qd = question_data or {}
    sol = solution or {}
    plan = plan or {}
    blob = _blob(sol, qd)
    sim = sol.get("simulation") or {}
    sim_type = str(sim.get("type") or "none").lower()
    has_fig = bool((sol.get("diagramSpec") or {}).get("elements"))
    fig_n = len((sol.get("diagramSpec") or {}).get("elements") or [])
    phases_n = len((sol.get("diagramSpec") or {}).get("phases") or [])

    issues: List[str] = []
    if sim.get("_sanitizedFrom"):
        issues.append(
            f"Simulation was sanitized: '{sim.get('_sanitizedFrom')}' -> '{sim_type}' "
            "(did not match question)."
        )
    if sim_type in SPATIAL_3D and not sim_allowed_for_question(sim_type, blob):
        issues.append(f"WARNING: sim={sim_type} still does not match question keywords.")

    q_snip = str(qd.get("questionText") or sol.get("questionText") or "")[:180]
    scenes_out = []
    for sc in plan.get("scenes") or []:
        if not isinstance(sc, dict):
            continue
        eng = str(sc.get("engine") or "untagged")
        mode = str(sc.get("visualMode") or "?")
        force = bool(sc.get("force3D"))
        actions = sc.get("actions") or []
        sim_action = next(
            (
                a.get("simulation")
                for a in actions
                if isinstance(a, dict) and str(a.get("action") or "").upper() == "SIMULATE"
            ),
            None,
        )
        title = (sc.get("onScreen") or {}).get("title") or ""
        scene_issues = []
        if eng == "threejs" or force or mode.upper() == "3D":
            if sim_type not in SPATIAL_3D:
                scene_issues.append("3D scene without spatial sim — likely wrong/stale animation")
            if title in ("3D intuition",) or "Three.js spatial" in str(
                (sc.get("onScreen") or {}).get("subtitle") or ""
            ):
                scene_issues.append("Toolkit stub title (generic 3D) — not question-specific")
        if eng == "fbd_diagram" and not has_fig:
            scene_issues.append("fbd_diagram engine but diagramSpec has no elements")
        if "projectile" in str(sc.get("animations") or []).lower() and "projectile" not in blob:
            scene_issues.append("projectile animation tag on non-projectile question")

        expected = "2D"
        if sim_type in SPATIAL_3D and sim_allowed_for_question(sim_type, blob):
            expected = "3D-spatial"
        elif has_fig:
            expected = "2D-figure"
        elif eng in ("smiles_scheme", "dagre_flow"):
            expected = "2D-board"

        ok = len(scene_issues) == 0
        if not ok:
            issues.extend([f"{sc.get('id')}: {x}" for x in scene_issues])

        scenes_out.append(
            {
                "id": sc.get("id"),
                "type": sc.get("type"),
                "engine": eng,
                "visualMode": mode,
                "force3D": force,
                "boardLayout": sc.get("boardLayout"),
                "duration": sc.get("duration"),
                "onScreenTitle": title,
                "simulateAction": sim_action,
                "beats": len(sc.get("visualBeats") or []),
                "expectedLane": expected,
                "ok": ok,
                "issues": scene_issues,
                "narrationPreview": str(sc.get("narration") or "")[:100],
            }
        )

    engines = sorted({str(s.get("engine") or "") for s in scenes_out})
    return {
        "ok": len(issues) == 0,
        "questionPreview": q_snip,
        "concept": sol.get("concept"),
        "topic": qd.get("topic") or (plan.get("video") or {}).get("topic"),
        "subject": qd.get("subject") or (plan.get("video") or {}).get("subject"),
        "simulation": {
            "type": sim_type,
            "params": sim.get("params") or {},
            "describe": str(sim.get("describe") or "")[:160],
            "allowedForQuestion": sim_allowed_for_question(sim_type, blob),
            "sanitizedFrom": sim.get("_sanitizedFrom"),
        },
        "diagramSpec": {
            "present": has_fig,
            "elementCount": fig_n,
            "phaseCount": phases_n,
            "title": (sol.get("diagramSpec") or {}).get("title"),
        },
        "enginesUsed": engines,
        "sceneCount": len(scenes_out),
        "scenes": scenes_out,
        "issues": issues,
        "demotedFake3D": (plan.get("video") or {}).get("demotedFake3D") or [],
    }
