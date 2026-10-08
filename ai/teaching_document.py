"""TeachingDocument — single IR for every question visual.

AI fills this; Python validates; Remotion animates by layout only.
No freehand bond SVG. No per-question React files.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .gemini import GeminiClient

try:
    from rdkit import Chem  # type: ignore

    _HAS_RDKIT = True
except ImportError:
    Chem = None  # type: ignore
    _HAS_RDKIT = False

_SMILES_RE = re.compile(r"^[A-Za-z0-9@+\-\[\]()=#\\/.%:]+$")


class Layout(str, Enum):
    scheme = "scheme"
    flowchart = "flowchart"
    plot = "plot"
    figure = "figure"
    mcq = "mcq"
    fbd = "fbd"


class StageKind(str, Enum):
    molecule = "molecule"
    label = "label"
    gas = "gas"
    option = "option"
    axis_mark = "axis_mark"
    bio_part = "bio_part"


class StageRole(str, Enum):
    start = "start"
    mid = "mid"
    end = "end"
    option = "option"
    reagent = "reagent"
    other = "other"


def _enum_token(v: Any) -> str:
    """Normalize Enum / 'StageRole.start' / 'stagerole.start' → bare value token."""
    if v is None:
        return ""
    if isinstance(v, Enum):
        return str(getattr(v, "value", v)).strip().lower()
    s = str(v).strip().lower()
    # str(SomeEnum.member) sometimes yields 'classname.member'
    if "." in s:
        s = s.rsplit(".", 1)[-1]
    return s


class Stage(BaseModel):
    id: str
    kind: StageKind = StageKind.label
    label: str = ""
    smiles: Optional[str] = None
    role: StageRole = StageRole.other
    correct: bool = False
    callout: Optional[str] = None

    @field_validator("id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        v = str(v or "").strip()
        if not v:
            raise ValueError("stage id required")
        return v[:64]

    @field_validator("kind", mode="before")
    @classmethod
    def _kind_ok(cls, v):
        if v is None:
            return StageKind.label
        if isinstance(v, StageKind):
            return v
        s = _enum_token(v)
        aliases = {
            "mol": "molecule",
            "structure": "molecule",
            "text": "label",
            "node": "label",
            "opt": "option",
            "mcq": "option",
        }
        s = aliases.get(s, s)
        try:
            return StageKind(s)
        except ValueError:
            return StageKind.label

    @field_validator("role", mode="before")
    @classmethod
    def _role_aliases(cls, v):
        """Accept synonyms + Enum members so parse never gets 'stagerole.start'."""
        if v is None:
            return StageRole.other
        if isinstance(v, StageRole):
            return v
        s = _enum_token(v)
        aliases = {
            "reactant": "start",
            "starting": "start",
            "intermediate": "mid",
            "intermediates": "mid",
            "product": "end",
            "final": "end",
            "products": "end",
            "opt": "option",
            "mcq": "option",
        }
        s = aliases.get(s, s)
        try:
            return StageRole(s)
        except ValueError:
            return StageRole.other


class Edge(BaseModel):
    source: str = Field(alias="from")
    target: str = Field(alias="to")
    label: str = ""
    id: Optional[str] = None

    model_config = {"populate_by_name": True}


class PlotSeries(BaseModel):
    id: str = "main"
    label: str = ""
    points: List[List[float]] = Field(default_factory=list)  # [[x,y], ...]
    color: str = "#38BDF8"


class PlotSpec(BaseModel):
    title: str = ""
    xLabel: str = "x"
    yLabel: str = "y"
    xMin: float = 0
    xMax: float = 10
    yMin: float = -10
    yMax: float = 10
    series: List[PlotSeries] = Field(default_factory=list)
    marks: List[Dict[str, Any]] = Field(default_factory=list)  # {id,x,y,label}


class FigureSpec(BaseModel):
    type: str = "custom"  # flower | amoeba | animal_cell | plant_cell | nephron | neuron | custom
    title: str = ""
    highlight: Optional[str] = None
    parts: List[Dict[str, str]] = Field(default_factory=list)


class AnswerSpec(BaseModel):
    option: Optional[str] = None
    plain: str = ""


class Beat(BaseModel):
    t: float = 0.0
    focus: Optional[str] = None
    say: str = ""


class TeachingDocument(BaseModel):
    layout: Layout
    title: str = "Figure"
    stages: List[Stage] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
    plot: Optional[PlotSpec] = None
    figure: Optional[FigureSpec] = None
    answer: AnswerSpec = Field(default_factory=AnswerSpec)
    beats: List[Beat] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


TEACHING_PROMPT = """You build a TeachingDocument for an educational video (DoubtSolve).

