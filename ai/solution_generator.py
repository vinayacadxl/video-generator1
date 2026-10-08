"""Solution Engine — video-ready teaching solution for Remotion + Three.js.

Gemini must return a pedagogically structured solution so the Scene Director
can show: given → intuition → simulation → vectors → progressive equations → answer.
"""

import re
from .gemini import GeminiClient


SOLUTION_SYSTEM_PROMPT = """You are a master STEM teacher creating a SOLUTION PACK for an animated educational video.

The video pipeline is:
Gemini Solution Pack → Visual Lesson JSON → Remotion (2D) / Three.js (3D) → ElevenLabs → FFmpeg → MP4

Your job is NOT only to solve the question. You must structure the solution so a student
can UNDERSTAND it easily when watching the video.

STRICT RULES:
1. Be scientifically correct. Verify arithmetic. Prefer standard constants (13.6 eV for H, etc.).
2. Solve ONLY the provided questionText / image. Never substitute a sample physics projectile problem.
3. Keep the subject consistent with the question (Chemistry → chemistry visuals; Physics → physics visuals).
4. Use student-friendly HINGLISH (Roman script) in "intuition", step "say", and equationBeats "say".
   Keep formulas/symbols/units in English. Example: "Pehle velocity ko ux aur uy mein todo."
5. Break math into progressive equation beats: formula → substitute → simplify → answer.
6. Never invent numbers not present in the question; if a value is missing, keep it symbolic.
7. Do NOT write Remotion/Three.js/Blender code. Only structured JSON.
8. "steps" MUST be an array of objects (not plain strings).
9. If questionText is missing/unreadable, return:
   {"error": "UNREADABLE_QUESTION", "reason": "No clear question to solve."}
9b. H2 PE CURVE / E0 TRAP (JEE Adv 2020 — critical):
   - Zero when e- and nucleus infinitely far = IONIZED reference, NOT ground-state H.
   - Ground-state H TOTAL energy E = -13.6 eV; by VIRIAL theorem POTENTIAL energy V = 2E = -27.2 eV.
   - Question asks NET POTENTIAL ENERGY when ee & nn repulsion absent
     → E0 = 2 × (-27.2) = -54.4 eV/molecule
     → with NA=6.023e23 and 1 eV=1.6e-19 J: E0 = -5242.42 kJ mol^-1 (official).
   - NEVER answer 0. NEVER answer ~-2621 (that wrongly used total energy 2×(-13.6)).
   - MUST put that figure in diagramSpec (axes, Morse curve, E0, d0, H—H) for GenericDiagram.
10. VISUALS ARE MANDATORY — pick the RIGHT reusable system (never invent a new React file / never hardcode one question):
    A) Prefer teachingDocument (single IR) — pipeline also extracts it if missing:
       layout: scheme|flowchart|plot|figure|mcq|fbd
       stages[] + edges[] (scheme/flowchart), plot{}, figure{}, answer{}, beats[]
       Molecules = SMILES only. NEVER freehand bond coordinates.
    B) GRAPHS / PE / RDF: teachingDocument.layout=plot with series points, or diagramSpec.
    C) Never invent a DIFFERENT sample molecule than the question asks.
12. teachingDocument example (ibuprofen scheme):
    {
      "layout": "scheme",
      "title": "Ibuprofen synthesis",
      "stages": [
        {"id":"s1","kind":"molecule","label":"Benzene","smiles":"c1ccccc1","role":"start"},
        {"id":"s2","kind":"molecule","label":"Product","smiles":"...","role":"end"},
        {"id":"optB","kind":"molecule","label":"(B)","smiles":"...","role":"option","correct":true}
      ],
      "edges": [{"from":"s1","to":"s2","label":"reagents from figure"}],
      "answer": {"option":"B","plain":"..."},
      "beats": [{"t":0,"focus":"s1","say":"Pehle benzene"}]
    }
13. diagramSpec format (graphs/physics ONLY — viewBox 0..1100 x 0..520, y DOWN):
    {
      "title": "Question figure",
      "kind": "graph|schematic|fbd|circuit|geometry|molecule|mixed",
      "viewBox": [0,0,1100,520],
      "rebuildFromQuestion": true,
      "elements": [
        {"id":"e1","type":"arrow|line|dashedLine|polyline|circle|rect|text|point|doubleArrow",
         "x1":120,"y1":400,"x2":900,"y2":400,"stroke":"#64748B","strokeWidth":3,
         "reveal":0,"group":"axes","animate":"fade|draw"}
      ],
      "phases": [
        {"id":"axes","groups":["axes"],"see":"diagram_axes","say":"Pehle axes."},
        {"id":"main","groups":["axes","curve"],"see":"diagram_main","say":"Main figure."}
      ]
    }

Return ONLY this JSON:

{
  "concept": "<core concept from THIS question>",
  "teachingGoal": "<one sentence>",
  "given": ["values actually present"],
  "find": "<what to find>",
  "intuition": "<2-3 short spoken sentences>",
  "visualConcept": {
    "bestEngine": "2D | 3D | HYBRID",
    "primaryVisual": "teaching_scheme | teaching_flow | teaching_plot | biology_figure | diagram_spec",
    "why": "<why this visual helps>",
    "mustShow": ["formula", "answer"],
    "rebuildQuestionFigure": true
  },
  "teachingDocument": {
    "layout": "scheme|flowchart|plot|figure|mcq|fbd",
    "title": "short",
    "stages": [],
    "edges": [],
    "plot": null,
    "figure": null,
    "answer": {"option": null, "plain": ""},
    "beats": []
  },
  "diagramSpec": null,
  "simulation": {
    "type": "diagram | molecule | projectile | free_fall | circular | shm | wave | vehicle | earth | rocket",
    "params": {"useDiagramSpec": false},
    "describe": "<ANIMATION PLAN>"
  },
  "formula": "<main formula for THIS question>",
  "equationBeats": [
    { "id": "eq1", "label": "Formula", "latex": "<formula>", "say": "<spoken>" },
    { "id": "eq2", "label": "Substitute", "latex": "<with numbers if any>", "say": "<spoken>" },
    { "id": "eq3", "label": "Answer", "latex": "<final>", "say": "<spoken>" }
  ],
  "steps": [
    {
      "id": "step_01",
      "title": "<short title>",
      "explanation": "<why>",
      "formula": "<relation>",
      "calculation": "<numbers if any>",
      "visualCue": "highlight",
      "say": "<spoken line>"
    }
  ],
  "answer": "<final answer with units>",
  "answerPlain": "<spoken answer>",
  "keyTakeaway": "<exam tip>",
  "commonMistake": "<common mistake>",
  "explanation": "<short wrap-up>"
}
"""


