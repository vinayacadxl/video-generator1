"""Rewrite STEM / equation / chemistry text so TTS speaks naturally.

Spoken text only — on-screen captions keep the original narration.
Dense formulas are summarized as short phrases (not letter-by-letter).
"""

from __future__ import annotations

import re
import unicodedata


# Longer / more specific phrases first
_WORD_REPLACEMENTS = [
    (r"\bequations?\b", "equation"),
    (r"\bformulae?\b", "formula"),
    (r"\bsynthesis\b", "synthesis"),
    (r"\bozonolysis\b", "ozonolysis"),
    (r"\blactonization\b", "lactonization"),
    (r"\blactonisation\b", "lactonization"),
    (r"\besterification\b", "esterification"),
    (r"\bintramolecular\b", "intramolecular"),
    (r"\bintermolecular\b", "intermolecular"),
    (r"\belectrostatic\b", "electrostatic"),
    (r"\binfinity\b", "infinity"),
    (r"\binfinite\b", "infinite"),
    (r"\bintegration\b", "integration"),
    (r"\bconstant\b", "constant"),
    (r"\breference\b", "reference"),
    (r"\bconvention\b", "convention"),
    (r"\bscheme\b", "scheme"),
    (r"\bflowchart\b", "flow chart"),
    (r"\bmolecules?\b", "molecule"),
    (r"\breagents?\b", "reagent"),
    (r"\bTollens'?\b", "Tollens"),
    (r"\bIUPAC\b", "I U pack"),
    (r"\bhexadiene\b", "hexadiene"),
    (r"\bbutadiene\b", "butadiene"),
    (r"\bpentadiene\b", "pentadiene"),
    (r"\bcyclopentene\b", "cyclopentene"),
    (r"\bcyclohexanone\b", "cyclohexanone"),
    (r"\bethylcyclopentene\b", "ethyl cyclopentene"),
    (r"\boxoheptanoic acid\b", "oxo heptanoic acid"),
    (r"\boxoheptanoic\b", "oxo heptanoic"),
    (r"\boxoheptanal\b", "oxo heptanal"),
    (r"\bhydroxyheptanoic acid\b", "hydroxy heptanoic acid"),
    (r"\bhydroxyheptanoic\b", "hydroxy heptanoic"),
    (r"\bheptanoic\b", "heptanoic"),
    (r"\bheptanal\b", "heptanal"),
    (r"\blactone\b", "lactone"),
    (r"\bdimethylethenyl\b", "dimethyl ethenyl"),
    (r"\bmethylethenyl\b", "methyl ethenyl"),
    (r"\bethenyl\b", "ethenyl"),
    (r"\bdimethyl\b", "dimethyl"),
    (r"\bdiene\b", "diene"),
    (r"\balkene\b", "alkene"),
    (r"\balkane\b", "alkane"),
    (r"\bcarbonyl\b", "carbonyl"),
    (r"\baldehyde\b", "aldehyde"),
    (r"\bketone\b", "ketone"),
    (r"\bcarboxylic acid\b", "carboxylic acid"),
    (r"\bTollens(?:'?\s*reagent)?\b", "Tollens reagent"),
    (r"\bsubstituents?\b", "substituent"),
    (r"\bnomenclature\b", "nomenclature"),
    (r"\bhybridisati?on\b", "hybridization"),
    (r"\bpi bonds?\b", "pi bonds"),
    (r"\bsigma bonds?\b", "sigma bonds"),
    (r"\bπ\b", "pi"),
    (r"\bσ\b", "sigma"),
    (r"\bvalency\b", "valency"),
    (r"\blocant\b", "locant"),
    (r"\bibuprofen\b", "ibuprofen"),
    (r"\bFriedel[- ]Crafts\b", "Friedel Crafts"),
    (r"\bClemmensen\b", "Clemmensen"),
    (r"\bseparation\b", "separation"),
    (r"\binteraction\b", "interaction"),
    (r"\breductive workup\b", "reductive workup"),
    (r"\bselective oxidation\b", "selective oxidation"),
]


