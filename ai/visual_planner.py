"""Visual Lesson Planner — builds Remotion/Three.js Lesson JSON from teaching solution pack.

Gemini must NOT write renderer code. It maps the Solution Pack into teachable scenes:
Hook → Intuition/Sim → Breakdown → Progressive Equations → Answer/Recap.
"""

import os
import re

from .gemini import GeminiClient
from .solution_generator import enrich_solution
from .visual_teaching import (
    beats_for_lesson_scenes,
    enrich_figure_scenes,
    enrich_question_scenes,
)
from .engine_mix import ensure_full_engine_mix
from .pipeline_audit import (
    build_visual_audit,
    sanitize_simulation,
    strip_fake_3d_scenes,
)
from .flow_scene import enrich_flow_scenes
from .scheme_scene import enrich_scheme_scenes
from .video_format import attach_format_to_plan, scene_format_checklist


HINGLISH_HINTS = (
    " hum ", " hai", " hain", " aaj ", " ab ", " toh ", " yeh ", " ye ",
    " samjh", " dekho", " dekhna", " karte", " karna", " chalo", " yaad ",
    " humein", " nahi ", " mat ", " pehle", " baad", " bilkul",
)


def _looks_hinglish(text: str) -> bool:
    t = f" {(text or '').lower()} "
    hits = sum(1 for h in HINGLISH_HINTS if h in t)
    return hits >= 2


def ensure_hinglish_narrations(scenes, gemini_client=None):
    """Rewrite scene narrations to Roman Hinglish when they are pure English."""
    if not scenes:
        return scenes
    if os.getenv("NARRATION_LANGUAGE", "hinglish").lower() in ("en", "english", "off"):
        return scenes

    need = []
    for i, scene in enumerate(scenes):
        nar = (scene.get("narration") or "").strip()
        if nar and not _looks_hinglish(nar):
            need.append((i, nar))

    if not need:
        return scenes

    gemini = gemini_client or GeminiClient()
    if gemini.is_live():
        payload = {
            "narrations": [{"index": i, "text": text} for i, text in need],
            "instruction": (
                "Rewrite each narration in natural Indian Hinglish (Roman script). "
                "Keep science terms/formulas/units in English. Same meaning, similar length. "
                "Warm teacher tone. Return JSON: {\"items\":[{\"index\":0,\"text\":\"...\"}]}"
            ),
        }
        system = (
            "You convert educational voiceover scripts to Hinglish. "
            "Respond ONLY with JSON. Do not use Devanagari."
        )
        res = gemini.generate_json_with_retry(system, payload, max_retries=2, timeout=90)
        items = (res or {}).get("items") or []
        by_idx = {int(it["index"]): it.get("text", "").strip() for it in items if "index" in it and it.get("text")}
        for i, _old in need:
            if by_idx.get(i):
                scenes[i]["narration"] = by_idx[i]
                scenes[i]["narrationLanguage"] = "hinglish"
        return scenes

    # Offline light touch: wrap common English openers into Hinglish framing
    for i, old in need:
        text = old.strip()
        text = re.sub(r"(?i)^welcome students!\s*today we will\b", "Welcome students! Aaj hum", text, count=1)
        text = re.sub(r"(?i)^welcome students!\s*", "Welcome students! Aaj hum ", text, count=1)
        text = re.sub(r"(?i)\btoday we will\b", "aaj hum", text)
        text = re.sub(r"(?i)\blet'?s\b", "chalo", text)
        text = re.sub(r"(?i)\bso the final answer is\b", "toh final answer hai", text)
        text = re.sub(r"(?i)\bremember:\b", "yaad rakho:", text)
        text = re.sub(r"(?i)\bnow we\b", "ab hum", text)
        text = re.sub(r"(?i)\bwe are given\b", "given hai", text)
        text = re.sub(r"(?i)\bwe must find\b", "humein find karna hai", text)
        text = re.sub(r"\s+", " ", text).strip()
        # Collapse accidental "Aaj hum aaj hum"
        text = re.sub(r"(?i)\baaj hum\s+aaj hum\b", "aaj hum", text)
        if not _looks_hinglish(text):
            text = f"Chalo is step ko simply samajhte hain. {text}"
        scenes[i]["narration"] = text
        scenes[i]["narrationLanguage"] = "hinglish"
    return scenes