def _as_step_objects(steps):
    """Normalize legacy string steps into teaching step objects."""
    out = []
    for i, step in enumerate(steps or []):
        if isinstance(step, dict):
            out.append({
                "id": step.get("id", f"step_{i+1:02d}"),
                "title": step.get("title", f"Step {i+1}"),
                "explanation": step.get("explanation") or step.get("text") or "",
                "formula": step.get("formula", ""),
                "calculation": step.get("calculation", ""),
                "visualCue": step.get("visualCue", "highlight"),
                "say": step.get("say") or step.get("explanation") or "",
            })
        else:
            text = str(step)
            out.append({
                "id": f"step_{i+1:02d}",
                "title": f"Step {i+1}",
                "explanation": text,
                "formula": "",
                "calculation": "",
                "visualCue": "highlight",
                "say": text,
            })
    return out


def _guess_simulation(question_text: str, topic: str = ""):
    blob = f"{question_text} {topic}".lower()
    if any(
        k in blob
        for k in (
            "potential energy",
            "internuclear",
            "pe curve",
            "e0",
            "h2 molecule",
            "h₂",
        )
    ):
        return {
            "type": "diagram",
            "params": {"useDiagramSpec": True, "molecule": "H2"},
            "describe": (
                "Animate diagramSpec: axes → PE curve → H—H (d) → d0/E0 marks (generic renderer)."
            ),
        }
    # Avoid bare "range"/"trajectory" — those appear in fluid/optics/etc. and cause wrong 3D
    if any(
        k in blob
        for k in (
            "projectile",
            "thrown at an angle",
            "angle of projection",
            "parabolic path",
            "projected with velocity",
            "maximum range of projectile",
        )
    ):
        return {
            "type": "projectile",
            "params": {"u": 20, "theta": 45, "g": 9.8},
            "describe": "Launch a projectile and draw the parabolic path with ux, uy, and g.",
        }
    if any(k in blob for k in ("free fall", "dropped", "falls from")):
        return {"type": "free_fall", "params": {"h0": 20, "g": 9.8}, "describe": "Show free-fall under gravity."}
    if any(k in blob for k in ("circular", "centripetal", "orbit")):
        return {"type": "circular", "params": {"r": 2, "omega": 1.5}, "describe": "Show circular motion path."}
    if any(k in blob for k in ("pendulum", "shm", "simple harmonic")):
        return {"type": "shm", "params": {"A": 2, "omega": 2}, "describe": "Show oscillating motion."}
    if any(k in blob for k in ("wave", "wavelength", "frequency")):
        return {"type": "wave", "params": {"A": 1, "k": 1.2, "omega": 2}, "describe": "Animate a traveling wave."}
    if any(k in blob for k in ("molecule", "atom", "bond", "electron", "iupac", "organic")):
        return {"type": "molecule", "params": {}, "describe": "Show atoms/bonds or organic structure for THIS compound."}
    if any(k in blob for k in ("train", "brake", "car ", "momentum", "collision")):
        return {"type": "vehicle", "params": {}, "describe": "Show vehicle motion and change in velocity."}
    return {
        "type": "diagram",
        "params": {},
        "describe": "Animate a teaching flow: given → idea → find → formula (never blank visuals).",
    }