# Speak as names — never letter-spell reagents
_CHEM_NAMES = {
    "NaBH4": "sodium borohydride",
    "NaBH₄": "sodium borohydride",
    "LiAlH4": "lithium aluminium hydride",
    "LiAlH₄": "lithium aluminium hydride",
    "NH4OH": "ammonium hydroxide",
    "NH₄OH": "ammonium hydroxide",
    "Ag2O": "silver oxide",
    "Ag₂O": "silver oxide",
    "H2O": "water",
    "H₂O": "water",
    "O3": "ozone",
    "O₃": "ozone",
    "O2": "oxygen",
    "O₂": "oxygen",
    "N2": "nitrogen",
    "CO2": "carbon dioxide",
    "CO₂": "carbon dioxide",
    "Zn": "zinc",
    "H+": "acid",
    "H⁺": "acid",
    "H+.": "acid.",
    "KMnO4": "potassium permanganate",
    "KMnO₄": "potassium permanganate",
    "H2SO4": "sulphuric acid",
    "H₂SO₄": "sulphuric acid",
    "HCl": "hydrochloric acid",
    "NaOH": "sodium hydroxide",
    "KOH": "potassium hydroxide",
    "CH3COOH": "acetic acid",
    "CH₃COOH": "acetic acid",
    "Ag2O/NH4OH": "Tollens reagent",
    "Ag₂O/NH₄OH": "Tollens reagent",
    "Ag2O / NH4OH": "Tollens reagent",
    "MnO2": "manganese dioxide",
    "MnO₂": "manganese dioxide",
    "KI": "potassium iodide",
    "Pb(NO3)2": "lead nitrate",
    "Pb(NO₃)₂": "lead nitrate",
    "K2S2O3": "potassium thiosulfate",
    "K₂S₂O₃": "potassium thiosulfate",
}


_DIGIT = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


def _digit_word(n: str) -> str:
    return " ".join(_DIGIT.get(ch, ch) for ch in str(n))


def _looks_organic_formula(token: str) -> bool:
    """Organic / reagent blobs that TTS would letter-spam — not simple physics."""
    t = token.strip()
    if len(t) < 3:
        return False
    if re.search(r"→|↔|->", t):
        return True
    if re.search(r"C=C|C=O|R-CHO|COOH|CHO\b", t, re.I):
        return True
    if re.search(r"R[₀-₉0-9]", t) and re.search(r"[A-Za-z]", t):
        return True
    # Long chem strings like R1R2C=CR3R4
    if "=" in t and re.search(r"[A-Za-z]\d+[A-Za-z]", t):
        return True
    return False


def _summarize_dense_formulas(text: str) -> str:
    """Replace organic equation blobs with short natural phrases."""
    out = text

    # Full organic reaction with arrow / "gives"
    out = re.sub(
        r"[R0-9₁₂₃₄₅₆₇₈₉A-Za-z()=\+\-]+\s*(?:→|->|gives)\s*[R0-9₁₂₃₄₅₆₇₈₉A-Za-z()=\+\-\s,]+",
        lambda m: _phrase_for_reaction(m.group(0)),
        out,
    )

    def repl_token(m: re.Match) -> str:
        tok = m.group(0)
        if tok in _CHEM_NAMES:
            return _CHEM_NAMES[tok]
        if _looks_organic_formula(tok):
            return _phrase_for_formula_token(tok)
        return tok

    out = re.sub(
        r"(?<![A-Za-z])([A-Za-z][A-Za-z0-9₀-₉₁₂₃₄₅₆₇₈₉()=\+\-^/]{3,80})(?![A-Za-z])",
        repl_token,
        out,
    )
    return out


