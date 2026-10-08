"""Reusable teaching animation — no per-question hardcode.

Builds timed visual beats from VisualPack + solution steps so Remotion can:
  - reveal molecules one-by-one along a reaction path
  - sync narration (visualBeats) with focus/highlight
  - drop invalid SMILES before render (avoids broken boards)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Minimal SMILES sanity (not full chemistry — catches empty/garbage before video)
_SMILES_OK = re.compile(r"^[A-Za-z0-9@+\-\[\]()=#\\/.%]+$")


def validate_smiles(smiles: str) -> bool:
    s = (smiles or "").strip()
    if len(s) < 2 or len(s) > 512:
        return False
    if not _SMILES_OK.match(s):
        return False
    # Must contain at least one letter (element symbol)
    if not re.search(r"[A-Za-z]", s):
        return False
    return True


def sanitize_molecules(molecules: List[dict]) -> List[dict]:
    out: List[dict] = []
    seen = set()
    for m in molecules or []:
        if not isinstance(m, dict):
            continue
        sm = str(m.get("smiles") or "").strip()
        if not validate_smiles(sm):
            continue
        mid = str(m.get("id") or f"mol_{len(out)}").strip()
        if mid in seen:
            mid = f"{mid}_{len(out)}"
        seen.add(mid)
        out.append(
            {
                "id": mid,
                "smiles": sm,
                "label": m.get("label") or mid,
                "role": m.get("role") or "option",
                "correct": bool(m.get("correct")),
                "callout": m.get("callout"),
            }
        )
    return out


def _path_molecules(molecules: List[dict]) -> List[dict]:
    """Teaching order: reactant → intermediates → products; else non-options in order."""
    role_order = ("reactant", "intermediate", "product")
    path: List[dict] = []
    for role in role_order:
        path.extend([m for m in molecules if (m.get("role") or "").lower() == role])
    if len(path) >= 2:
        return path[:6]
    non_opt = [
        m
        for m in molecules
        if (m.get("role") or "").lower() not in ("option",)
        and not str(m.get("id") or "").lower().startswith("opt")
    ]
    if len(non_opt) >= 2:
        return non_opt[:6]
    return molecules[:6]


def build_organic_animation_sequence(pack: dict, solution: Optional[dict] = None) -> List[dict]:
    """
    Auto timeline for MoleculeBoard — derived from pack molecules + reactionSteps + solution steps.
    Each beat: { at, see, focusId, revealIndex, say, callout }
    """
    solution = solution or {}
    molecules = pack.get("molecules") or []
    path = _path_molecules(molecules)
    rxn = pack.get("reactionSteps") or []
    step_says = [
        str(s.get("say") or "").strip()
        for s in (solution.get("steps") or [])
        if isinstance(s, dict)
    ]
    eq_says = [
        str(e.get("say") or "").strip()
        for e in (solution.get("equationBeats") or [])
        if isinstance(e, dict)
    ]
    notes = [str(n).strip() for n in (pack.get("teachNotes") or []) if str(n).strip()]

    beats: List[dict] = []
    if not path:
        return beats

    t = 0.0
    beats.append(
        {
            "at": t,
            "see": f"mol_{path[0]['id']}",
            "focusId": path[0]["id"],
            "revealIndex": 0,
            "say": step_says[0]
            or notes[0]
            if notes
            else f"Pehle {path[0].get('label') or 'reactant'} ka structure dekho.",
            "callout": path[0].get("callout"),
        }
    )

    for i in range(1, len(path)):
        t += 5.0
        reagent = ""
        if i - 1 < len(rxn):
            reagent = str(rxn[i - 1].get("reagents") or "").strip()
        say = step_says[i] if i < len(step_says) else ""
        if not say and i - 1 < len(eq_says):
            say = eq_says[i - 1]
        if not say and reagent:
            say = f"Ab yeh step: {reagent}"
        if not say:
            say = f"Phir {path[i].get('label') or 'product'} ban'ta hai."
        beats.append(
            {
                "at": t,
                "see": f"mol_{path[i]['id']}",
                "focusId": path[i]["id"],
                "revealIndex": i,
                "say": say,
                "callout": path[i].get("callout"),
            }
        )

    # MCQ options beat
    options = [m for m in molecules if (m.get("role") or "").lower() == "option"]
    if options:
        t += 5.0
        beats.append(
            {
                "at": t,
                "see": "mol_options",
                "focusId": options[0].get("id"),
                "revealIndex": len(path) - 1,
                "say": "Ab options A se D compare karte hain.",
            }
        )

    t += 4.0
    beats.append(
        {
            "at": t,
            "see": "mol_answer",
            "focusId": path[-1]["id"] if path else None,
            "revealIndex": len(path) - 1,
            "say": str(solution.get("answerPlain") or solution.get("answer") or "Final answer.")[:220],
        }
    )
    return beats


def _flow_nodes_edges(pack: dict) -> tuple:
    fg = pack.get("flowGraph") or {}
    nodes = fg.get("nodes") or []
    edges = fg.get("edges") or []
    return nodes, edges


def _bfs_node_order(nodes: List[dict], edges: List[dict]) -> List[str]:
    ids = [str(n.get("id")) for n in nodes if n.get("id")]
    if not ids:
        return []
    inc = {i: 0 for i in ids}
    for e in edges:
        t = str(e.get("target") or "")
        if t in inc:
            inc[t] += 1
    roots = [i for i in ids if inc[i] == 0] or [ids[0]]
    order: List[str] = []
    seen = set()
    q = list(roots)
    while q:
        nid = q.pop(0)
        if nid in seen:
            continue
        seen.add(nid)
        order.append(nid)
        for e in edges:
            if str(e.get("source")) == nid:
                tgt = str(e.get("target") or "")
                if tgt not in seen:
                    q.append(tgt)
    for i in ids:
        if i not in seen:
            order.append(i)
    return order


def build_flow_animation_sequence(pack: dict, solution: Optional[dict] = None) -> List[dict]:
    """Timed beats for React Flow — one node reveal per step."""
    solution = solution or {}
    nodes, edges = _flow_nodes_edges(pack)
    if not nodes:
        return []
    by_id = {str(n.get("id")): n for n in nodes if n.get("id")}
    order = _bfs_node_order(nodes, edges)
    step_says = [
        str(s.get("say") or "").strip()
        for s in (solution.get("steps") or [])
        if isinstance(s, dict)
    ]
    notes = [str(n).strip() for n in (pack.get("teachNotes") or []) if str(n).strip()]
    beats: List[dict] = []
    t = 0.0
    for i, nid in enumerate(order):
        node = by_id.get(nid) or {}
        label = str(node.get("label") or nid)
        say = step_says[i] if i < len(step_says) else ""
        if not say and i < len(notes):
            say = notes[i]
        if not say:
            say = f"Ab yeh step dekho: {label[:120]}"
        beats.append(
            {
                "at": t,
                "see": f"flow_{nid}",
                "focusId": nid,
                "revealIndex": i,
                "say": say,
            }
        )
        t += 5.5
    beats.append(
        {
            "at": t,
            "see": "flow_answer",
            "focusId": order[-1] if order else None,
            "revealIndex": len(order) - 1,
            "say": str(solution.get("answerPlain") or solution.get("answer") or "Final answer.")[:220],
        }
    )
    return beats


def attach_teaching_timeline(pack: dict, solution: dict) -> dict:
    """Sanitize SMILES + attach animationSequence for organic / flow packs."""
    if not isinstance(pack, dict):
        return pack
    domain = str(pack.get("domain") or "").lower()
    if domain == "organic":
        pack["molecules"] = sanitize_molecules(pack.get("molecules") or [])
        if pack["molecules"]:
            pack["animationSequence"] = build_organic_animation_sequence(pack, solution)
        else:
            pack["animationSequence"] = []
    elif domain == "flow":
        pack["molecules"] = []
        pack["diagramSpec"] = None
        fg = pack.get("flowGraph")
        if isinstance(fg, dict) and (fg.get("nodes") or []):
            pack["animationSequence"] = build_flow_animation_sequence(pack, solution)
        else:
            pack["animationSequence"] = []
    return pack


def beats_for_lesson_scenes(pack: dict, solution: dict) -> List[dict]:
    """Convert animationSequence to lesson visualBeats (see/say/at)."""
    seq = pack.get("animationSequence") or []
    if seq:
        default_see = "flow_main" if str(pack.get("domain") or "").lower() == "flow" else "mol_main"
        return [
            {
                "at": float(b.get("at") or 0),
                "see": b.get("see") or default_see,
                "say": b.get("say") or "",
            }
            for b in seq
            if b.get("say")
        ]
    return []


_SHALLOW_PHASE = re.compile(
    r"(?i)^(first[,.]?\s|then[,.]?\s|next[,.]?\s|followed\s|and finally|figure part|"
    r"the (input|output|connecting|current|first|second)|pehle figure)"
)


def _labels_for_groups(elements: List[dict], groups: List[str]) -> List[str]:
    want = {str(g) for g in (groups or [])}
    labs: List[str] = []
    for e in elements or []:
        if not isinstance(e, dict):
            continue
        if want and str(e.get("group") or "main") not in want:
            continue
        for key in ("label", "text"):
            v = e.get(key)
            if not v:
                continue
            s = str(v).strip()
            # Skip internal ids like input_line / conn_L1_down
            if not s or "_" in s and " " not in s and len(s) > 12:
                continue
            if s not in labs:
                labs.append(s[:40])
        if len(labs) >= 3:
            break
    return labs


def _human_part_name(phase: dict, labs: List[str], index: int) -> str:
    if labs:
        return ", ".join(labs)
    pid = str(phase.get("id") or "").replace("_", " ").strip()
    # Soften technical ids
    soft = {
        "input path": "left side wires",
        "output path": "right side wires",
        "connection show": "connecting wires",
        "inductor1 show": "pehla inductor",
        "inductor2 show": "doosra inductor",
        "current flow": "current direction",
    }
    key = pid.lower()
    if key in soft:
        return soft[key]
    if pid and not pid.startswith("figure"):
        return pid
    return f"part {index + 1}"


def deepen_diagram_phases(spec: dict, solution: dict) -> dict:
    """Upgrade thin phase.say lines into teachable Hinglish (generic, any figure)."""
    if not isinstance(spec, dict):
        return spec
    out = dict(spec)
    elements = list(out.get("elements") or [])
    phases = list(out.get("phases") or [])
    if not phases:
        return out

    # Idempotent: strip prior auto teaching tails before rebuilding
    phases = [
        p
        for p in phases
        if isinstance(p, dict) and str(p.get("id") or "") not in ("figure_meaning", "figure_formula")
    ]

    intuition = str(solution.get("intuition") or "").strip()
    formula = str(solution.get("formula") or "").strip()
    find = str(solution.get("find") or "").strip()
    eq_beats = [e for e in (solution.get("equationBeats") or []) if isinstance(e, dict)]

    deepened = []
    n = len(phases)
    for i, p in enumerate(phases):
        p = dict(p)
        raw_say = str(p.get("say") or "").strip()
        say = raw_say
        labs = _labels_for_groups(elements, p.get("groups") or [])
        part = _human_part_name(p, labs, i)
        shallow = (
            len(say) < 70
            or bool(_SHALLOW_PHASE.search(say))
            or say.lower().endswith(("is shown.", "is added.", "are shown."))
            or "highlight ho raha" in say.lower()
            or "input_line" in say
            or "conn_" in say
        )
        if shallow:
            # Keep nouns from original stub (L1, L2, current…) — just teach in Hinglish
            core = re.sub(
                r"(?i)^(first|then|next|followed by|and finally)[,.]?\s*",
                "",
                raw_say,
            ).strip()
            core = re.sub(r"(?i)\bis (shown|added)\.?$", "", core).strip(" .")
            core = re.sub(r"(?i)^the\s+", "", core).strip()
            core = re.sub(r"(?i)^first\s+", "pehla ", core)
            core = re.sub(r"(?i)^second\s+", "doosra ", core)
            # "current flow 'I' is indicated at various points" → shorter
            core = re.sub(
                r"(?i)\s+is indicated at various points\.?$",
                "",
                core,
            ).strip()
            if not core or len(core) < 8:
                core = part
            if i == 0:
                say = (
                    f"Pehle figure ka base carefully dekho — {core}. "
                    "Yahan se poora diagram step-by-step build hoga."
                )
            elif i == n - 1:
                tip = intuition.split(".")[0].strip() if intuition else ""
                say = (
                    f"Ab {core} clearly mark hai. "
                    + (f"{tip}." if tip else "Ab is figure se concept clear karte hain.")
                )
            else:
                say = (
                    f"Ab {core} highlight hota hai. "
                    "Is part ko dhyan se dekho — yahi se next step clear hoga."
                )
        p["say"] = say
        if not p.get("see"):
            p["see"] = f"diagram_{p.get('id') or i}"
        deepened.append(p)

    all_groups = list(
        {str(e.get("group") or "main") for e in elements if isinstance(e, dict)}
    )[:8] or ["main"]

    if intuition:
        deepened.append(
            {
                "id": "figure_meaning",
                "groups": all_groups,
                "see": "diagram_marks",
                "say": intuition[:220],
            }
        )
    eq_say = ""
    if eq_beats:
        eq_say = str(eq_beats[0].get("say") or "").strip()
    if not eq_say and formula:
        eq_say = (
            f"Is figure se formula clear hota hai: {formula}. "
            + (f"Humein find karna hai: {find}." if find else "")
        )
    if eq_say:
        deepened.append(
            {
                "id": "figure_formula",
                "groups": all_groups,
                "see": "diagram_tip",
                "say": eq_say[:220],
            }
        )

    out["phases"] = deepened
    return out


def build_figure_scene(solution: dict, *, deepen: bool = True) -> dict:
    """DIAGRAM scene with phase-timed beats + concept narration (any subject)."""
    raw = dict(solution.get("diagramSpec") or {})
    spec = deepen_diagram_phases(raw, solution) if deepen else raw
    if isinstance(solution.get("diagramSpec"), dict):
        solution["diagramSpec"] = spec

    phases = spec.get("phases") or []
    title = spec.get("title") or solution.get("concept") or "Question figure"
    n = max(len(phases), 1)
    # ~3.5s per phase, clamp 20–32s
    duration = float(min(32.0, max(20.0, 3.5 * n + 2.0)))
    step = (duration - 1.5) / n

    beats = []
    for i, p in enumerate(phases):
        beats.append(
            {
                "at": round(i * step, 1),
                "see": p.get("see") or f"diagram_{p.get('id') or i}",
                "say": p.get("say") or f"Figure part {i + 1}",
            }
        )

    # Narration: intro + build + meaning (avoid dumping every beat twice)
    build_says = [str(b["say"]) for b in beats if "figure_meaning" not in str(b.get("see")) and "diagram_tip" not in str(b.get("see"))]
    meaning = next((b["say"] for b in beats if b.get("see") in ("diagram_marks", "diagram_tip")), "")
    narration = (
        f"Chalo question wale figure ko dheere-dheere samajhte hain: {title}. "
        + " ".join(build_says[:4])[:380]
    )
    if meaning:
        narration = f"{narration} {str(meaning)[:180]}"

    bullets = [str(p.get("say") or "")[:90] for p in phases[:5] if p.get("say")]
    return {
        "id": "scene_question_figure",
        "type": "DIAGRAM",
        "visualMode": "2D",
        "engine": "fbd_diagram",
        "boardLayout": "fbd",
        "duration": duration,
        "learningGoal": f"Figure ko clearly samajhna: {title}",
        "narration": narration[:700],
        "onScreen": {
            "title": title,
            "subtitle": "Figure step-by-step",
            "given": solution.get("given") or [],
            "find": solution.get("find") or "",
            "bullets": bullets or ["Figure rebuild"],
            "equations": [solution.get("formula")] if solution.get("formula") else [],
            "answer": None,
        },
        "visualBeats": beats,
        "visuals": ["diagram_spec", "fbd", "question_figure"],
        "animations": ["draw", "fade", "highlight"],
        "actions": [
            {"action": "CREATE", "target": "FbdEngine"},
            {"action": "SIMULATE", "simulation": "diagram", "params": {"useDiagramSpec": True}},
        ],
    }


def question_anchor_from_solution(solution: dict) -> Optional[Dict[str, str]]:
    """Starting structure from the question — for HOOK so video relates to the paper figure."""
    solution = solution or {}
    td = solution.get("teachingDocument") or {}
    stages = [s for s in (td.get("stages") or []) if isinstance(s, dict)]
    for s in stages:
        role = str(s.get("role") or "").lower()
        sm = str(s.get("smiles") or "").strip()
        if role in ("start", "reactant") and validate_smiles(sm):
            return {
                "smiles": sm,
                "label": str(s.get("label") or "Starting material")[:80],
            }
    # First non-option molecule with SMILES
    for s in stages:
        kind = str(s.get("kind") or "").lower()
        role = str(s.get("role") or "").lower()
        sm = str(s.get("smiles") or "").strip()
        if role == "option" or kind == "option":
            continue
        if validate_smiles(sm):
            return {
                "smiles": sm,
                "label": str(s.get("label") or "Question figure")[:80],
            }
    pack = solution.get("visualPack") or {}
    for m in pack.get("molecules") or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").lower()
        sm = str(m.get("smiles") or "").strip()
        if role in ("reactant", "start") and validate_smiles(sm):
            return {
                "smiles": sm,
                "label": str(m.get("label") or "Starting material")[:80],
            }
    for m in pack.get("molecules") or []:
        if not isinstance(m, dict):
            continue
        if str(m.get("role") or "").lower() == "option":
            continue
        sm = str(m.get("smiles") or "").strip()
        if validate_smiles(sm):
            return {
                "smiles": sm,
                "label": str(m.get("label") or "Question figure")[:80],
            }
    return None


def expand_given_chips(given: List[str]) -> List[str]:
    """Split packed reagent lists into readable chips — never one giant truncated line."""
    out: List[str] = []
    for g in given or []:
        t = str(g).strip()
        if not t:
            continue
        # "Reagents: (1) O3... (2) Ag2O... (3) NaBH4 (4) H+"
        if re.search(r"\(\s*\d+\s*\)", t) and len(t) > 48:
            prefix = ""
            m = re.match(r"^([^:]{0,24}:)\s*", t)
            body = t
            if m:
                prefix = m.group(1).strip()
                body = t[m.end() :].strip()
            parts = re.split(r"(?=\(\s*\d+\s*\))", body)
            parts = [p.strip(" ,;") for p in parts if p.strip(" ,;")]
            if len(parts) >= 2:
                for i, p in enumerate(parts):
                    if i == 0 and prefix and not p.lower().startswith("reagent"):
                        out.append(f"{prefix} {p}".strip())
                    else:
                        out.append(p)
                continue
        # Long comma lists
        if len(t) > 70 and t.count(",") >= 2 and "→" not in t:
            chunks = [c.strip() for c in t.split(",") if c.strip()]
            if len(chunks) >= 3:
                out.extend(chunks)
                continue
        out.append(t)
    # Dedupe preserve order, cap chips
    seen = set()
    clean: List[str] = []
    for x in out:
        key = x.lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append(x)
        if len(clean) >= 10:
            break
    return clean


def build_question_scene(solution: dict, question_data: Optional[dict] = None) -> dict:
    """HOOK: properly explain the question text, givens, find, and traps."""
    qd = question_data or {}
    q_text = str(
        qd.get("questionText")
        or solution.get("questionText")
        or solution.get("question")
        or ""
    ).strip()
    given = expand_given_chips(
        [str(g).strip() for g in (solution.get("given") or []) if str(g).strip()]
    )
    find = str(solution.get("find") or "").strip()
    concept = str(solution.get("concept") or qd.get("topic") or "is question").strip()
    goal = str(solution.get("teachingGoal") or "").strip()
    options = solution.get("options") or qd.get("options") or []
    if isinstance(options, dict):
        options = [f"{k}) {v}" for k, v in options.items()]
    options = [str(o).strip() for o in options if str(o).strip()][:6]

    beats: List[dict] = [
        {
            "at": 0.0,
            "see": "title_card",
            "say": f"Welcome students! Aaj hum {concept} wala question properly samjhenge.",
        }
    ]
    anchor = question_anchor_from_solution(solution)

    t = 3.5
    if q_text:
        if anchor:
            beats.append(
                {
                    "at": t,
                    "see": "question_figure",
                    "say": (
                        f"Question me yeh starting structure di hai: {anchor['label']}. "
                        "Isko paper wale figure se match karke dekho."
                    ),
                }
            )
            t += 4.0
        beats.append(
            {
                "at": t,
                "see": "question_text",
                # Voice: short. Full text + figure on screen.
                "say": (
                    "Ab question text carefully padho - jo structure screen pe hai, "
                    "usi reactant se product A nikalna hai."
                    if anchor
                    else "Ab question screen pe carefully padho - har line samajhna zaroori hai."
                ),
            }
        )
        t += max(5.0, min(10.0, len(q_text) / 22.0))
    elif goal:
        beats.append(
            {
                "at": t,
                "see": "question_text",
                "say": f"Question ka goal yeh hai: {goal[:200]}",
            }
        )
        t += 4.0

    try:
        from tts.pronounce import speak_given_item
    except Exception:  # pragma: no cover
        speak_given_item = lambda x: str(x)  # noqa: E731

    for g in given[:5]:
        spoken_g = speak_given_item(g)
        # Avoid dumping raw chem equations into voiceover
        raw = str(g)
        if (
            len(spoken_g) > 80
            or re.search(r"[=→↔]", raw)
            or (re.search(r"R\d", raw, re.I) and len(raw) > 12)
        ):
            spoken_g = "yeh given reagent ya condition"
        beats.append(
            {
                "at": round(t, 1),
                "see": "given_chips",
                "say": f"Given hai — {spoken_g}. Isko note kar lo.",
            }
        )
        t += 2.6

    # Find target only — never spoil the answer value on HOOK
    find_clean = find
    for bad in ("answer", "(A)", "(B)", "(C)", "(D)", "lactone", "product is"):
        if bad.lower() in find_clean.lower() and len(find_clean) > 40:
            find_clean = "final product (A)" if "product" in find.lower() else "required answer"
            break
    if find_clean:
        beats.append(
            {
                "at": round(t, 1),
                "see": "find_badge",
                "say": (
                    f"Humein find karna hai: {find_clean}. "
                    "Ab next scenes mein step-by-step solve karenge — abhi answer nahi."
                ),
            }
        )
        t += 3.5

    # Options labels only (A/B/C/D) — never full option text that may contain answer
    if options:
        labels = []
        for i, opt in enumerate(options[:4]):
            m = re.match(r"^\s*[\(\[]?([A-D])[\)\].:]?", str(opt), re.I)
            labels.append(m.group(1).upper() if m else chr(ord("A") + i))
        beats.append(
            {
                "at": round(t, 1),
                "see": "options_list",
                "say": f"Options hain {', '.join(labels)}. Sahi option baad mein choose karenge.",
            }
        )
        t += 2.5

    # Soft goal only — skip long commonMistake (often spoils method/answer)
    if goal and q_text:
        beats.append(
            {
                "at": round(t, 1),
                "see": "goal_note",
                "say": "Chalo ab figure aur steps se dheere-dheere samajhte hain.",
            }
        )
        t += 2.5

    duration = round(float(min(28.0, max(14.0, t + 1.0))), 1)
    narration = " ".join(str(b.get("say") or "") for b in beats)[:650]

    return {
        "id": "scene_01",
        "type": "HOOK",
        "visualMode": "2D",
        "engine": "remotion_2d",
        "duration": duration,
        "learningGoal": "Sirf question + given + find — answer spoil nahi",
        "narration": narration,
        "onScreen": {
            "title": concept,
            "subtitle": "Pehle sirf question samajhte hain",
            "given": given[:10],
            "find": find_clean,
            # Empty: HOOK must NOT dump formulas / answer / full steps on screen
            "bullets": [],
            "equations": [],
            "equationBeats": [],
            "answer": None,
            "questionText": q_text,  # full text — Remotion wraps, no "..."
            "questionAnchor": anchor,  # start SMILES — relate video to paper figure
            "progressiveReveal": True,
            "hideAnswer": True,
            "hideFormulas": True,
        },
        "visualBeats": beats,
        "visuals": ["title", "given_chips", "question", "question_figure"],
        "animations": ["fade_in", "highlight"],
        "actions": [
            {"action": "CREATE", "target": "TitleCard"},
            {"action": "FADE_IN", "target": "question_text"},
            {"action": "HIGHLIGHT", "target": "given_chips"},
            {"action": "HIGHLIGHT", "target": "find_badge"},
        ],
        "force3D": False,
    }


def enrich_question_scenes(
    plan: dict, solution: dict, question_data: Optional[dict] = None
) -> dict:
    """Ensure HOOK truly explains the question (not a thin welcome stub)."""
    plan = dict(plan or {})
    solution = dict(solution or {})
    qd = question_data or {}

    # Persist question text on solution for Remotion / later scenes
    q_text = str(
        qd.get("questionText")
        or solution.get("questionText")
        or solution.get("question")
        or ""
    ).strip()
    if q_text:
        solution["questionText"] = q_text

    rich = build_question_scene(solution, qd)
    scenes = list(plan.get("scenes") or [])
    replaced = False
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        st = str(sc.get("type") or "").upper()
        if st not in ("HOOK", "INTRO"):
            continue
        if st == "INTRO" and i > 0:
            # only upgrade the first intro-like scene if no HOOK
            if any(str(x.get("type") or "").upper() == "HOOK" for x in scenes):
                continue
        beats = sc.get("visualBeats") or []
        says = " ".join(str(b.get("say") or "") for b in beats).lower()
        thin = (
            len(beats) <= 4
            or "welcome" in says and "given" not in says
            or str(sc.get("engine") or "") == "fbd_diagram"
            or "diagram_spec" in (sc.get("visuals") or [])
            or len(str(sc.get("narration") or "")) < 120
        )
        if st == "HOOK" or thin:
            keep_id = sc.get("id") or rich["id"]
            # Keep a warm custom welcome opener if already Hinglish-rich
            old_nar = str(sc.get("narration") or "").strip()
            merged = {**sc, **rich, "id": keep_id}
            if old_nar.startswith("Hello students") or old_nar.startswith("Welcome students"):
                # Prefer new fuller narration (includes given/find walkthrough)
                merged["narration"] = rich["narration"]
            scenes[i] = merged
            replaced = True
            break

    if not replaced:
        scenes.insert(0, rich)

    plan["scenes"] = scenes
    plan["solution"] = solution
    return plan


def enrich_figure_scenes(plan: dict, solution: dict) -> dict:
    """Replace thin DIAGRAM stubs with phase-rich teaching beats."""
    plan = dict(plan or {})
    solution = solution or {}
    spec = solution.get("diagramSpec") or {}
    if not (isinstance(spec, dict) and spec.get("elements")):
        return plan

    # Deepen once, then build scene from already-deepened phases
    solution["diagramSpec"] = deepen_diagram_phases(dict(spec), solution)
    rich = build_figure_scene(solution, deepen=False)

    scenes = list(plan.get("scenes") or [])
    replaced = False
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        st = str(sc.get("type") or "").upper()
        eng = str(sc.get("engine") or "")
        beats = sc.get("visualBeats") or []
        thin = (
            st == "DIAGRAM"
            or eng == "fbd_diagram"
            or "diagram_spec" in (sc.get("visuals") or [])
        ) and (
            len(beats) <= 3
            or any(
                str(b.get("say") or "").lower() in ("figure start", "important parts", "key highlight")
                for b in beats
            )
        )
        if st == "DIAGRAM" and (thin or eng in ("fbd_diagram", "remotion_2d", "")):
            keep_id = sc.get("id") or rich["id"]
            scenes[i] = {**sc, **rich, "id": keep_id}
            replaced = True
            break

    if not replaced:
        # Insert after hook if present
        insert_at = 1 if scenes else 0
        scenes.insert(insert_at, rich)

    # INTUITION on fbd: fake 3D tags OR stolen solve-step English → figure meaning beats
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        if str(sc.get("type") or "").upper() != "INTUITION":
            continue
        if str(sc.get("engine") or "") != "fbd_diagram":
            continue
        beats = sc.get("visualBeats") or []
        sees = " ".join(str(b.get("see") or "") for b in beats).lower()
        says = " ".join(str(b.get("say") or "") for b in beats).lower()
        bad = (
            "_3d" in sees
            or "coil_" in sees
            or "observe the circuit" in says
            or "compare the derived" in says
            or "for two coils with self-inductances" in says
        )
        if bad:
            # Prefer meaning/formula beats; else first build beats — retimed to this scene
            all_b = rich.get("visualBeats") or []
            meaning = [
                b
                for b in all_b
                if str(b.get("see") or "")
                in ("diagram_marks", "diagram_tip", "diagram_current_flow")
            ]
            fig_beats = meaning or all_b[:4]
            if fig_beats:
                dur = max(float(sc.get("duration") or 12), 14.0)
                step = (dur - 1.0) / max(len(fig_beats), 1)
                retimed = [
                    {
                        **b,
                        "at": round(j * step, 1),
                    }
                    for j, b in enumerate(fig_beats)
                ]
                nar = str(sc.get("narration") or "").strip()
                scenes[i] = {
                    **sc,
                    "narration": nar
                    or str(solution.get("intuition") or rich.get("narration") or "")[:500],
                    "visualBeats": retimed,
                    "visuals": ["diagram_spec", "fbd"],
                    "boardLayout": "fbd",
                    "engine": "fbd_diagram",
                    "force3D": False,
                    "duration": dur,
                }

    plan["scenes"] = scenes
    plan["solution"] = solution
    return plan
