"""Multi-domain VisualPack — typed teaching visuals (NOT freehand broken SVG, NOT question photo).

Domains:
  - flow: inorganic / multi-step reaction flowcharts → flowGraph (React Flow / XYFlow)
  - organic: molecules via SMILES (+ optional reaction steps / MCQ options)
  - graph: keep diagramSpec (PE curve, RDF, energy levels)
  - biology: parametric bioFigure (flower, amoeba, cell, nephron, …)
  - physics: diagramSpec / simple schematics
  - generic: teaching_flow diagramSpec

AI extracts structured data; Remotion uses TeachingFlowGraph / MoleculeBoard / BiologyFigure / GenericDiagram.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .gemini import GeminiClient
from .diagram_builder import ensure_diagram_spec, normalize_diagram_spec
from .visual_teaching import attach_teaching_timeline


VISUAL_PACK_PROMPT = """You build a VisualPack for an educational video (DoubtSolve).

NEVER invent freehand SVG coordinates for organic bonds (they break).
NEVER say to show the raw question photo.

Choose ONE primary domain and fill the matching fields.

DOMAINS:
1) flow — reaction flowchart / inorganic sequence / "select correct statement" with boxes (A)(B)(C)…
   Return flowGraph with nodes[] (id, label, kind: reagent|product|branch|mixture) and edges[] (source, target, label=reagent).
   Match the QUESTION figure topology (branches, parallel paths). NO SMILES. NO freehand SVG coordinates.
2) organic — structure / MCQ / multi-step synthesis (ibuprofen, FC, etc.)
   CRITICAL for multi-step synthesis shown as arrows in the question image:
   - Put START + each intermediate + FINAL product as molecules with roles
     reactant → intermediate → product (SMILES for EACH stage of the scheme).
   - Put reagents exactly as written on the arrows into reactionSteps[].
   - Put A/B/C/D structures as role=option separately.
   - Do NOT only return benzene + options — that breaks the teaching figure.
   For simple structure MCQ only: reactant + options is OK.
3) graph — PE curves, RDF plots, energy levels, axes graphs → use diagramSpec elements
   with LIGHT colors only (#38BDF8 #F8FAFC #F87171 …), no black.
4) biology — flower, amoeba, cell, nephron, leaf, heart schematic
   Return bioFigure.type from: flower | amoeba | animal_cell | plant_cell | nephron | neuron | custom
   Plus parts[] labels to highlight (e.g. stigma, petal, nucleus, pseudopodia).
5) physics — FBD / rays / circuits as diagramSpec primitives (no organic SMILES).

Return ONLY JSON:
{
  "domain": "flow|organic|graph|biology|physics|generic",
  "title": "short",
  "molecules": [
    {"id":"reactant","smiles":"CCc1cccc1","label":"Starting alkene","role":"reactant"},
    {"id":"optA","smiles":"...","label":"(A)","role":"option","correct":false}
  ],
  "reactionSteps": [{"n":1,"reagents":"O3, Zn, H2O"},{"n":2,"reagents":"Ag2O/NH4OH"}],
  "correctOption": "A",
  "bioFigure": {
    "type": "flower|amoeba|animal_cell|plant_cell|nephron|neuron|custom",
    "title": "…",
    "highlight": "part_id",
    "parts": [{"id":"petal","label":"Petal"},{"id":"stigma","label":"Stigma"}]
  },
  "flowGraph": {
    "title": "Reaction sequence",
    "nodes": [{"id":"start","label":"KI + MnO₂ + H₂SO₄","kind":"reagent"}],
    "edges": [{"id":"e1","source":"start","target":"b","label":""}]
  },
  "diagramSpec": null,
  "teachNotes": ["one short hinglish beat"]
}

Rules:
- flow: ONLY for inorganic flowcharts with lettered boxes (A)(B)(C) and branches.
  Do NOT use flow for organic synthesis schemes (those are domain=organic).
- organic multi-step: molecules MUST include the full scheme chain + options.
  Example ibuprofen: benzene (reactant), acyl intermediate, alkylbenzene, ketone, cyanohydrin/product stages,
  then options A–D with correct:true on ibuprofen. reactionSteps = exact reagents from arrows.