def _phrase_for_reaction(blob: str) -> str:
    b = blob.lower()
    if "c=c" in b or "alkene" in b or re.search(r"r\d*r?\d*c=c", b):
        if "c=o" in b or "carbonyl" in b:
            return "alkene breaks into carbonyl compounds"
        return "this alkene reaction"
    if "r-cho" in b or "aldehyde" in b:
        return "aldehyde oxidizes to carboxylic acid"
    if "nabh" in b or "reduction" in b:
        return "ketone reduces to alcohol"
    if "→" in blob or "->" in blob or "gives" in b:
        return "this reaction converts reactant to product"
    return "this reaction equation"


def _phrase_for_formula_token(tok: str) -> str:
    t = tok.strip()
    tl = t.lower().replace("₄", "4").replace("₂", "2").replace("₃", "3")
    if tl in {k.lower().replace("₄", "4") for k in _CHEM_NAMES}:
        for k, v in _CHEM_NAMES.items():
            if k.lower().replace("₄", "4").replace("₂", "2") == tl:
                return v
    if re.fullmatch(r"L[_₀-₉0-9]*eq", t, re.I) or tl in ("leq", "l_eq"):
        return "L equivalent"
    if re.fullmatch(r"[LM]\d*", t, re.I):
        # L1, L2, M — speak briefly, not letter-digit spam in a chain
        m = re.fullmatch(r"([A-Za-z])(\d*)", t)
        if m:
            return f"{m.group(1).upper()}" + (f" {_digit_word(m.group(2))}" if m.group(2) else "")
    if "c=o" in tl:
        return "carbonyl group"
    if "c=c" in tl:
        return "double bond"
    if "cho" in tl:
        return "aldehyde"
    if "cooh" in tl:
        return "carboxylic acid"
    if re.search(r"r[0-9].*c=c", tl):
        return "substituted alkene"
    if len(t) > 18 or t.count("=") >= 1:
        return "this formula"
    return "this expression"


def _speak_indexed_letters(token: str) -> str:
    """q1 → q one ; L1 → L one. Avoid spelling long organic blobs."""
    if _looks_organic_formula(token):
        return _phrase_for_formula_token(token)
    compact = re.sub(r"[^A-Za-z0-9]", "", token)
    parts = re.findall(r"[A-Za-z]\d*", compact)
    # Organic R1R2C… spam (4+ letter-digit chunks) — summarize
    if len(parts) >= 5 and re.search(r"R\d", compact, re.I):
        return _phrase_for_formula_token(token)
    if parts and "".join(parts) == compact and len(parts) >= 1:
        spoken = []
        for p in parts:
            if len(p) == 1:
                spoken.append(p)
            else:
                spoken.append(f"{p[0]} {_digit_word(p[1:])}")
        return " ".join(spoken)
    return re.sub(
        r"([A-Za-z])(\d+)",
        lambda m: f"{m.group(1)} {_digit_word(m.group(2))}",
        token,
    )


def _speak_chem_token(token: str) -> str:
    """H2O / Ag2O / NaBH4 — prefer spoken names, never N-A-B-H letter spam."""
    if token in _CHEM_NAMES:
        return _CHEM_NAMES[token]
    # Title-case lookup
    for k, v in _CHEM_NAMES.items():
        if k.lower() == token.lower():
            return v
    parts: list[str] = []
    for atom, num in re.findall(r"([A-Z][a-z]?)(\d*)", token):
        # Keep element symbol as one word (Na, not N a)
        parts.append(atom)
        if num:
            parts.append(_digit_word(num))
    if len(parts) >= 6:
        return "this reagent"
    return " ".join(parts) if parts else token