PLANNER_SYSTEM_PROMPT = """You are the Visual Lesson Director for DoubtSolve.ai.

Pipeline:
Solution Pack (already solved) → YOUR Lesson JSON → Scene Director → Remotion 2D / Three.js 3D → ElevenLabs → FFmpeg

GOAL:
Create a video plan that makes a confused student say: "Ab samajh aa gaya!"
Not a PowerPoint. Not walls of text. Visual teaching with clear beats.

CRITICAL RULES:
1. Do NOT generate Remotion / React / Three.js / Blender code.
2. Use the Solution Pack as source of truth for formulas, numbers, answer. Do not invent new values.
3. Every scene must define:
   - narration (spoken, warm, simple)
   - onScreen (what appears: titles, given chips, equations, takeaways)
   - visualBeats (timed teaching moments: what student SEES while a sentence is spoken)
   - actions (declarative only)
4. visualMode "2D" = Remotion (equations, cards, diagrams, arrows, kinetic text)
   visualMode "3D" = Three.js (projectile, train, rocket, earth, molecules, particles)
5. MANDATORY HYBRID toolkit every video (AI chooses CONTENT, pipeline ensures ENGINES):
   - At least one Remotion 2D math/card scene
   - At least one scheme/molecule board (smiles-drawer)
   - At least one flowchart scene (dagre)
   - At least one Three.js 3D spatial/intuition scene (visualMode "3D")
   Do not make an all-2D chemistry video — keep one dedicated 3D intuition scene.
6. NARRATION LANGUAGE = HINGLISH (mandatory for every scene.narration and visualBeats[].say):
   - Natural Indian Hinglish, Roman script.
   - Keep formulas/symbols/units in English.
   - Scene 01: "Welcome students! Aaj hum ... samjhenge."
7. NO REPEATED STRATEGY: each scene narration must teach something NEW.
   Do not repeat the same "expand hydrogens / count sigma / count pi" script in every scene.
8. SCREEN MUST MATCH AUDIO: every visualBeats[].say must have matching onScreen content
   (bullets / equations with REAL numbers when you speak numbers).
   Put numeric calculation lines in onScreen.equations or equationBeats as the voice says them.
9. DATA-DRIVEN VISUALS ONLY: do not invent image file paths (no .png assets).
   Use onScreen + visualBeats.see tags the renderer understands:
   pe_curve_axes | pe_curve_draw | pe_atoms | mark_d0 | mark_E0 | virial_tip |
   skeletal_molecule | expanded_molecule | highlight_sigma_bonds | highlight_pi_bonds |
   parent_chain | numbering | substituents | equation_* | given_chips | find_badge | answer_badge |
   teaching_flow | show_vectors | simulation_start
10. CRITICAL: Show the ACTUAL compound / figure from the Solution Pack / question.
    Never swap in a different molecule (e.g. formyloxyindene for an IUPAC hexadiene MCQ).
    Pass through solution.structureDiagram unchanged in the plan.
11. VISUALS/ANIMATION MANDATORY — never plan a text-only video:
    - At least ONE dedicated DIAGRAM scene that animates solution.diagramSpec (generic figure JSON).
    - Use visualBeats.see from diagramSpec.phases (diagram_axes | diagram_main | diagram_marks | …).
    - Pass through solution.diagramSpec unchanged — ONE Remotion GenericDiagram renders ANY figure type.
    - Do NOT invent a new React component name per question; stick to diagramSpec.
    - Hook/Intuition should also reference the figure, not empty boards.
12. Never reveal final numeric answer before the calculation scene finishes.
13. Duration: 8–18s per scene; total usually 70–140s.
14. Do NOT put brand names (DoubtSolve, etc.) in onScreen titles.

MANDATORY SCENE ARC (5–7 scenes):
1. HOOK — welcome + restate question + show GIVEN + start of question figure
2. INTUITION — everyday understanding WITH a light animated diagram
3. SIMULATION / DIAGRAM — FULL rebuild+animation of the question figure (mandatory)
4. BREAKDOWN — mark important parts on that same figure (E0, d0, vectors, bonds…)
5. CALCULATION — progressive equationBeats on 2D board
6. ANSWER — celebrate final answer clearly
7. RECAP — keyTakeaway + commonMistake (short)

If solution is conceptual MCQ, replace SIMULATION with comparison diagram and use option elimination in CALCULATION.

STRICT OUTPUT JSON:
{
  "video": {
    "title": "...",
    "subject": "Physics",
    "topic": "...",
    "targetDuration": 100,
    "visualMode": "HYBRID",
    "quality": "1080p",
    "engines": {"2D": "remotion", "3D": "threejs"},
    "pedagogy": "understand_then_solve"
  },
  "solution": { "<pass through enriched solution pack>" },
  "scenes": [
    {
      "id": "scene_01",
      "type": "HOOK",
      "visualMode": "2D",
      "duration": 10,
      "narration": "Welcome students! Aaj hum is question ko step by step samjhenge...",
      "learningGoal": "Know what is given and what we must find",
      "onScreen": {
        "title": "Concept Title",
        "subtitle": "Question samajhte hain",
        "given": ["values from question"],
        "find": "What to find",
        "bullets": [],
        "equations": [],
        "answer": null
      },
      "visualBeats": [
        {"at": 0.0, "see": "title_card", "say": "Topic introduce karo"},
        {"at": 3.0, "see": "given_chips", "say": "Given values dikhao"},
        {"at": 6.0, "see": "find_badge", "say": "Kya find karna hai highlight karo"}
      ],
      "visuals": ["title", "given_chips"],
      "animations": ["fade_in", "highlight"],
      "actions": [
        {"action": "CREATE", "target": "TitleCard"},
        {"action": "HIGHLIGHT", "target": "GivenParameters"}
      ]
    }
  ]
}

Supported actions:
CREATE, MOVE, FADE_IN, FADE_OUT, HIGHLIGHT, SHOW_LABEL, SHOW_EQUATION, SHOW_ARROW,
SHOW_VECTOR, SHOW_DISTANCE, ANIMATE_PROPERTY, GRAPH, PARTICLE_EFFECT, SIMULATE

For SIMULATE, copy simulation.type and simulation.params from the Solution Pack.
For SHOW_EQUATION, prefer equationBeats[].latex in order.
"""