- organic: SMILES for THIS question only. NEVER freehand bond SVG. NEVER a different sample molecule.
- biology: bioFigure required; molecules empty.
- graph: diagramSpec for PE/RDF axes plots.
"""


def _flow_graph_present(obj: dict) -> bool:
    fg = (obj or {}).get("flowGraph")
    return isinstance(fg, dict) and bool(fg.get("nodes"))


def _detect_domain(question_data: dict, solution: dict) -> str:
    blob = f"{question_data.get('questionText','')} {question_data.get('topic','')} {question_data.get('subject','')} {solution.get('concept','')}".lower()
    vp = solution.get("visualPack") if isinstance(solution.get("visualPack"), dict) else {}
    if _flow_graph_present(vp) or _flow_graph_present(solution):
        return "flow"
    if any(k in blob for k in ("flower", "amoeba", "ameoba", "nephron", "stomata", "chloroplast", "mitochondria", "neuron", "biology", "petal", "pistil", "pseudopodia")):
        return "biology"
    if any(
        k in blob
        for k in (
            "flowchart",
            "flow chart",
            "reaction sequence",
            "select the correct statement",
            "correct statement(s)",
            "correct statement",
            "vapours",
            "vapour",
            "vapors",
            "otherproduct",
            "other product",
            "pb(no3",
            "k2s2o3",
            "thiosulphate",
            "thiosulfate",
            "mno2",
            "mno₂",
            "vapours (b)",
        )
    ) and "ibuprofen" not in blob and "benzene" not in blob and "friedel" not in blob:
        return "flow"
    if any(
        k in blob
        for k in (
            "ozonolysis",
            "lactone",
            "smiles",
            "iupac",
            "organic",
            "alkene",
            "reagent",
            "nabh4",
            "ag2o",
            "product (a)",
            "o3,",
            "synthesis",
            "friedel",
            "alcl3",
            "acyl",
            "benzene",
            "aromatic",
            "multi-step",
            "multistep",
            "azo",
            "ester",
            "carboxylate",
        )
    ):
        return "organic"
    if any(k in blob for k in ("radial", "potential energy", "internuclear", "energy level", "rdf", "4πr", "plot for")):
        return "graph"
    if str(question_data.get("subject", "")).lower().startswith("bio"):
        return "biology"
    if str(question_data.get("subject", "")).lower().startswith("chem"):
        return "generic"
    if str(question_data.get("subject", "")).lower().startswith("phys"):
        return "physics"
    return "generic"


def _bio_type_from_blob(blob: str) -> str:
    if "amoeba" in blob or "ameoba" in blob or "pseudopod" in blob:
        return "amoeba"
    if "flower" in blob or "petal" in blob or "pistil" in blob or "stigma" in blob:
        return "flower"
    if "plant cell" in blob or "chloroplast" in blob or "cell wall" in blob:
        return "plant_cell"
    if "animal cell" in blob or "mitochondria" in blob:
        return "animal_cell"
    if "nephron" in blob or "glomerulus" in blob:
        return "nephron"
    if "neuron" in blob or "axon" in blob or "dendrite" in blob:
        return "neuron"
    return "custom"


def offline_visual_pack(question_data: dict, solution: dict) -> dict:
    domain = _detect_domain(question_data, solution)
    blob = f"{question_data.get('questionText','')} {question_data.get('topic','')}".lower()
    pack: Dict[str, Any] = {
        "domain": domain,
        "title": solution.get("concept") or question_data.get("topic") or "Visual",
        "molecules": [],
        "reactionSteps": [],
        "correctOption": None,
        "bioFigure": None,
        "flowGraph": None,
        "diagramSpec": solution.get("diagramSpec"),
        "teachNotes": [],
    }
    if domain == "flow":
        fg = (solution.get("visualPack") or {}).get("flowGraph") or solution.get("flowGraph")
        if isinstance(fg, dict) and fg.get("nodes"):
            pack["flowGraph"] = fg
        pack["diagramSpec"] = None
        pack["teachNotes"] = [
            "Reaction flowchart ko node-by-node samjhao — SMILES cards mat banao.",
        ]
    elif domain == "biology":
        btype = _bio_type_from_blob(blob)
        parts = {
            "flower": [
                {"id": "petal", "label": "Petal"},
                {"id": "stigma", "label": "Stigma"},
                {"id": "anther", "label": "Anther"},
                {"id": "ovary", "label": "Ovary"},
            ],
            "amoeba": [
                {"id": "pseudopodia", "label": "Pseudopodia"},
                {"id": "nucleus", "label": "Nucleus"},
                {"id": "food_vacuole", "label": "Food vacuole"},
                {"id": "contractile", "label": "Contractile vacuole"},
            ],
            "animal_cell": [
                {"id": "nucleus", "label": "Nucleus"},
                {"id": "mitochondria", "label": "Mitochondria"},
                {"id": "membrane", "label": "Cell membrane"},
            ],
            "plant_cell": [
                {"id": "cell_wall", "label": "Cell wall"},
                {"id": "chloroplast", "label": "Chloroplast"},
                {"id": "vacuole", "label": "Vacuole"},
                {"id": "nucleus", "label": "Nucleus"},
            ],
            "nephron": [
                {"id": "glomerulus", "label": "Glomerulus"},
                {"id": "bowman", "label": "Bowman's capsule"},
                {"id": "tubule", "label": "Tubule"},
            ],
            "neuron": [
                {"id": "dendrite", "label": "Dendrites"},
                {"id": "soma", "label": "Cell body"},
                {"id": "axon", "label": "Axon"},
            ],
        }.get(btype, [{"id": "part1", "label": "Main structure"}])
        pack["bioFigure"] = {
            "type": btype,
            "title": pack["title"],
            "highlight": parts[0]["id"],
            "parts": parts,
        }
        pack["teachNotes"] = [f"Yeh {btype.replace('_', ' ')} diagram ke labeled parts dekhte hain."]
    elif domain == "organic":
        # No per-question SMILES hardcode — reuse molecules already on the solution (from AI solve).
        existing = []
        for m in (solution.get("visualPack") or {}).get("molecules") or []:
            if isinstance(m, dict) and str(m.get("smiles") or "").strip():
                existing.append(m)
        pack["molecules"] = existing
        pack["reactionSteps"] = list(
            (solution.get("visualPack") or {}).get("reactionSteps")
            or solution.get("reactionSteps")
            or []
        )
        pack["correctOption"] = (solution.get("visualPack") or {}).get("correctOption") or solution.get(
            "correctOption"
        )
        pack["teachNotes"] = [
            "Organic: AI se is question ke SMILES lao; freehand bond SVG mat banao.",
        ]
        pack["diagramSpec"] = None
    return pack


def extract_visual_pack(question_data: dict, solution: dict, images=None, gemini_client=None) -> dict:
    images = images or question_data.get("images") or []
    gemini = gemini_client or GeminiClient()
    domain_hint = _detect_domain(question_data, solution)

    # Prefer molecules already returned by the solver (same question — no second hardcode path)
    seeded = solution.get("visualPack")
    if isinstance(seeded, dict):
        if domain_hint == "flow" and _flow_graph_present(seeded):
            return normalize_visual_pack(seeded, question_data, solution)
        mols = seeded.get("molecules") or []
        has_smiles = any(isinstance(m, dict) and str(m.get("smiles") or "").strip() for m in mols)
        if domain_hint == "organic" and has_smiles:
            return normalize_visual_pack(seeded, question_data, solution)
        if domain_hint == "biology" and seeded.get("bioFigure"):
            return normalize_visual_pack(seeded, question_data, solution)

    if not gemini.is_live():
        return offline_visual_pack(question_data, solution)

    payload = {
        "questionText": question_data.get("questionText", ""),
        "subject": question_data.get("subject", ""),
        "topic": question_data.get("topic", ""),
        "solutionConcept": solution.get("concept"),
        "answer": solution.get("answer"),
        "domainHint": domain_hint,
        "images": images,
        "instruction": (
            "Build VisualPack JSON for THIS question only. "
            "Organic: real SMILES for named structures in the question — never a sample molecule."
        ),
    }
    res = gemini.generate_json_with_retry(VISUAL_PACK_PROMPT, payload, max_retries=2, timeout=120)
    if not isinstance(res, dict) or not res.get("domain"):
        return offline_visual_pack(question_data, solution)
    return normalize_visual_pack(res, question_data, solution)


def normalize_flow_graph(fg: Any) -> Optional[dict]:
    if not isinstance(fg, dict):
        return None
    nodes: List[dict] = []
    for n in fg.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "").strip()
        label = str(n.get("label") or "").strip()
        if not nid or not label:
            continue
        nodes.append(
            {
                "id": nid,
                "label": label[:160],
                "kind": str(n.get("kind") or "product").lower(),
            }
        )
    if not nodes:
        return None
    valid_ids = {n["id"] for n in nodes}
    edges: List[dict] = []
    for i, e in enumerate(fg.get("edges") or []):
        if not isinstance(e, dict):
            continue
        src = str(e.get("source") or "").strip()
        tgt = str(e.get("target") or "").strip()
        if src not in valid_ids or tgt not in valid_ids:
            continue
        edges.append(
            {
                "id": str(e.get("id") or f"e{i}_{src}_{tgt}"),
                "source": src,
                "target": tgt,
                "label": str(e.get("label") or "").strip()[:80],
            }
        )
    return {"title": str(fg.get("title") or "").strip()[:120], "nodes": nodes, "edges": edges}


def normalize_visual_pack(pack: dict, question_data: dict, solution: dict) -> dict:
    base = offline_visual_pack(question_data, solution)
    if not isinstance(pack, dict):
        return base
    # Question-driven domain wins — AI must not demote organic to freehand "graph"
    forced = _detect_domain(question_data, solution)
    domain = str(pack.get("domain") or base["domain"]).lower()
    if forced == "flow":
        domain = "flow"
    elif forced == "organic":
        domain = "organic"
    elif forced == "biology":
        domain = "biology"
    if domain not in ("flow", "organic", "graph", "biology", "physics", "generic"):
        domain = base["domain"]
    fg_raw = pack.get("flowGraph") or (solution.get("visualPack") or {}).get("flowGraph")
    flow_graph = normalize_flow_graph(fg_raw)
    out = {
        "domain": domain,
        "title": pack.get("title") or base["title"],
        "molecules": [],
        "reactionSteps": pack.get("reactionSteps") or base.get("reactionSteps") or [],
        "correctOption": pack.get("correctOption") or base.get("correctOption"),
        "bioFigure": pack.get("bioFigure") or base.get("bioFigure"),
        "flowGraph": flow_graph,
        # Typed packs never use broken freehand molecule SVG
        "diagramSpec": None
        if domain in ("organic", "flow")
        else (normalize_diagram_spec(pack.get("diagramSpec")) or solution.get("diagramSpec")),
        "teachNotes": pack.get("teachNotes") or base.get("teachNotes") or [],
    }
    if domain == "flow":
        out["molecules"] = []
        if not out["flowGraph"] and base.get("flowGraph"):
            out["flowGraph"] = base["flowGraph"]
    for m in pack.get("molecules") or []:
        if not isinstance(m, dict):
            continue
        smiles = str(m.get("smiles") or "").strip()
        if not smiles or len(smiles) < 2:
            continue
        out["molecules"].append(
            {
                "id": m.get("id") or f"mol_{len(out['molecules'])}",
                "smiles": smiles,
                "label": m.get("label") or m.get("id") or "",
                "role": m.get("role") or "option",
                "correct": bool(m.get("correct")),
            }
        )
    # Fallback only from solution-carried molecules (never a different sample molecule)
    if domain == "organic" and not out["molecules"] and base.get("molecules"):
        out["molecules"] = base["molecules"]
        out["reactionSteps"] = base.get("reactionSteps") or out["reactionSteps"]
    if domain == "biology" and not out.get("bioFigure"):
        out["bioFigure"] = base.get("bioFigure")
    if out.get("bioFigure") and isinstance(out["bioFigure"], dict):
        bf = out["bioFigure"]
        bf["type"] = str(bf.get("type") or "custom").lower().replace(" ", "_")
        bf.setdefault("parts", [])
        bf.setdefault("title", out["title"])
    return attach_teaching_timeline(out, solution)


def ensure_visual_pack(question_data: dict, solution: dict, images=None, gemini_client=None) -> dict:
    """Deprecated shim — delegates to TeachingDocument IR."""
    from .teaching_document import ensure_teaching_document

    return ensure_teaching_document(
        question_data, solution, images=images, gemini_client=gemini_client
    )
