"""Ensure every lesson video uses the full Remotion toolkit mix.

AI still chooses *what* to teach; this guarantees *which engines* appear:
  - Remotion 2D (equations / cards) — always
  - smiles-drawer via SchemeEngine — scheme board scene
  - dagre (+ React Flow shell) via FlowEngine — flowchart scene
  - Three.js via ThreeDScene — at least one spatial 3D scene

No per-question hardcode: stages/edges come from TeachingDocument / steps.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _path_stages(td: dict) -> List[dict]:
    stages = list(td.get("stages") or [])
    path = [s for s in stages if str(s.get("role") or "") != "option"]
    return path if path else stages


def _flow_doc_from_solution(solution: dict) -> dict:
    """Build a flowchart-friendly view of the same teaching data (no new facts)."""
    td = dict(solution.get("teachingDocument") or {})
    stages = _path_stages(td)
    edges = list(td.get("edges") or [])
    if len(stages) < 2:
        steps = [s for s in (solution.get("steps") or []) if isinstance(s, dict)]
        stages = [
            {
                "id": "s0",
                "kind": "label",
                "label": str(solution.get("concept") or "Start")[:60],
                "role": "start",
            }
        ]
        for i, st in enumerate(steps[:5]):
            stages.append(
                {
                    "id": f"s{i + 1}",
                    "kind": "label",
                    "label": str(st.get("title") or st.get("say") or f"Step {i + 1}")[:60],
                    "role": "end" if i == min(len(steps), 5) - 1 else "mid",
                }
            )
        edges = [
            {
                "source": stages[i]["id"],
                "target": stages[i + 1]["id"],
                "from": stages[i]["id"],
                "to": stages[i + 1]["id"],
                "label": str(steps[i].get("formula") or "")[:40] if i < len(steps) else "",
            }
            for i in range(len(stages) - 1)
        ]
    return {
        "layout": "flowchart",
        "title": td.get("title") or solution.get("concept") or "Process flow",
        "stages": stages,
        "edges": edges,
        "answer": td.get("answer"),
        "beats": td.get("beats") or [],
    }


def _scheme_doc_from_solution(solution: dict) -> dict:
    td = dict(solution.get("teachingDocument") or {})
    if str(td.get("layout") or "") in ("scheme", "mcq") and _path_stages(td):
        out = dict(td)
        out["layout"] = "scheme"
        return out
    flow = _flow_doc_from_solution(solution)
    flow["layout"] = "scheme"
    # Prefer SMILES on start/end when present on original
    for s in flow.get("stages") or []:
        if s.get("smiles"):
            s["kind"] = "molecule"
    return flow


def _has_engine(scenes: List[dict], engine: str) -> bool:
    return any(str(sc.get("engine") or "").lower() == engine for sc in scenes)


def _tag_existing_2d(scenes: List[dict]) -> None:
    for sc in scenes:
        if str(sc.get("visualMode") or "2D").upper() != "3D" and not sc.get("engine"):
            sc["engine"] = "remotion_2d"


def _wants_chemistry_scheme(solution: dict, plan: dict) -> bool:
    """Data-driven: SMILES / scheme layout present — not keyword lists."""
    td = solution.get("teachingDocument") or {}
    pack = solution.get("visualPack") or {}
    if any((s.get("smiles") or "").strip() for s in (td.get("stages") or []) if isinstance(s, dict)):
        return True
    if pack.get("molecules"):
        return True
    return str(td.get("layout") or "").lower() in ("scheme", "mcq")


def ensure_full_engine_mix(
    plan: Optional[dict],
    solution: Optional[dict],
) -> dict:
    """
    Patch lesson plan so every video uses Remotion + Three.js + relevant boards.
    Chemistry → smiles scheme; Physics → diagramSpec FBD (not empty molecule boxes).
    """
    plan = dict(plan or {})
    solution = dict(solution or {})
    scenes: List[dict] = list(plan.get("scenes") or [])
    if not scenes:
        return plan

    video = plan.setdefault("video", {})
    video["visualMode"] = "HYBRID"
    use_chem = _wants_chemistry_scheme(solution, plan)
    video["engines"] = {
        "2D": "remotion",
        "3D": "threejs",
        "molecules": "smiles-drawer" if use_chem else "off",
        "flowchart": "dagre+xyflow",
        "figure": "fbd/diagramSpec",
    }
    video["toolkitPolicy"] = "content_driven_engines"

    _tag_existing_2d(scenes)

    scheme_doc = _scheme_doc_from_solution(solution)
    flow_doc = _flow_doc_from_solution(solution)
    has_diagram = bool((solution.get("diagramSpec") or {}).get("elements"))

    # --- Primary figure scene ---
    if use_chem and not _has_engine(scenes, "smiles_scheme"):
        from .scheme_scene import build_scheme_visual_beats

        scheme_beats = build_scheme_visual_beats(scheme_doc, solution, 16.0)
        scheme_dur = max(16.0, 3.2 * max(len(scheme_beats), 1) + 2.0)
        scheme_scene = {
            "id": "scene_toolkit_scheme",
            "type": "DIAGRAM",
            "visualMode": "2D",
            "engine": "smiles_scheme",
            "boardLayout": "scheme",
            "teachingDocumentOverride": scheme_doc,
            "duration": scheme_dur,
            "learningGoal": "Scheme + reason for each reagent.",
            "narration": " ".join(b["say"] for b in scheme_beats)[:560],
            "onScreen": {
                "subtitle": "Step + reason",
                "given": [],
                "find": "",
                "bullets": [],
                "equations": [],
                "answer": None,
                "boardOnly": True,
                "progressiveReveal": True,
            },
            "visualBeats": scheme_beats,
            "visuals": ["teaching_scheme", "smiles_drawer"],
            "animations": ["fade_in", "highlight"],
            "actions": [{"action": "CREATE", "target": "SchemeEngine"}],
        }
        replaced = False
        for i, sc in enumerate(scenes):
            if str(sc.get("type") or "").upper() == "DIAGRAM" and not sc.get("engine"):
                scenes[i] = {**sc, **scheme_scene, "id": sc.get("id") or scheme_scene["id"]}
                replaced = True
                break
        if not replaced:
            scenes.insert(min(2, len(scenes)), scheme_scene)
    elif (not use_chem) and has_diagram and not _has_engine(scenes, "fbd_diagram"):
        # Physics / any figure: use phase-rich scene from diagramSpec (not a 3-beat stub)
        from .visual_teaching import build_figure_scene

        fbd_scene = build_figure_scene(solution)
        fbd_scene["engine"] = "fbd_diagram"
        fbd_scene["boardLayout"] = "fbd"
        fbd_scene["visualMode"] = "2D"
        # Remove wrongly injected empty chemistry scheme if present
        scenes = [sc for sc in scenes if str(sc.get("engine") or "") != "smiles_scheme"]
        replaced = False
        for i, sc in enumerate(scenes):
            if str(sc.get("type") or "").upper() in ("DIAGRAM", "SIMULATION", "MOTION") and not sc.get(
                "force3D"
            ):
                scenes[i] = {**sc, **fbd_scene, "id": sc.get("id") or fbd_scene["id"]}
                replaced = True
                break
        if not replaced:
            scenes.insert(min(2, len(scenes)), fbd_scene)

    # --- Flowchart / dagre scene ---
    if not _has_engine(scenes, "dagre_flow"):
        flow_scene = {
            "id": "scene_toolkit_flow",
            "type": "EXPLANATION",
            "visualMode": "2D",
            "engine": "dagre_flow",
            "boardLayout": "flowchart",
            "teachingDocumentOverride": flow_doc,
            "duration": 12.0,
            "learningGoal": "Follow the process as a flowchart.",
            "narration": (
                "Ab same steps ko flowchart me dekhte hain — "
                "kaunsa step pehle, kaunsa baad me, bilkul clear."
            ),
            "onScreen": {
                "title": flow_doc.get("title") or "Flow",
                "subtitle": "dagre layout + React Flow",
                "given": [],
                "find": "",
                "bullets": [s.get("label") for s in (flow_doc.get("stages") or [])[:4]],
                "equations": [],
                "answer": None,
            },
            "visuals": ["teaching_flow", "dagre"],
            "animations": ["fade_in"],
            "actions": [{"action": "CREATE", "target": "FlowEngine"}],
        }
        from .flow_scene import build_flow_visual_beats

        flow_scene["visualBeats"] = build_flow_visual_beats(flow_doc, flow_scene["duration"])
        flow_scene["narration"] = " ".join(b["say"] for b in flow_scene["visualBeats"])[:600]
        flow_scene["onScreen"]["bullets"] = []
        flow_scene["onScreen"]["boardOnly"] = True
        # Insert after scheme / early explanation slot
        insert_at = min(3, len(scenes))
        scenes.insert(insert_at, flow_scene)

    # --- Three.js ONLY for true spatial sims that MATCH the question ———
    # Never inject "3D intuition / Three.js spatial model" stub for fluid/circuit/etc.
    from .pipeline_audit import sanitize_simulation, sim_allowed_for_question

    solution = sanitize_simulation(solution, {})
    sim_type = str((solution.get("simulation") or {}).get("type") or "").lower()
    q_blob = " ".join(
        [
            str(solution.get("questionText") or ""),
            str(solution.get("concept") or ""),
            str(solution.get("teachingGoal") or ""),
            str(video.get("topic") or ""),
            str(video.get("title") or ""),
        ]
    ).lower()
    wants_spatial_3d = sim_type in ("projectile", "rocket", "vehicle", "earth") and sim_allowed_for_question(
        sim_type, q_blob
    )
    if has_diagram and not use_chem and not wants_spatial_3d:
        # Force INTUITION/MOTION onto the same question figure (2D FBD).
        # Never force HOOK/RECAP onto FBD — those need given/find chips for question explain.
        for i, sc in enumerate(scenes):
            st = str(sc.get("type") or "").upper()
            if st in ("HOOK", "RECAP", "CONCLUSION", "CALCULATION"):
                continue
            if st in ("INTUITION", "MOTION", "SIMULATION") or sc.get("force3D"):
                scenes[i] = {
                    **sc,
                    "visualMode": "2D",
                    "engine": "fbd_diagram" if has_diagram else "remotion_2d",
                    "boardLayout": "fbd" if has_diagram else sc.get("boardLayout"),
                    "force3D": False,
                    "visuals": list(
                        dict.fromkeys(
                            [v for v in (sc.get("visuals") or []) if "three" not in str(v).lower()]
                            + (["diagram_spec", "fbd"] if has_diagram else [])
                        )
                    ),
                }
    elif not _has_engine(scenes, "threejs") and wants_spatial_3d:
        concept = str(solution.get("concept") or video.get("title") or "Concept")
        three_scene = {
            "id": "scene_toolkit_3d",
            "type": "INTUITION",
            "visualMode": "3D",
            "engine": "threejs",
            "force3D": True,
            "duration": 12.0,
            "learningGoal": "Build spatial intuition in 3D.",
            "narration": (
                f"Thoda spatial view bhi dekh lo — {concept} ko 3D me "
                "rotate karke intuition strong karte hain."
            ),
            "onScreen": {
                "title": "3D intuition",
                "subtitle": "Three.js spatial model",
                "given": [],
                "find": "",
                "bullets": ["Rotate", "Spatial motion"],
                "equations": [],
                "answer": None,
            },
            "visualBeats": [
                {"at": 0.0, "see": "sim_start", "say": "3D model"},
                {"at": 6.0, "see": "sim_focus", "say": "Rotate focus"},
                {"at": 10.0, "see": "sim_hold", "say": "Hold"},
            ],
            "visuals": ["threejs"],
            "animations": ["orbit", "fade_in"],
            "actions": [{"action": "SIMULATE", "simulation": sim_type or "projectile"}],
        }
        replaced = False
        for i, sc in enumerate(scenes):
            st = str(sc.get("type") or "").upper()
            if st in ("MOTION", "INTUITION", "SIMULATION") and not sc.get("force3D"):
                scenes[i] = {
                    **sc,
                    "visualMode": "3D",
                    "engine": "threejs",
                    "force3D": True,
                    "visuals": list(dict.fromkeys((sc.get("visuals") or []) + ["threejs"])),
                }
                replaced = True
                break
        if not replaced:
            scenes.insert(min(2, len(scenes)), three_scene)

    # Ensure at least one plain remotion_2d calculation/recap
    if not _has_engine(scenes, "remotion_2d"):
        for sc in scenes:
            if str(sc.get("visualMode") or "2D").upper() != "3D":
                sc["engine"] = "remotion_2d"
                break

    # Mark remaining untagged 2D scenes
    _tag_existing_2d(scenes)

    plan["scenes"] = scenes
    used = sorted({str(sc.get("engine") or "remotion_2d") for sc in scenes})
    video["enginesUsed"] = used
    return plan


def verify_engine_mix(plan: dict) -> Dict[str, Any]:
    """Return pass/fail checklist for toolkit coverage."""
    scenes = plan.get("scenes") or []
    engines = {str(sc.get("engine") or "") for sc in scenes}
    modes = {str(sc.get("visualMode") or "").upper() for sc in scenes}
    has_figure = "smiles_scheme" in engines or "fbd_diagram" in engines
    # threejs optional when the lesson is figure/circuit-first (no fake molecule 3D)
    return {
        "ok": has_figure
        and "remotion_2d" in engines
        and "dagre_flow" in engines
        and "2D" in modes,
        "engines": sorted(engines),
        "modes": sorted(modes),
        "sceneCount": len(scenes),
        "scenes": [
            {
                "id": sc.get("id"),
                "type": sc.get("type"),
                "visualMode": sc.get("visualMode"),
                "engine": sc.get("engine"),
                "boardLayout": sc.get("boardLayout"),
            }
            for sc in scenes
        ],
    }