def _speak_side(expr: str) -> str:
    """Speak one side of a simple physics equation (may contain / + -)."""
    expr = expr.strip()
    if not expr:
        return expr
    if _looks_organic_formula(expr):
        return _phrase_for_formula_token(expr)
    chunks = re.split(r"(\s*[+\-]\s*)", expr)
    spoken: list[str] = []
    for ch in chunks:
        if not ch or not ch.strip():
            continue
        if re.fullmatch(r"\s*\+\s*", ch):
            spoken.append(" plus ")
            continue
        if re.fullmatch(r"\s*-\s*", ch):
            spoken.append(" minus ")
            continue
        piece = ch.strip()
        if "/" in piece:
            left, right = piece.split("/", 1)
            spoken.append(
                f"{_speak_indexed_letters(left)} upon {_speak_indexed_letters(right.strip())}"
            )
        else:
            spoken.append(_speak_indexed_letters(piece))
    return "".join(spoken).strip()


def _speak_fn_call(name: str, arg: str) -> str:
    arg_s = arg.strip()
    if re.search(r"infin", arg_s, re.I):
        arg_s = "infinity"
    return f"{name} of {_speak_indexed_letters(arg_s)}"


def _expand_inline_equations(text: str) -> str:
    """U(r) = Kq1q2/r + C  →  U of r equals K q one q two upon r plus C"""

    def repl_fn_eq(m: re.Match) -> str:
        left = _speak_fn_call(m.group(1), m.group(2))
        right = _speak_side(m.group(3))
        return f" {left} equals {right} "

    def repl_simple_eq(m: re.Match) -> str:
        left = m.group(1)
        if left.lower() in ("leq", "l_eq", "l eq"):
            left_s = "L equivalent"
        else:
            left_s = _speak_indexed_letters(left.replace("_", ""))
        right = _speak_side(m.group(2))
        return f" {left_s} equals {right} "

    rhs = r"([A-Za-z0-9][A-Za-z0-9_*/()+\-]*(?:\s*[+\-]\s*[A-Za-z0-9_*/()+\-]*){0,6})"

    text = re.sub(
        rf"\b([A-Za-z]{{1,8}})\(([^)]{{1,40}})\)\s*=\s*{rhs}",
        repl_fn_eq,
        text,
    )
    # L_eq / Leq / L1 = ...
    text = re.sub(
        rf"(?<!equals )\b(L_?eq|Leq|[A-Za-z]{{1,8}})\s*=\s*{rhs}",
        repl_simple_eq,
        text,
        flags=re.I,
    )
    return text


def _normalize_symbols(text: str) -> str:
    pairs = {
        "→": " gives ",
        "←": " from ",
        "↔": " equilibrium ",
        "⇒": " implies ",
        "∞": " infinity ",
        "≤": " less than or equal to ",
        "≥": " greater than or equal to ",
        "≠": " not equal to ",
        "≈": " approximately ",
        "×": " times ",
        "·": " dot ",
        "°": " degrees ",
        "Δ": " delta ",
        "δ": " delta ",
        "α": " alpha ",
        "β": " beta ",
        "γ": " gamma ",
        "θ": " theta ",
        "₁": "1",
        "₂": "2",
        "₃": "3",
        "₄": "4",
        "₅": "5",
        "₆": "6",
        "₇": "7",
        "₈": "8",
        "₉": "9",
        "₀": "0",
        "⁺": "+",
        "⁻": "-",
        "¹": "1",
        "²": " squared",
        "³": " cubed",
    }
    out = text
    for a, b in pairs.items():
        out = out.replace(a, b)
    out = re.sub(r"_(\d+)", lambda m: " " + _digit_word(m.group(1)), out)
    out = re.sub(r"\^(\d+)", lambda m: " to the power " + _digit_word(m.group(1)), out)
    return out


def _strip_devanagari(text: str) -> str:
    if not any("\u0900" <= ch <= "\u097F" for ch in text):
        return text
    cleaned = "".join(ch for ch in text if not ("\u0900" <= ch <= "\u097F"))
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,")
    if len(cleaned) < 16:
        return (
            "Dekho students, yeh concept carefully samajhte hain. "
            "Key idea screen pe formula ke through clear hoga."
        )
    return cleaned