def _step_join(steps):
    parts = []
    for s in steps or []:
        if isinstance(s, dict):
            parts.append(s.get("explanation") or s.get("say") or "")
        else:
            parts.append(str(s))
    return ". ".join([p for p in parts if p])


def _generic_diagram_scene(solution) -> dict:
    """Animate whatever is in solution.diagramSpec (any exam figure)."""
    from .visual_teaching import build_figure_scene

    return build_figure_scene(solution or {})


def _organic_visual_beats(pack, solution):
    beats = beats_for_lesson_scenes(pack or {}, solution or {})
    if beats:
        return beats
    return [
        {"at": 0.0, "see": "mol_main", "say": "Pehle structure dekho."},
        {"at": 8.0, "see": "mol_path", "say": "Phir reaction path step by step."},
    ]


def _beats_from_teaching_document(td, solution):
    """Map TeachingDocument.beats → lesson visualBeats."""
    if not isinstance(td, dict):
        return []
    layout = str(td.get("layout") or "")
    out = []
    for b in td.get("beats") or []:
        if not isinstance(b, dict) or not b.get("say"):
            continue
        focus = b.get("focus") or ""
        if layout in ("scheme", "mcq"):
            see = f"mol_{focus}" if focus else "mol_main"
        elif layout == "flowchart":
            see = f"flow_{focus}" if focus else "flow_main"
        elif layout == "plot":
            see = f"plot_{focus}" if focus else "diagram_main"
        else:
            see = focus or "diagram_main"
        out.append({"at": float(b.get("t") or 0), "see": see, "say": str(b.get("say"))})
    return out