def _extract_numbers(text: str):
    """Best-effort numeric extraction for offline projectile-style fallbacks."""
    vals = {}
    m_u = re.search(r"(?:u|velocity|speed)\s*=?\s*(\d+(?:\.\d+)?)\s*m/?s", text, re.I)
    m_th = re.search(r"(?:θ|theta|angle)\s*=?\s*(\d+(?:\.\d+)?)\s*°?", text, re.I)
    m_g = re.search(r"g\s*=?\s*(\d+(?:\.\d+)?)", text, re.I)
    if m_u:
        vals["u"] = float(m_u.group(1))
    if m_th:
        vals["theta"] = float(m_th.group(1))
    if m_g:
        vals["g"] = float(m_g.group(1))
    return vals


def enrich_solution(solution, question_data=None, images=None, gemini_client=None):
    """Ensure every solution has video-pipeline fields the renderer can consume."""
    from .teaching_document import ensure_teaching_document

    question_data = question_data or {}
    q_text = question_data.get("questionText", "")
    topic = question_data.get("topic", "")
    sol = dict(solution or {})
    images = images or question_data.get("images") or []

    sol["steps"] = _as_step_objects(sol.get("steps"))
    sol.setdefault("concept", topic or "Concept")
    if q_text:
        sol["questionText"] = q_text
    else:
        sol.setdefault("questionText", sol.get("question") or "")
    sol.setdefault("teachingGoal", sol.get("explanation") or "Understand the concept and solve confidently.")
    sol.setdefault("given", [])
    sol.setdefault("find", "")
    sol.setdefault("formula", "")
    sol.setdefault("answer", "")
    sol.setdefault("answerPlain", str(sol.get("answer", "")))
    sol.setdefault("keyTakeaway", sol.get("explanation") or "Remember the governing idea and formula.")
    sol.setdefault("commonMistake", "Do not mix symbols or skip unit checks.")
    sol.setdefault("intuition", sol.get("explanation") or "Let's build intuition before calculating.")

    if not sol.get("simulation"):
        sim = _guess_simulation(q_text, topic)
        nums = _extract_numbers(q_text)
        if nums and sim.get("type") == "projectile":
            sim["params"].update(nums)
        sol["simulation"] = sim

    # Drop wrong-topic sims (Fluid Dynamics ≠ projectile from first lesson)
    from .pipeline_audit import sanitize_simulation

    sol = sanitize_simulation(sol, question_data)

    # Hard block: chemistry / RDF / orbital must never keep projectile simulation
    subj = str(question_data.get("subject", "")).lower()
    blob = f"{q_text} {topic} {sol.get('concept', '')}".lower()
    chemish = subj.startswith("chem") or any(
        k in blob for k in ("orbital", "radial", "atomic structure", "rdf", "molecule", "3s", "hybrid")
    )
    if chemish and str((sol.get("simulation") or {}).get("type", "")).lower() == "projectile":
        sol["simulation"] = {
            "type": "diagram",
            "params": {"useDiagramSpec": False},
            "describe": "TeachingDocument layout — never projectile for chemistry.",
        }

    if not sol.get("visualConcept"):
        sol["visualConcept"] = {
            "bestEngine": "2D",
            "primaryVisual": "teaching_scheme",
            "why": "Single TeachingDocument IR — Remotion renders by layout.",
            "mustShow": ["formula", "steps", "answer"],
            "rebuildQuestionFigure": True,
        }
    else:
        vc = sol["visualConcept"]
        if isinstance(vc, dict):
            vc.setdefault("rebuildQuestionFigure", True)

    # Canonical IR: TeachingDocument (validates SMILES, sets layout, shims visualPack)
    sol = ensure_teaching_document(question_data, sol, images=images, gemini_client=gemini_client)

    if not sol.get("equationBeats"):
        beats = []
        if sol.get("formula"):
            beats.append({
                "id": "eq1",
                "label": "Formula",
                "latex": sol["formula"],
                "say": "Start from the governing formula.",
            })
        for i, step in enumerate(sol["steps"][:3]):
            latex = step.get("calculation") or step.get("formula") or step.get("explanation")
            if latex:
                beats.append({
                    "id": f"eq{i+2}",
                    "label": step.get("title") or f"Step {i+1}",
                    "latex": latex,
                    "say": step.get("say") or step.get("explanation") or "",
                })
        if sol.get("answer"):
            beats.append({
                "id": "eq_ans",
                "label": "Answer",
                "latex": str(sol["answer"]),
                "say": sol.get("answerPlain") or f"Final answer is {sol['answer']}.",
            })
        sol["equationBeats"] = beats

    # Flatten helpers for older renderer paths
    sol["stepTexts"] = [
        s.get("explanation") or s.get("say") or ""
        for s in sol["steps"]
    ]
    return sol