def speak_given_item(given: str) -> str:
    """Short TTS-friendly phrase for a Given chip (used by planners too)."""
    g = (given or "").strip()
    if not g:
        return g
    # "Self-inductance of coil 1: L1" — keep words, soften trailing formula
    if ":" in g:
        label, rest = g.split(":", 1)
        rest = rest.strip()
        if rest in _CHEM_NAMES or _looks_organic_formula(rest) or re.fullmatch(r"[A-Za-z]_?\d*", rest):
            return f"{label.strip()}, {speakable(rest)}"
        return speakable(g)
    if g in _CHEM_NAMES or _looks_organic_formula(g):
        return speakable(g)
    return speakable(g)


def speakable(text: str) -> str:
    """Return narration text safer for TTS — natural phrases, not letter spam."""
    if not text:
        return text

    out = unicodedata.normalize("NFKC", text)
    out = _strip_devanagari(out)

    # Reagent names FIRST (before symbol normalize splits them)
    for tok, name in sorted(_CHEM_NAMES.items(), key=lambda kv: -len(kv[0])):
        out = out.replace(tok, name)

    out = _normalize_symbols(out)

    # Physics math first (so L_eq = ... is spoken cleanly)
    out = _expand_inline_equations(out)

    # Organic / dense chem equations → short spoken idea
    out = _summarize_dense_formulas(out)

    out = re.sub(r"\bC=C\b", "carbon-carbon double bond", out)
    out = re.sub(r"\bC=O\b", "carbonyl", out)
    out = re.sub(r"\bC-H\b", "C H bond", out)
    out = re.sub(r"\bC-C\b", "C C bond", out)
    out = re.sub(r"\bC-O\b", "C O bond", out)

    # Bare U(r) / PE(r) without equals
    out = re.sub(
        r"\b([A-Za-z]{1,4})\(([^)]{1,20})\)",
        lambda m: _speak_fn_call(m.group(1), m.group(2))
        if not _looks_organic_formula(m.group(0))
        else _phrase_for_formula_token(m.group(0)),
        out,
    )

    for pattern, repl in _WORD_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)

    # (A) → option A
    out = re.sub(r"\boption\s*\(\s*([A-D])\s*\)", r"option \1", out, flags=re.I)
    out = re.sub(r"\(\s*([A-D])\s*\)", r"option \1", out, flags=re.I)
    out = re.sub(r"\boption\s+option\b", "option", out, flags=re.I)

    # Structure dump in answer text — don't read bracketed chemistry essays
    out = re.sub(
        r"\[Structure:[^\]]{20,}\]",
        " the product structure shown on screen ",
        out,
        flags=re.I,
    )
    out = re.sub(
        r"\(Structure:[^)]{20,}\)",
        " the product structure shown on screen ",
        out,
        flags=re.I,
    )

    out = re.sub(r"\b(\d+),(\d+)-", r"\1 \2 ", out)
    out = re.sub(r"\b(\d+)-(\d+)-", r"\1 \2 ", out)
    # IUPAC locants: 6-oxo… / 1-ethyl… → six oxo / one ethyl
    out = re.sub(
        r"\b(\d+)-([A-Za-z])",
        lambda m: f"{_digit_word(m.group(1))} {m.group(2)}",
        out,
    )
    # 2M / 2L → two M (physics coefficients)
    out = re.sub(
        r"\b(\d+)([A-Za-z])\b",
        lambda m: f"{_digit_word(m.group(1))} {m.group(2)}",
        out,
    )

    # Collapse accidental letter-spam leftovers: "R one R two C" chains
    out = re.sub(
        r"(?:\b[A-Z]\s+(?:one|two|three|four|five|six|seven|eight|nine)\s+){3,}",
        "this formula ",
        out,
    )

    out = re.sub(r"\s*,\s*,+", ", ", out)
    out = re.sub(r"\s{2,}", " ", out).strip()

    if len(out) > 300:
        cut = out.find(" ", 170)
        if 170 < cut < 250 and ". " not in out[120:cut]:
            out = out[:cut] + ". " + out[cut + 1 :]

    return out