def ensure_visual_scenes(plan, solution):
    """Guarantee every lesson has a TeachingDocument-driven diagram scene."""
    plan = dict(plan or {})
    scenes = list(plan.get("scenes") or [])
    if not scenes:
        return plan

    td = solution.get("teachingDocument") or {}
    layout = str(td.get("layout") or "")
    has_diagram_spec = bool((solution.get("diagramSpec") or {}).get("elements"))
    pack = solution.get("visualPack") or {}
    has_flow = layout == "flowchart" or bool((pack.get("flowGraph") or {}).get("nodes"))
    has_molecules = layout in ("scheme", "mcq") or (
        bool(pack.get("molecules")) and not has_flow
    )
    has_bio = layout == "figure" or bool((pack.get("bioFigure") or {}).get("type"))
    has_plot = layout == "plot"
    has_td = bool(td.get("layout") and (td.get("stages") or td.get("plot") or td.get("figure") or td.get("edges")))
    has_visual = False
    for sc in scenes:
        st = str(sc.get("type") or "").upper()
        visuals = " ".join(sc.get("visuals") or []).lower()
        sees = " ".join(str(b.get("see") or "") for b in (sc.get("visualBeats") or [])).lower()
        if (
            st in ("DIAGRAM", "MOTION", "SIMULATION")
            or "diagram" in f"{visuals} {sees}"
            or "molecule" in visuals
            or "biology" in visuals
            or "teaching_" in visuals
            or "flow_" in sees
        ):
            has_visual = True
            break

    if has_td or has_flow or has_molecules or has_bio or has_plot:
        beat_list = _beats_from_teaching_document(td, solution) or beats_for_lesson_scenes(pack, solution)
        fig_duration = 16.0
        if beat_list:
            fig_duration = max(18.0, float(beat_list[-1].get("at") or 0) + 8.0)
        visual_tag = {
            "scheme": "teaching_scheme",
            "mcq": "teaching_mcq",
            "flowchart": "teaching_flow",
            "plot": "teaching_plot",
            "figure": "biology_figure",
            "fbd": "diagram_spec",
        }.get(layout) or (
            "teaching_flow"
            if has_flow
            else ("molecule_smiles" if has_molecules else ("biology_figure" if has_bio else "diagram_spec"))
        )
        fig = {
            "id": "scene_typed_visual",
            "type": "DIAGRAM",
            "visualMode": "2D",
            "duration": fig_duration,
            "learningGoal": "See structured teaching figure for this question.",
            "narration": (
                " ".join(b.get("say") or "" for b in (td.get("beats") or [])[:2])
                or " ".join(pack.get("teachNotes") or [])
                or "Ab question ke structures / labeled diagram ko carefully dekhte hain."
            ),
            "onScreen": {
                "title": td.get("title") or pack.get("title") or solution.get("concept") or "Figure",
                "subtitle": layout or pack.get("domain") or "visual",
                "given": solution.get("given") or [],
                "find": solution.get("find") or "",
                "bullets": [b.get("say") for b in (td.get("beats") or []) if b.get("say")][:4]
                or pack.get("teachNotes")
                or [],
                "equations": [],
                "answer": None,
            },
            "visualBeats": beat_list
            or [
                {"at": 0.0, "see": "diagram_main", "say": "Figure start"},
                {"at": 6.0, "see": "diagram_marks", "say": "Important parts"},
                {"at": 12.0, "see": "diagram_tip", "say": "Key highlight"},
            ],
            "visuals": [visual_tag],
            "animations": ["fade_in", "highlight"],
            "actions": [{"action": "CREATE", "target": "TeachingStage"}],
        }
        replaced = False
        for i, sc in enumerate(scenes):
            if str(sc.get("type") or "").upper() in ("MOTION", "SIMULATION", "DIAGRAM"):
                scenes[i] = fig
                replaced = True
                break
        if not replaced:
            scenes.insert(min(2, len(scenes)), fig)
        has_visual = True

    if has_diagram_spec and not has_molecules and not has_bio:
        fig = _generic_diagram_scene(solution)
        already = any(
            "diagram_spec" in " ".join(sc.get("visuals") or []).lower()
            or "question_figure" in " ".join(sc.get("visuals") or []).lower()
            for sc in scenes
        )
        if not already:
            for i, sc in enumerate(scenes):
                if str(sc.get("type") or "").upper() in ("MOTION", "SIMULATION", "DIAGRAM"):
                    scenes[i] = fig
                    already = True
                    break
            if not already:
                scenes.insert(min(2, len(scenes)), fig)
        for sc in scenes:
            if str(sc.get("type") or "").upper() in ("HOOK", "INTRO", "INTUITION", "MOTION", "DIAGRAM"):
                sc.setdefault("visuals", [])
                if "diagram_spec" not in sc["visuals"]:
                    sc["visuals"] = list(sc["visuals"]) + ["diagram_spec"]
        has_visual = True

    if not has_visual:
        scenes.insert(min(2, len(scenes)), _generic_diagram_scene(solution))

    plan["scenes"] = scenes
    return plan