class SolutionGenerator:
    def __init__(self, gemini_client=None):
        self.gemini = gemini_client or GeminiClient()

    def solve(self, question_data, images=None):
        from .question_analyzer import looks_like_failed_ocr
        from .solution_verifier import verify_and_gate

        q_text = question_data.get("questionText", "")
        subject = question_data.get("subject", "General Science")
        topic = question_data.get("topic", "")
        images = images or question_data.get("images") or []

        if looks_like_failed_ocr(q_text) and not images:
            return {
                "error": "UNREADABLE_QUESTION",
                "reason": "Question text is empty or looks like a failed OCR placeholder.",
                "concept": "OCR Failed",
                "steps": [],
                "answer": "",
            }

        candidate = None
        ai_fail_reason = None
        progress = getattr(self, "progress_cb", None)

        def _prog(msg: str):
            print(f"[SolutionGenerator] {msg}")
            if callable(progress):
                try:
                    progress("INFO", msg)
                except Exception:
                    pass

        def _valid_pack(res) -> bool:
            if not res or res.get("error"):
                return False
            ans = str(res.get("answer") or "").strip()
            return bool(ans) and "requires ai" not in ans.lower()

        if self.gemini.is_live():
            # ——— Phase A: FAST answer (small JSON) — avoids 15min MixRoute hangs ———
            _prog("Stage 2a: Fast answer solve (MixRoute, ~60s)...")
            fast_prompt = {
                "subject": subject,
                "topic": topic,
                "questionText": q_text,
                "images": images,
                "instruction": (
                    f"Solve THIS {subject} MCQ/numerical from the image carefully. "
                    "Return SMALL JSON only with keys: "
                    "concept, formula, answer, answerPlain, "
                    "steps (3 objects: title, explanation, say), "
                    "equationBeats (optional 1-3), visualConcept.bestEngine. "
                    "If options A–D exist, answer MUST start with the correct letter e.g. '(A) ...'. "
                    "No giant teachingDocument. No placeholder answers."
                ),
            }
            res_fast = self.gemini.generate_json_with_retry(
                SOLUTION_SYSTEM_PROMPT, fast_prompt, max_retries=2, timeout=55
            )

            locked_answer = None
            if _valid_pack(res_fast):
                locked_answer = str(res_fast.get("answer") or "").strip()
                _prog(f"Stage 2a OK — answer: {locked_answer[:80]}")
            else:
                _prog("Stage 2a timed out / empty — trying one more compact pass...")
                res_fast = self.gemini.generate_json_with_retry(
                    SOLUTION_SYSTEM_PROMPT, fast_prompt, max_retries=1, timeout=70
                )
                if _valid_pack(res_fast):
                    locked_answer = str(res_fast.get("answer") or "").strip()
                    _prog(f"Stage 2a OK (retry) — answer: {locked_answer[:80]}")

            # ——— Phase B: expand to teaching pack (answer locked) ———
            res = None
            if locked_answer:
                _prog("Stage 2b: Expanding teaching pack around locked answer...")
                expand_prompt = {
                    "subject": subject,
                    "topic": topic,
                    "questionText": q_text,
                    "images": images,
                    "lockedAnswer": locked_answer,
                    "seed": {
                        "concept": res_fast.get("concept"),
                        "formula": res_fast.get("formula"),
                        "steps": res_fast.get("steps"),
                        "equationBeats": res_fast.get("equationBeats"),
                    },
                    "instruction": (
                        f"Build a FULL Remotion teaching solution pack. "
                        f"LOCKED final answer (do not change): {locked_answer}. "
                        "Fill concept, teachingGoal, given, find, intuition, formula, "
                        "steps (4-6), equationBeats, answer, answerPlain, keyTakeaway, "
                        "commonMistake, visualConcept, simulation, teachingDocument "
                        "(layout fbd for physics wire/loop; scheme/mcq for organic). "
                        "Keep JSON moderate size."
                    ),
                }
                res = self.gemini.generate_json_with_retry(
                    SOLUTION_SYSTEM_PROMPT, expand_prompt, max_retries=2, timeout=75
                )
                if not _valid_pack(res):
                    # Use fast pack as candidate — enrich will fill gaps
                    _prog("Stage 2b expand failed — using fast pack as solution.")
                    res = res_fast
                else:
                    # Force locked answer
                    res["answer"] = locked_answer
                    if not res.get("answerPlain"):
                        res["answerPlain"] = str(res_fast.get("answerPlain") or locked_answer)
            else:
                # Last resort: one medium full solve (still capped)
                _prog("Stage 2 fallback: one medium full solve (75s)...")
                full_prompt = {
                    "subject": subject,
                    "topic": topic,
                    "questionText": q_text,
                    "images": images,
                    "instruction": (
                        f"Solve THIS {subject} question. Return teaching pack JSON with "
                        "real answer (option letter if MCQ). Keep response under ~3KB."
                    ),
                }
                res = self.gemini.generate_json_with_retry(
                    SOLUTION_SYSTEM_PROMPT, full_prompt, max_retries=1, timeout=75
                )

            if _valid_pack(res):
                q_blob = f"{q_text} {subject} {topic}".lower()
                concept = str(res.get("concept", "")).lower()
                sim = str((res.get("simulation") or {}).get("type", "")).lower()
                chemistryish = any(
                    k in q_blob
                    for k in ("chemistry", "molecule", "orbital", "hybrid", "bond", "organic", "inorganic", "mole", "acid")
                )
                projectileish = "projectile" in concept or sim == "projectile"
                if chemistryish and projectileish:
                    res["simulation"] = {"type": "none", "params": {}, "describe": ""}
                candidate = enrich_solution(
                    res, question_data, images=images, gemini_client=self.gemini
                )
            else:
                ai_fail_reason = (
                    "MixRoute timed out on Stage 2 (magnetism/figure solve). "
                    "API hung — retry generation; if it keeps failing, check MixRoute quota/key."
                )
        else:
            ai_fail_reason = "Gemini/MixRoute not configured (offline)."

        if candidate is None:
            # Do NOT feed placeholder "Requires AI..." into verifier — fail clearly.
            if self.gemini.is_live():
                return {
                    "error": "SOLUTION_AI_FAILED",
                    "reason": ai_fail_reason
                    or "AI solve failed after retries. Please regenerate the video.",
                    "concept": "AI solve failed",
                    "steps": [],
                    "answer": "",
                }
            candidate = enrich_solution(
                self._offline_fallback(question_data),
                question_data,
                images=images,
                gemini_client=self.gemini,
            )

        # ——— HARD GATE: verify before video ———
        gate = verify_and_gate(question_data, candidate, gemini_client=self.gemini, images=images)
        if gate.get("ok") and gate.get("solution"):
            out = enrich_solution(
                gate["solution"], question_data, images=images, gemini_client=self.gemini
            )
            out["verification"] = {
                "ok": True,
                "confidence": (gate.get("report") or {}).get("confidence"),
                "source": gate.get("source"),
                "report": gate.get("report"),
            }
            print(f"[SolutionVerifier] PASSED (source={gate.get('source')})")
            return out

        # One repair attempt with critic feedback
        if self.gemini.is_live() and gate.get("report"):
            print("[SolutionVerifier] FAILED - attempting repair solve with critique...")
            repair_prompt = {
                "subject": subject,
                "topic": topic,
                "questionText": q_text,
                "images": images,
                "previousWrongAnswer": candidate.get("answer"),
                "verifierReport": gate.get("report"),
                "instruction": (
                    "Your previous answer was REJECTED as incorrect or unverified. "
                    "Re-solve from scratch carefully. Fix the mistakes listed. "
                    "Return a full correct solution pack JSON with diagramSpec."
                ),
            }
            repaired = self.gemini.generate_json_with_retry(
                SOLUTION_SYSTEM_PROMPT, repair_prompt, max_retries=2, timeout=120
            )
            if repaired and not repaired.get("error"):
                gate2 = verify_and_gate(
                    question_data,
                    enrich_solution(
                        repaired, question_data, images=images, gemini_client=self.gemini
                    ),
                    gemini_client=self.gemini,
                    images=images,
                )
                if gate2.get("ok") and gate2.get("solution"):
                    out = enrich_solution(
                        gate2["solution"], question_data, images=images, gemini_client=self.gemini
                    )
                    out["verification"] = {
                        "ok": True,
                        "confidence": (gate2.get("report") or {}).get("confidence"),
                        "source": "repaired+" + str(gate2.get("source")),
                        "report": gate2.get("report"),
                    }
                    print("[SolutionVerifier] PASSED after repair")
                    return out

        reason = gate.get("reason") or "Solution could not be verified as correct."
        print(f"[SolutionVerifier] BLOCKED: {reason}")
        return {
            "error": "SOLUTION_UNVERIFIED",
            "reason": reason,
            "answer": candidate.get("answer"),
            "candidate": candidate,
            "verification": {"ok": False, "report": gate.get("report")},
            "concept": candidate.get("concept") or "Unverified",
            "steps": [],
        }

    def _offline_fallback(self, question_data):
        subject = question_data.get("subject", "Physics")
        q_text = question_data.get("questionText", "")
        topic = question_data.get("topic", f"{subject} Problem")
        sim = _guess_simulation(q_text, topic)
        nums = _extract_numbers(q_text)
        if nums and sim["type"] == "projectile":
            sim["params"].update(nums)

        if sim["type"] == "projectile":
            import math

            u = float(sim["params"].get("u", 20))
            theta = float(sim["params"].get("theta", 45))
            g = float(sim["params"].get("g", 9.8))
            R = (u * u * math.sin(math.radians(2 * theta))) / g
            T = (2 * u * math.sin(math.radians(theta))) / g
            return {
                "concept": "Projectile Motion",
                "teachingGoal": "Understand why the path is a parabola and how to calculate range.",
                "given": [f"u = {u} m/s", f"θ = {theta}°", f"g = {g} m/s²"],
                "find": "Range R",
                "intuition": (
                    "When something is thrown at an angle, it has forward speed and upward speed. "
                    "Gravity only changes the upward part, so the path becomes a curve — a parabola."
                ),
                "visualConcept": {
                    "bestEngine": "HYBRID",
                    "primaryVisual": "projectile",
                    "why": "Seeing the launch, vectors, and curve makes the formulas obvious.",
                    "mustShow": ["trajectory", "ux", "uy", "gravity", "range_marker"],
                },
                "simulation": sim,
                "formula": "R = u² sin(2θ) / g",
                "equationBeats": [
                    {
                        "id": "eq1",
                        "label": "Formula",
                        "latex": "R = u² sin(2θ) / g",
                        "say": "Range depends on launch speed and angle.",
                    },
                    {
                        "id": "eq2",
                        "label": "Substitute",
                        "latex": f"R = ({u})² sin({2*theta}°) / {g}",
                        "say": "Substitute the given values.",
                    },
                    {
                        "id": "eq3",
                        "label": "Simplify",
                        "latex": f"R = {u*u} × sin({2*theta}°) / {g}",
                        "say": "Square the speed and evaluate the sine term.",
                    },
                    {
                        "id": "eq4",
                        "label": "Answer",
                        "latex": f"R = {R:.2f} m",
                        "say": f"The range is {R:.2f} meters. Flight time is about {T:.2f} seconds.",
                    },
                ],
                "steps": [
                    {
                        "id": "step_01",
                        "title": "Split velocity",
                        "explanation": "Resolve velocity into horizontal and vertical components.",
                        "formula": "ux = u cosθ , uy = u sinθ",
                        "calculation": f"ux = {u} cos{theta}° , uy = {u} sin{theta}°",
                        "visualCue": "show_velocity_components",
                        "say": "First split velocity into ux and uy.",
                    },
                    {
                        "id": "step_02",
                        "title": "Gravity effect",
                        "explanation": "ux stays constant; uy changes because of gravity.",
                        "formula": "ay = -g",
                        "calculation": f"ay = -{g} m/s²",
                        "visualCue": "animate_gravity",
                        "say": "Gravity pulls only vertically downward.",
                    },
                    {
                        "id": "step_03",
                        "title": "Range formula",
                        "explanation": "Range is horizontal speed times time of flight.",
                        "formula": "R = u² sin(2θ) / g",
                        "calculation": f"R = {R:.2f} m",
                        "visualCue": "draw_trajectory",
                        "say": "Multiply horizontal motion by flight time to get range.",
                    },
                ],
                "answer": f"{R:.2f} m",
                "answerPlain": f"The range is {R:.2f} meters.",
                "keyTakeaway": "For a given speed, range is maximum at 45°.",
                "commonMistake": "Students forget sin(2θ) and use sinθ only.",
                "explanation": "Projectile motion combines constant horizontal velocity with accelerated vertical motion.",
            }

        return {
            "concept": f"{subject} Problem Analysis",
            "teachingGoal": f"Understand and solve: {topic}",
            "given": ["Values stated in the question"],
            "find": "Required answer from the question",
            "intuition": "We will identify the idea, show a clear visual, then solve step by step.",
            "visualConcept": {
                "bestEngine": "2D",
                "primaryVisual": "equation_board",
                "why": "Clear progressive explanation helps students follow every step.",
                "mustShow": ["given", "steps", "answer"],
            },
            "simulation": sim,
            "formula": "",
            "equationBeats": [],
            "steps": [
                {
                    "id": "step_01",
                    "title": "Need AI",
                    "explanation": "Connect Gemini API for a full verified solution pack.",
                    "formula": "",
                    "calculation": "",
                    "visualCue": "highlight",
                    "say": "A live AI connection is needed for the complete solution.",
                }
            ],
            "answer": "Requires AI connection for accurate solution",
            "answerPlain": "Please configure Gemini to generate the full solution.",
            "keyTakeaway": "Always start from the governing concept, then calculate.",
            "commonMistake": "Jumping to the answer without understanding the setup.",
            "explanation": "Connect to Gemini API for step-by-step solution generation.",
        }