ONE schema for EVERY question. Remotion renders by layout only.
NEVER invent freehand SVG bond coordinates.
NEVER say to show the raw question photo.

Choose exactly ONE layout:

1) scheme — multi-step organic synthesis (arrows + reagents on paper, e.g. ibuprofen)
   stages: start molecule, each intermediate, final product (kind=molecule, SMILES required when known)
   edges: from→to with label = exact reagent text from the figure arrows
   options A–D as stages with role=option, kind=option|molecule
2) flowchart — branched inorganic / lettered boxes (A)(B)(C) with reagents on arrows
   stages: each box as label (or molecule if known); edges with reagent labels; match topology
3) plot — PE curve, RDF, energy levels
   fill plot.series points [[x,y],...] and marks; stages empty or axis marks only
4) figure — biology labeled (flower, amoeba, cell…)
   fill figure.type + parts[]; stages empty
5) mcq — structure / concept options only (no multi-step scheme)
   one stem stage optional + option stages
6) fbd — physics forces / rays as typed labels only (no freehand bonds)

Return ONLY JSON:
{
  "layout": "scheme|flowchart|plot|figure|mcq|fbd",
  "title": "short",
  "stages": [
    {"id":"s1","kind":"molecule","label":"Benzene","smiles":"c1ccccc1","role":"start","correct":false}
  ],
  "edges": [{"from":"s1","to":"s2","label":"reagent"}],
  "plot": null,
  "figure": null,
  "answer": {"option":"B","plain":"..."},
  "beats": [{"t":0,"focus":"s1","say":"Hinglish spoken beat"}]
}

Rules:
- scheme MUST include full chain (not only benzene + options).
- Copy reagents EXACTLY from the question arrows when present.
- SMILES REQUIRED for every stage with kind=molecule and every MCQ option (A–D).
  Empty smiles = broken video (UI shows empty boxes). Prefer valid Daylight SMILES.
- Never invent freehand bond coordinates — SMILES only.
- flowchart: no SMILES required; topology must match branches.
- plot: never draw bonds as freehand lines.
"""


FILL_SMILES_PROMPT = """You fill missing SMILES for an organic TeachingDocument.

Given the question (and image if any) + existing stages/edges, return ONLY JSON:
{"stages":[{"id":"s0","smiles":"..."},{"id":"optA","smiles":"..."}]}