class VisualPlanner:
    def __init__(self, gemini_client=None):
        self.gemini = gemini_client or GeminiClient()

    def plan(self, question_data, solution_data, force_visual_mode=None):
        solution = enrich_solution(solution_data, question_data)
        visual_mode = (
            force_visual_mode
            or solution.get("visualConcept", {}).get("bestEngine")
            or "HYBRID"
        )

        prompt_payload = {
            "question": question_data,
            "solutionPack": solution,
            "visualMode": visual_mode,
            "instruction": (
                "Build a student-friendly Lesson JSON from this Solution Pack. "
                "Preserve exact formulas, numbers, and answer. "
                "ALL scene narration MUST be Hinglish (Roman script). "
                "MANDATORY: include a DIAGRAM/MOTION scene that rebuilds and animates "
                "the question figure (PE curve / molecule / vectors). Never text-only. "
                "Use equationBeats for progressive math. Use simulation for spatial scenes."
            ),
        }

        if self.gemini.is_live():
            res = self.gemini.generate_json_with_retry(PLANNER_SYSTEM_PROMPT, prompt_payload)
            if res and "scenes" in res and len(res["scenes"]) >= 4:
                plan = self._normalize_plan(res, question_data, solution, visual_mode)
            else:
                plan = self._offline_fallback(question_data, solution, visual_mode)
        else:
            plan = self._offline_fallback(question_data, solution, visual_mode)

        # Kill wrong sim BEFORE engine mix injects Three.js projectile stub
        solution = sanitize_simulation(solution, question_data)
        plan = ensure_visual_scenes(plan, solution)
        # Content-driven engines (3D only when spatial sim matches question)
        plan = ensure_full_engine_mix(plan, solution)
        plan = strip_fake_3d_scenes(plan, solution)
        # Explain the question properly (given / find / traps) before figure
        plan = enrich_question_scenes(plan, solution, question_data)
        # Deepen figure DIAGRAM beats (phases + intuition/formula) — no topic hardcode
        plan = enrich_figure_scenes(plan, solution)
        plan = enrich_flow_scenes(plan, solution)
        plan = enrich_scheme_scenes(plan, solution)
        plan["scenes"] = ensure_hinglish_narrations(plan.get("scenes") or [], self.gemini)
        plan.setdefault("video", {})["narrationLanguage"] = "hinglish"
        plan = attach_format_to_plan(plan)
        plan["visualAudit"] = build_visual_audit(plan, solution, question_data)
        plan["visualAudit"]["formatChecklist"] = scene_format_checklist(plan.get("scenes") or [])
        plan["solution"] = solution
        return plan

    def _normalize_plan(self, plan, question_data, solution, visual_mode):
        plan = dict(plan)
        plan["solution"] = solution
        video = plan.setdefault("video", {})
        video.setdefault("title", question_data.get("topic") or solution.get("concept") or "Lesson")
        video.setdefault("subject", question_data.get("subject", "Science"))
        video.setdefault("topic", question_data.get("topic", solution.get("concept", "")))
        video["engines"] = {"2D": "remotion", "3D": "threejs"}
        video["visualMode"] = visual_mode
        video.setdefault("pedagogy", "understand_then_solve")

        # Ensure each scene has onScreen + visualBeats defaults
        has_fig = bool((solution.get("diagramSpec") or {}).get("elements"))
        for scene in plan.get("scenes", []):
            scene.setdefault("onScreen", {})
            scene.setdefault("visualBeats", [])
            scene.setdefault("visuals", [])
            scene.setdefault("animations", [])
            scene.setdefault("actions", [])
            if not scene.get("narration"):
                scene["narration"] = "Chalo, is step ko carefully samajhte hain."
            # Sanitize bullets — never leave raw step dicts
            oscreen = scene["onScreen"]
            if isinstance(oscreen.get("bullets"), list):
                clean = []
                for b in oscreen["bullets"]:
                    if isinstance(b, dict):
                        clean.append(str(b.get("title") or b.get("say") or b.get("explanation") or "")[:120])
                    else:
                        clean.append(str(b)[:160])
                oscreen["bullets"] = [c for c in clean if c and not c.strip().startswith("{")]
            # Chemistry: keep diagram visuals on 2D teaching scenes, but NEVER
            # strip an explicit force3D / toolkit Three.js scene.
            if has_fig or str(question_data.get("subject", "")).lower().startswith("chem"):
                if scene.get("force3D") or str(scene.get("engine") or "") == "threejs":
                    scene["visualMode"] = "3D"
                elif str(scene.get("visualMode", "")).upper() == "3D" and (
                    solution.get("simulation") or {}
                ).get("type") not in ("projectile", "rocket", "vehicle", "earth", "molecule"):
                    # Soft downgrade only accidental 3D without toolkit tag
                    scene["visualMode"] = "2D"
                if (
                    str(scene.get("visualMode", "2D")).upper() != "3D"
                    and "diagram_spec" not in (scene.get("visuals") or [])
                    and str(scene.get("type", "")).upper()
                    in ("HOOK", "INTRO", "INTUITION", "DIAGRAM", "MOTION", "EXPLANATION")
                ):
                    scene["visuals"] = list(scene.get("visuals") or []) + ["diagram_spec"]
        return plan

    def _offline_fallback(self, question_data, solution, visual_mode):
        subject = question_data.get("subject", "Physics")
        q_text = question_data.get("questionText", "")
        title = solution.get("concept") or question_data.get("topic") or f"{subject} Lesson"
        sim = solution.get("simulation") or {}
        sim_type = sim.get("type", "none")
        use_3d = visual_mode in ("3D", "HYBRID") and sim_type not in ("none", "", None)
        beats = solution.get("equationBeats") or []
        given = solution.get("given") or []
        answer = solution.get("answer", "")
        intuition = solution.get("intuition", "")
        takeaway = solution.get("keyTakeaway", "")
        mistake = solution.get("commonMistake", "")
        find = solution.get("find", "")

        eq_actions = [
            {"action": "SHOW_EQUATION", "equation": b.get("latex", ""), "label": b.get("label", "")}
            for b in beats
            if b.get("latex")
        ]

        scenes = [
            {
                "id": "scene_01",
                "type": "HOOK",
                "visualMode": "2D",
                "duration": 10.0,
                "learningGoal": "Know the question, given values, and target.",
                "narration": (
                    f"Welcome students! Aaj hum {title} samjhenge. "
                    f"Question yeh hai: {q_text[:150]}. "
                    f"Given hai {', '.join(given[:3]) or 'question ke values'}, aur humein find karna hai {find or 'required answer'}."
                ),
                "onScreen": {
                    "title": title,
                    "subtitle": "Pehle question samajhte hain",
                    "given": given,
                    "find": find,
                    "bullets": [],
                    "equations": [],
                    "answer": None,
                },
                "visualBeats": [
                    {"at": 0.0, "see": "title_card", "say": "Welcome"},
                    {"at": 3.5, "see": "given_chips", "say": "Show givens"},
                    {"at": 7.0, "see": "find_badge", "say": "Show target"},
                ],
                "visuals": ["title", "given_chips"],
                "animations": ["fade_in", "highlight"],
                "actions": [
                    {"action": "CREATE", "target": "TitleCard"},
                    {"action": "HIGHLIGHT", "target": "GivenParameters"},
                ],
            },
            {
                "id": "scene_02",
                "type": "INTRO",
                "visualMode": "2D",
                "duration": 12.0,
                "learningGoal": "Build everyday intuition before formulas.",
                "narration": (
                    f"{intuition} "
                    + (
                        "Ab question wale graphs / figure ko screen pe dekhte hain."
                        if (solution.get("diagramSpec") or {}).get("elements")
                        else "Ab concept ko clear steps me todo."
                    )
                ),
                "onScreen": {
                    "title": "Pehle intuition",
                    "subtitle": "Concept, phir figure",
                    "given": [],
                    "find": "",
                    "bullets": [intuition] if intuition else ["Concept clearly samjho"],
                    "equations": [],
                    "answer": None,
                },
                "visualBeats": [
                    {"at": 0.0, "see": "diagram_axes", "say": "Simply explain karo"},
                    {"at": 4.0, "see": "diagram_main", "say": "Figure / graph dikhao"},
                ],
                "visuals": ["diagram_spec", "intuition"],
                "animations": ["fade_in"],
                "actions": [{"action": "HIGHLIGHT", "target": "Intuition"}],
                "visualMode": "2D",
            },
            (
                _generic_diagram_scene(solution)
                if (solution.get("diagramSpec") or {}).get("elements")
                else {
                "id": "scene_03",
                "type": "MOTION",
                "visualMode": "3D" if use_3d else "2D",
                "duration": 14.0,
                "learningGoal": "See the concept move.",
                "narration": (
                    sim.get("describe")
                    or "Dhyan se visual dekho — yeh motion bilkul wahi hai jo equations describe karengi."
                ),
                "onScreen": {
                    "title": "Concept dekho",
                    "subtitle": sim_type if sim_type != "none" else "Diagram",
                    "given": [],
                    "find": "",
                    "bullets": solution.get("visualConcept", {}).get("mustShow", []),
                    "equations": [],
                    "answer": None,
                },
                "visualBeats": [
                    {"at": 0.0, "see": "diagram_main", "say": "Figure start"},
                    {"at": 5.0, "see": "diagram_marks", "say": "Important parts notice karo"},
                    {"at": 10.0, "see": "diagram_tip", "say": "Final state hold"},
                ],
                "visuals": ["diagram_spec"],
                "animations": ["launch_projectile", "draw_trajectory"] if sim_type == "projectile" else ["fade_in", "highlight"],
                "actions": [
                    {
                        "action": "SIMULATE",
                        "simulation": sim_type if sim_type not in ("none", "", None) else "diagram",
                        "params": sim.get("params", {}),
                    }
                ],
            }
            ),
            {
                "id": "scene_04",
                "type": "EXPLANATION",
                "visualMode": "2D",
                "duration": 12.0,
                "learningGoal": "Identify the important parts of the figure / concept.",
                "narration": (
                    _step_join(solution.get("steps")[:2])
                    or "Ab figure ke important parts mark karte hain, taaki formula clear ho jaye."
                ),
                "onScreen": {
                    "title": "Parts mein todo",
                    "subtitle": "Figure pe marks",
                    "given": given,
                    "find": find,
                    "bullets": [
                        str(s.get("title") or s.get("say") or s.get("explanation") or "")[:100]
                        for s in (solution.get("steps") or [])[:3]
                        if isinstance(s, dict)
                    ],
                    "equations": [solution.get("formula")] if solution.get("formula") else [],
                    "answer": None,
                },
                "visualBeats": [
                    {"at": 0.0, "see": "diagram_main", "say": "Parts dikhao"},
                    {"at": 6.0, "see": "diagram_marks", "say": "Important marks highlight"},
                ],
                "visuals": ["diagram_spec", "labels"],
                "animations": ["highlight"],
                "actions": (
                    [
                        {"action": "SHOW_VECTOR", "label": "ux", "color": "cyan"},
                        {"action": "SHOW_VECTOR", "label": "uy", "color": "pink"},
                        {"action": "SHOW_VECTOR", "label": "g", "color": "red"},
                    ]
                    if sim_type == "projectile"
                    else [{"action": "HIGHLIGHT", "target": "Breakdown"}]
                ),
            },
            {
                "id": "scene_05",
                "type": "CALCULATION",
                "visualMode": "2D",
                "duration": 16.0,
                "learningGoal": "Solve step-by-step with progressive equations.",
                "narration": " ".join(
                    [b.get("say") or b.get("latex", "") for b in beats]
                    or ["Ab carefully calculate karte hain — ek equation, ek step."]
                ),
                "onScreen": {
                    "title": "Step by step solve",
                    "subtitle": "Formula → Substitute → Answer",
                    "given": given,
                    "find": find,
                    "bullets": [],
                    "equations": [b.get("latex", "") for b in beats],
                    "equationBeats": beats,
                    "answer": None,
                },
                "visualBeats": [
                    {"at": float(i * 3.5), "see": f"equation_{b.get('id', i)}", "say": b.get("say", "")}
                    for i, b in enumerate(beats)
                ],
                "visuals": ["equation_board"],
                "animations": ["write_equation", "substitute"],
                "actions": eq_actions
                or [{"action": "SHOW_EQUATION", "equation": solution.get("formula") or "Let's calculate"}],
            },
            {
                "id": "scene_06",
                "type": "CONCLUSION",
                "visualMode": "2D",
                "duration": 10.0,
                "learningGoal": "Lock the final answer and exam tip.",
                "narration": (
                    f"Toh final answer hai {answer}. "
                    f"{solution.get('answerPlain') or ''} "
                    f"Yaad rakho: {takeaway} "
                    f"Yeh common mistake avoid karna: {mistake}"
                ),
                "onScreen": {
                    "title": "Final Answer",
                    "subtitle": takeaway,
                    "given": [],
                    "find": find,
                    "bullets": [takeaway, f"Avoid: {mistake}"],
                    "equations": [],
                    "answer": answer,
                },
                "visualBeats": [
                    {"at": 0.0, "see": "answer_badge", "say": "Answer reveal"},
                    {"at": 5.0, "see": "takeaway", "say": "Key tip"},
                ],
                "visuals": ["answer", "takeaway"],
                "animations": ["highlight", "pulse"],
                "actions": [{"action": "HIGHLIGHT", "target": "FinalAnswer"}],
            },
        ]

        return {
            "video": {
                "title": title,
                "subject": subject,
                "topic": question_data.get("topic", title),
                "targetDuration": sum(s["duration"] for s in scenes),
                "visualMode": visual_mode,
                "quality": "1080p",
                "engines": {"2D": "remotion", "3D": "threejs"},
                "pedagogy": "understand_then_solve",
            },
            "solution": solution,
            "scenes": scenes,
        }