Rules:
- Provide Daylight SMILES for EVERY stage id listed that is a molecule or option.
- Match the ACTUAL structures in the question figure (rings, Et groups, lactones, etc.).
- Include start reactant, intermediates if drawable, final product, and options A–D.
- No commentary. No freehand coordinates. SMILES strings only.
"""


def stages_missing_smiles(doc: TeachingDocument) -> List[Stage]:
    layout = doc.layout if isinstance(doc.layout, str) else doc.layout.value
    if layout not in ("scheme", "mcq"):
        return []
    missing: List[Stage] = []
    for s in doc.stages:
        role = s.role if isinstance(s.role, str) else (s.role.value if s.role else "")
        kind = s.kind if isinstance(s.kind, str) else (s.kind.value if s.kind else "")
        needs = (
            role in ("start", "mid", "end", "option")
            or kind in ("molecule", "option")
            or role == "option"
        )
        if needs and not validate_smiles(s.smiles):
            missing.append(s)
    return missing


def fill_missing_smiles(
    doc: TeachingDocument,
    question_data: dict,
    solution: Optional[dict] = None,
    images=None,
    gemini_client=None,
) -> TeachingDocument:
    """Ask Gemini for SMILES when scheme/mcq stages have empty structures."""
    missing = stages_missing_smiles(doc)
    if not missing:
        return doc

    gemini = gemini_client or GeminiClient()
    if not gemini.is_live():
        print(f"[TeachingDocument] {len(missing)} stages lack SMILES (Gemini offline)")
        return doc

    images = images or question_data.get("images") or []
    payload = {
        "questionText": question_data.get("questionText", ""),
        "answer": (solution or {}).get("answer"),
        "concept": (solution or {}).get("concept"),
        "needSmilesFor": [
            {
                "id": s.id,
                "label": s.label,
                "role": s.role if isinstance(s.role, str) else (s.role.value if s.role else None),
                "kind": s.kind if isinstance(s.kind, str) else (s.kind.value if s.kind else None),
            }
            for s in missing
        ],
        "existingStages": [
            {
                "id": s.id,
                "label": s.label,
                "smiles": s.smiles,
                "role": s.role if isinstance(s.role, str) else (s.role.value if s.role else None),
            }
            for s in doc.stages
        ],
        "edges": [
            {"from": e.source, "to": e.target, "label": e.label} for e in doc.edges
        ],
        "images": images,
    }
    res = gemini.generate_json_with_retry(FILL_SMILES_PROMPT, payload, max_retries=2, timeout=120)
    filled = {str(it.get("id")): str(it.get("smiles") or "").strip() for it in (res or {}).get("stages") or [] if it.get("id")}
    if not filled:
        print("[TeachingDocument] SMILES fill returned empty")
        return doc

    new_stages: List[Stage] = []
    n_ok = 0
    for s in doc.stages:
        smi = (filled.get(s.id) or s.smiles or "").strip() or None
        if smi and validate_smiles(smi):
            if s.smiles != smi:
                n_ok += 1
            role = s.role if isinstance(s.role, str) else (s.role.value if s.role else "")
            new_stages.append(
                s.model_copy(
                    update={
                        "smiles": smi,
                        "kind": StageKind.option if role == "option" else StageKind.molecule,
                    }
                )
            )
        else:
            new_stages.append(s)
    print(f"[TeachingDocument] filled SMILES on {n_ok} stages")
    return doc.model_copy(update={"stages": new_stages})


def validate_smiles(smiles: Optional[str]) -> bool:
    s = (smiles or "").strip()
    if len(s) < 2 or len(s) > 512:
        return False
    if not _SMILES_RE.match(s):
        return False
    if not re.search(r"[A-Za-z]", s):
        return False
    if _HAS_RDKIT and Chem is not None:
        try:
            mol = Chem.MolFromSmiles(s)
            return mol is not None
        except Exception:
            return False
    return True


def _guess_layout(question_data: dict, solution: dict) -> Layout:
    blob = (
        f"{question_data.get('questionText', '')} {question_data.get('topic', '')} "
        f"{question_data.get('subject', '')} {solution.get('concept', '')}"
    ).lower()
    if any(
        k in blob
        for k in (
            "flower",
            "amoeba",
            "nephron",
            "stomata",
            "chloroplast",
            "biology",
            "petal",
            "pseudopodia",
        )
    ):
        return Layout.figure
    if any(
        k in blob
        for k in (
            "radial",
            "potential energy",
            "internuclear",
            "energy level",
            "rdf",
            "4πr",
            "pe curve",
            "morse",
        )
    ):
        return Layout.plot
    if any(
        k in blob
        for k in (
            "flowchart",
            "flow chart",
            "select the correct statement",
            "correct statement",
            "vapours",
            "vapors",
            "k2s2o3",
            "pb(no3",
            "mno2",
            "thiosulphate",
            "thiosulfate",
        )
    ):
        return Layout.flowchart
    if any(
        k in blob
        for k in (
            "ibuprofen",
            "synthesis",
            "friedel",
            "clemmensen",
            "multi-step",
            "multistep",
            "synthesis from",
            "starting from benzene",
        )
    ) or ("alcl3" in blob and "benzene" in blob):
        return Layout.scheme
    if any(
        k in blob
        for k in (
            "ozonolysis",
            "lactone",
            "iupac",
            "organic",
            "smiles",
            "azo",
            "ester",
            "alkene",
        )
    ):
        # Prefer scheme if reagents/arrows present, else mcq
        if any(k in blob for k in ("reagent", "alcl3", "nabh4", "o3", "heat", "h2so4")):
            return Layout.scheme
        return Layout.mcq
    if any(k in blob for k in ("projectile", "force", "fbd", "free body", "ray", "lens")):
        return Layout.fbd
    subj = str(question_data.get("subject", "")).lower()
    if subj.startswith("bio"):
        return Layout.figure
    if subj.startswith("phys"):
        return Layout.fbd
    if subj.startswith("chem"):
        return Layout.mcq
    return Layout.mcq


def migrate_from_legacy(solution: dict, question_data: dict) -> dict:
    """Build a raw TeachingDocument dict from old visualPack / diagramSpec."""
    pack = solution.get("visualPack") if isinstance(solution.get("visualPack"), dict) else {}
    layout = _guess_layout(question_data, solution)

    # Prefer explicit pack domain hints
    domain = str(pack.get("domain") or "").lower()
    if domain == "flow" or (pack.get("flowGraph") or {}).get("nodes"):
        layout = Layout.flowchart
    elif domain == "organic" and (pack.get("molecules") or pack.get("reactionSteps")):
        layout = Layout.scheme if (pack.get("reactionSteps") or len(pack.get("molecules") or []) > 2) else Layout.mcq
    elif domain == "biology" or pack.get("bioFigure"):
        layout = Layout.figure
    elif domain == "graph":
        layout = Layout.plot

    stages: List[dict] = []
    edges: List[dict] = []
    plot = None
    figure = None

    if layout == Layout.flowchart:
        fg = pack.get("flowGraph") or {}
        for n in fg.get("nodes") or []:
            if not isinstance(n, dict) or not n.get("id"):
                continue
            stages.append(
                {
                    "id": str(n["id"]),
                    "kind": "label",
                    "label": str(n.get("label") or n["id"]),
                    "role": "start" if str(n.get("kind")) == "reagent" else "mid",
                }
            )
        for e in fg.get("edges") or []:
            if not isinstance(e, dict):
                continue
            edges.append(
                {
                    "from": str(e.get("source") or ""),
                    "to": str(e.get("target") or ""),
                    "label": str(e.get("label") or ""),
                    "id": e.get("id"),
                }
            )
    elif layout in (Layout.scheme, Layout.mcq):
        role_map = {
            "reactant": "start",
            "intermediate": "mid",
            "product": "end",
            "option": "option",
        }
        for m in pack.get("molecules") or []:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id") or f"m{len(stages)}")
            role = role_map.get(str(m.get("role") or "").lower(), "other")
            kind = "option" if role == "option" else "molecule"
            stages.append(
                {
                    "id": mid,
                    "kind": kind,
                    "label": str(m.get("label") or mid),
                    "smiles": m.get("smiles"),
                    "role": role,
                    "correct": bool(m.get("correct")),
                    "callout": m.get("callout"),
                }
            )
        # Build linear edges from reactionSteps if missing
        path = [s for s in stages if s.get("role") in ("start", "mid", "end")]
        rxn = pack.get("reactionSteps") or []
        if len(path) >= 2 and not edges:
            for i in range(len(path) - 1):
                lab = ""
                if i < len(rxn) and isinstance(rxn[i], dict):
                    lab = str(rxn[i].get("reagents") or "")
                edges.append({"from": path[i]["id"], "to": path[i + 1]["id"], "label": lab})
        elif len(path) == 1 and rxn and layout == Layout.scheme:
            # Pad synthetic mid stages so scheme layout still works
            start = path[0]
            for i, step in enumerate(rxn[:-1] if len(rxn) > 1 else []):
                sid = f"stage_{i + 1}"
                stages.append(
                    {
                        "id": sid,
                        "kind": "label",
                        "label": f"After step {i + 1}",
                        "role": "mid",
                    }
                )
            end_id = "final"
            stages.append(
                {
                    "id": end_id,
                    "kind": "molecule",
                    "label": "Product",
                    "role": "end",
                    "smiles": next(
                        (s.get("smiles") for s in stages if s.get("correct")),
                        None,
                    ),
                }
            )
            chain = [start["id"]] + [f"stage_{i + 1}" for i in range(max(0, len(rxn) - 1))] + [end_id]
            # Fix chain length to edges
            ids = [start["id"]]
            for i in range(len(rxn) - 1):
                ids.append(f"stage_{i + 1}")
            ids.append(end_id)
            for i in range(len(ids) - 1):
                lab = str((rxn[i] or {}).get("reagents") or "") if i < len(rxn) else ""
                edges.append({"from": ids[i], "to": ids[i + 1], "label": lab})
    elif layout == Layout.figure:
        bf = pack.get("bioFigure") or {}
        figure = {
            "type": str(bf.get("type") or "custom"),
            "title": str(bf.get("title") or solution.get("concept") or ""),
            "highlight": bf.get("highlight"),
            "parts": bf.get("parts") or [],
        }
    elif layout == Layout.plot:
        # Best-effort from diagramSpec polylines — leave empty; plot engine may use diagramSpec fallback
        plot = {
            "title": str((solution.get("diagramSpec") or {}).get("title") or solution.get("concept") or ""),
            "xLabel": "x",
            "yLabel": "y",
            "series": [],
            "marks": [],
        }

    ans = str(solution.get("answer") or "")
    opt = None
    m = re.search(r"\(([A-Da-d])\)", ans)
    if m:
        opt = m.group(1).upper()
    if pack.get("correctOption"):
        opt = str(pack["correctOption"]).replace("(", "").replace(")", "")[:1].upper() or opt

    beats = []
    for b in pack.get("animationSequence") or []:
        if not isinstance(b, dict):
            continue
        focus = b.get("focusId") or (str(b.get("see") or "").replace("mol_", "").replace("flow_", "") or None)
        beats.append({"t": float(b.get("at") or 0), "focus": focus, "say": str(b.get("say") or "")})

    return {
        "layout": layout.value if isinstance(layout, Layout) else str(layout),
        "title": pack.get("title") or solution.get("concept") or question_data.get("topic") or "Figure",
        "stages": stages,
        "edges": edges,
        "plot": plot,
        "figure": figure,
        "answer": {"option": opt, "plain": str(solution.get("answerPlain") or ans)},
        "beats": beats,
    }


def sanitize_document(doc: TeachingDocument) -> TeachingDocument:
    """Drop invalid SMILES; keep label; prune broken edges."""
    clean_stages: List[Stage] = []
    for st in doc.stages:
        smiles = st.smiles
        if smiles and not validate_smiles(smiles):
            smiles = None
            if st.kind == StageKind.molecule:
                st = st.model_copy(update={"smiles": None, "kind": StageKind.label if not st.label else st.kind})
        else:
            st = st.model_copy(update={"smiles": smiles})
        clean_stages.append(st)
    ids = {s.id for s in clean_stages}
    clean_edges = [e for e in doc.edges if e.source in ids and e.target in ids]
    return doc.model_copy(update={"stages": clean_stages, "edges": clean_edges})


def validate_document(doc: TeachingDocument) -> List[str]:
    """Return list of errors (empty = ok)."""
    errs: List[str] = []
    layout = Layout(doc.layout) if not isinstance(doc.layout, Layout) else doc.layout
    if layout == Layout.scheme:
        path = [s for s in doc.stages if s.role in (StageRole.start, StageRole.mid, StageRole.end, "start", "mid", "end")]
        if len(path) < 1 and not doc.edges:
            errs.append("scheme needs stages or edges")
    elif layout == Layout.flowchart:
        if len(doc.stages) < 2:
            errs.append("flowchart needs >=2 stages")
        if not doc.edges:
            errs.append("flowchart needs edges")
    elif layout == Layout.plot:
        if not doc.plot or not (doc.plot.series or doc.plot.marks):
            # Soft: allow empty plot if diagramSpec still present on solution
            pass
    elif layout == Layout.figure:
        if not doc.figure or not doc.figure.type:
            errs.append("figure needs figure.type")
    elif layout == Layout.mcq:
        opts = [s for s in doc.stages if s.role in (StageRole.option, "option") or s.kind in (StageKind.option, "option")]
        if not opts and not doc.stages:
            errs.append("mcq needs option stages")
    return errs


def repair_sparse_document(
    doc: TeachingDocument,
    solution: dict,
    question_data: dict,
) -> TeachingDocument:
    """Never ship empty scheme/flowchart — build label stages from solution steps."""
    layout = Layout(doc.layout) if not isinstance(doc.layout, Layout) else doc.layout
    if layout not in (Layout.scheme, Layout.mcq, Layout.flowchart):
        return doc

    pathish = [
        s
        for s in doc.stages
        if s.role != StageRole.option and str(getattr(s.role, "value", s.role) or "") != "option"
    ]
    sparse = len(pathish) < 1
    # AI sometimes returns layout=scheme with stages=[] or only empty labels
    if len(pathish) >= 1 and not any(
        (s.smiles or "").strip() or (s.label or "").strip() for s in pathish
    ):
        sparse = True
    if layout == Layout.flowchart and (len(pathish) < 2 or not doc.edges):
        sparse = True
    if not sparse:
        return doc

    q = f"{question_data.get('questionText', '')} {solution.get('concept', '')}".lower()
    steps = [s for s in (solution.get("steps") or []) if isinstance(s, dict)]
    eq_beats = [e for e in (solution.get("equationBeats") or []) if isinstance(e, dict)]

    stages: List[Stage] = list(doc.stages) if doc.stages else []
    edges: List[Edge] = list(doc.edges) if doc.edges else []

    if not stages:
        start_label = "Start"
        start_smiles = None
        if "benzene" in q:
            start_label = "Benzene"
            start_smiles = "c1ccccc1"
        elif "dead" in q or "azodicarboxylate" in q:
            start_label = "DEAD"
            start_smiles = "CCOC(=O)N=NC(=O)OCC"
        stages.append(
            Stage(
                id="s0",
                kind=StageKind.molecule if start_smiles else StageKind.label,
                label=start_label,
                smiles=start_smiles,
                role=StageRole.start,
            )
        )

        chain_src = steps[:5] if steps else eq_beats[:5]
        prev = "s0"
        for i, item in enumerate(chain_src):
            sid = f"s{i + 1}"
            label = str(
                item.get("title") or item.get("label") or item.get("say") or f"Step {i + 1}"
            )[:80]
            reagent = str(
                item.get("formula") or item.get("calculation") or item.get("latex") or ""
            )[:60]
            role = StageRole.end if i == len(chain_src) - 1 else StageRole.mid
            if role == StageRole.end and "ibuprofen" in q:
                stages.append(
                    Stage(
                        id=sid,
                        kind=StageKind.molecule,
                        label="Ibuprofen",
                        smiles="CC(C)Cc1ccc(C(C)C(=O)O)cc1",
                        role=role,
                    )
                )
            else:
                stages.append(Stage(id=sid, kind=StageKind.label, label=label, role=role))
            edges.append(Edge(source=prev, target=sid, label=reagent))
            prev = sid

        if len(stages) == 1:
            end_label = str(solution.get("find") or solution.get("answer") or "Product")[:80]
            stages.append(
                Stage(id="s_end", kind=StageKind.label, label=end_label, role=StageRole.end)
            )
            edges.append(Edge(source="s0", target="s_end", label=""))

        ans = str(solution.get("answer") or "")
        for letter in ("A", "B", "C", "D"):
            if f"({letter})" in ans or ans.strip().upper().startswith(letter):
                stages.append(
                    Stage(
                        id=f"opt{letter}",
                        kind=StageKind.option,
                        label=f"({letter})",
                        role=StageRole.option,
                        correct=letter in ans.upper()[:8] or f"({letter})" in ans,
                    )
                )

    if not edges and len(stages) >= 2:
        path = [s for s in stages if s.role != StageRole.option]
        for i in range(len(path) - 1):
            edges.append(Edge(source=path[i].id, target=path[i + 1].id, label=""))

    print(
        f"[TeachingDocument] repaired sparse {layout.value}: "
        f"{len(stages)} stages, {len(edges)} edges"
    )
    return doc.model_copy(
        update={
            "stages": stages,
            "edges": edges,
            "title": doc.title or str(solution.get("concept") or "Figure"),
        }
    )


def ensure_beats(doc: TeachingDocument, solution: Optional[dict] = None) -> TeachingDocument:
    if doc.beats:
        return doc
    solution = solution or {}
    beats: List[Beat] = []
    layout = doc.layout
    t = 0.0
    path = [
        s
        for s in doc.stages
        if s.role in (StageRole.start, StageRole.mid, StageRole.end, "start", "mid", "end")
        or (layout == Layout.flowchart and s.role != StageRole.option)
    ]
    if not path:
        path = [s for s in doc.stages if s.role not in (StageRole.option, "option")]
    step_says = [
        str(s.get("say") or "").strip()
        for s in (solution.get("steps") or [])
        if isinstance(s, dict)
    ]
    for i, st in enumerate(path):
        say = step_says[i] if i < len(step_says) else f"Ab yeh dekho: {st.label or st.id}"
        beats.append(Beat(t=t, focus=st.id, say=say))
        t += 5.0
    opts = [s for s in doc.stages if s.role in (StageRole.option, "option")]
    if opts:
        beats.append(Beat(t=t, focus=opts[0].id, say="Ab options compare karte hain."))
        t += 4.0
    beats.append(
        Beat(
            t=t,
            focus=path[-1].id if path else None,
            say=str(doc.answer.plain or solution.get("answer") or "Final answer.")[:220],
        )
    )
    return doc.model_copy(update={"beats": beats})


def parse_teaching_document(raw: Any) -> Optional[TeachingDocument]:
    if not isinstance(raw, dict):
        return None
    try:
        # Normalize edge keys
        edges = []
        for e in raw.get("edges") or []:
            if not isinstance(e, dict):
                continue
            edges.append(
                {
                    "from": e.get("from") or e.get("source"),
                    "to": e.get("to") or e.get("target"),
                    "label": e.get("label") or "",
                    "id": e.get("id"),
                }
            )
        data = {**raw, "edges": edges}
        doc = TeachingDocument.model_validate(data)
        return doc
    except Exception as ex:
        print(f"[TeachingDocument] parse failed: {ex}")
        return None


def extract_teaching_document(
    question_data: dict,
    solution: dict,
    images=None,
    gemini_client=None,
) -> TeachingDocument:
    images = images or question_data.get("images") or []
    gemini = gemini_client or GeminiClient()
    hint = _guess_layout(question_data, solution)

    doc: Optional[TeachingDocument] = None
    if gemini.is_live():
        payload = {
            "questionText": question_data.get("questionText", ""),
            "subject": question_data.get("subject", ""),
            "topic": question_data.get("topic", ""),
            "answer": solution.get("answer"),
            "concept": solution.get("concept"),
            "steps": solution.get("steps"),
            "layoutHint": hint.value,
            "images": images,
            "instruction": (
                "Build TeachingDocument for THIS question figure only. "
                "CRITICAL: stages[] must NOT be empty for scheme/flowchart/mcq. "
                "Include SMILES for every molecule stage you can."
            ),
        }
        res = gemini.generate_json_with_retry(TEACHING_PROMPT, payload, max_retries=2, timeout=120)
        doc = parse_teaching_document(res)
        # Reject empty scheme from AI — fall through to migrate/repair
        if doc and doc.layout in ("scheme", "mcq", "flowchart") and not doc.stages:
            print("[TeachingDocument] AI returned empty stages — repairing")
            doc = None

    if doc is None:
        raw = migrate_from_legacy(solution, question_data)
        doc = parse_teaching_document(raw)
    if doc is None:
        doc = TeachingDocument(layout=hint, title=str(solution.get("concept") or "Figure"))
    return repair_sparse_document(doc, solution, question_data)


def teaching_to_visual_pack(doc: TeachingDocument) -> dict:
    """Backward-compat shim so existing Remotion paths keep working during migration."""
    layout = doc.layout if isinstance(doc.layout, str) else doc.layout.value
    pack: Dict[str, Any] = {
        "domain": {
            "scheme": "organic",
            "mcq": "organic",
            "flowchart": "flow",
            "plot": "graph",
            "figure": "biology",
            "fbd": "physics",
        }.get(layout, "generic"),
        "title": doc.title,
        "molecules": [],
        "reactionSteps": [],
        "correctOption": doc.answer.option,
        "bioFigure": None,
        "flowGraph": None,
        "teachNotes": [b.say for b in doc.beats if b.say][:4],
        "animationSequence": [
            {
                "at": b.t,
                "see": f"mol_{b.focus}" if layout in ("scheme", "mcq") else f"flow_{b.focus}",
                "focusId": b.focus,
                "say": b.say,
            }
            for b in doc.beats
        ],
    }
    if layout in ("scheme", "mcq"):
        role_inv = {"start": "reactant", "mid": "intermediate", "end": "product", "option": "option"}
        for s in doc.stages:
            role = s.role if isinstance(s.role, str) else s.role.value
            pack["molecules"].append(
                {
                    "id": s.id,
                    "smiles": s.smiles,
                    "label": s.label,
                    "role": role_inv.get(role, role),
                    "correct": s.correct,
                    "callout": s.callout,
                }
            )
        for i, e in enumerate(doc.edges):
            pack["reactionSteps"].append({"n": i + 1, "reagents": e.label or f"step {i + 1}"})
    elif layout == "flowchart":
        pack["flowGraph"] = {
            "title": doc.title,
            "nodes": [
                {
                    "id": s.id,
                    "label": s.label or s.id,
                    "kind": "reagent" if (s.role if isinstance(s.role, str) else s.role.value) == "start" else "product",
                }
                for s in doc.stages
            ],
            "edges": [
                {
                    "id": e.id or f"e{i}",
                    "source": e.source,
                    "target": e.target,
                    "label": e.label,
                }
                for i, e in enumerate(doc.edges)
            ],
        }
    elif layout == "figure" and doc.figure:
        pack["bioFigure"] = doc.figure.model_dump()
    return pack


def ensure_teaching_document(
    question_data: dict,
    solution: dict,
    images=None,
    gemini_client=None,
) -> dict:
    """Attach solution.teachingDocument (canonical) + sync visualPack shim + routing flags."""
    sol = dict(solution or {})
    doc = extract_teaching_document(question_data, sol, images=images, gemini_client=gemini_client)
    doc = sanitize_document(doc)
    doc = repair_sparse_document(doc, sol, question_data)
    # Empty SMILES → empty boxes in Remotion; always try to fill bonds
    doc = fill_missing_smiles(
        doc, question_data, solution=sol, images=images, gemini_client=gemini_client
    )
    doc = sanitize_document(doc)
    doc = ensure_beats(doc, sol)
    errs = validate_document(doc)
    if errs:
        print(f"[TeachingDocument] warnings: {errs}")

    payload = doc.model_dump(by_alias=True, mode="json")
    sol["teachingDocument"] = payload

    # Shim for current Remotion components
    pack = teaching_to_visual_pack(doc)
    sol["visualPack"] = pack

    layout = payload["layout"]
    vc = sol.setdefault("visualConcept", {})
    if not isinstance(vc, dict):
        vc = {}
        sol["visualConcept"] = vc

    # Clear competing freehand molecule specs for typed layouts
    if layout in ("scheme", "mcq", "flowchart", "figure"):
        sol["diagramSpec"] = None

    sol.pop("preferMoleculeBoard", None)
    sol.pop("preferTeachingFlow", None)
    sol.pop("preferBiologyFigure", None)

    if layout in ("scheme", "mcq"):
        vc["primaryVisual"] = "teaching_scheme" if layout == "scheme" else "teaching_mcq"
        vc["bestEngine"] = "2D"
        sol["preferMoleculeBoard"] = True
    elif layout == "flowchart":
        vc["primaryVisual"] = "teaching_flow"
        vc["bestEngine"] = "2D"
        sol["preferTeachingFlow"] = True
    elif layout == "figure":
        vc["primaryVisual"] = "biology_figure"
        vc["bestEngine"] = "2D"
        sol["preferBiologyFigure"] = True
    elif layout == "plot":
        vc["primaryVisual"] = "teaching_plot"
        vc["bestEngine"] = "2D"
        # Keep diagramSpec for plot fallback if plot.series empty
        if not (doc.plot and (doc.plot.series or doc.plot.marks)):
            from .diagram_builder import ensure_diagram_spec

            sol = ensure_diagram_spec(question_data, sol, images=images, gemini_client=gemini_client)
            vc["primaryVisual"] = "diagram_spec"
    else:
        vc["primaryVisual"] = "diagram_spec"
        from .diagram_builder import ensure_diagram_spec

        sol = ensure_diagram_spec(question_data, sol, images=images, gemini_client=gemini_client)

    vc["rebuildQuestionFigure"] = True
    vc.setdefault("mustShow", [])
    tag = vc["primaryVisual"]
    if tag not in vc["mustShow"]:
        vc["mustShow"] = list(vc["mustShow"]) + [tag]

    sim = sol.setdefault("simulation", {})
    if isinstance(sim, dict):
        sim["type"] = "diagram"
        sim.setdefault("params", {})
        sim["params"]["layout"] = layout
        if layout in ("scheme", "mcq", "flowchart", "figure"):
            sim["params"]["useDiagramSpec"] = False

    return sol


def document_to_dict(doc: TeachingDocument) -> dict:
    return doc.model_dump(by_alias=True, mode="json")
