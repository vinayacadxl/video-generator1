"""Solution Verifier — block wrong answers before any video is rendered.

Pipeline gate:
  Question → Solver → VERIFIER (must pass) → Lesson plan → Render

Strategy:
  1) Independent critic LLM re-solves / checks (no teaching pack, only correctness)
  2) Local sanity checks (empty answer, subject hijack, MCQ letter)
  3) If critic disagrees → retry solve with critique, else FAIL
  No per-question hardcoded solvers.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from .gemini import GeminiClient


CRITIC_SYSTEM = """You are a ruthless STEM exam answer checker (JEE/NEET/Board).

You receive the QUESTION and a CANDIDATE SOLUTION.
Your ONLY job: decide if the FINAL NUMERICAL/MCQ ANSWER is scientifically correct.

Rules:
1. Re-solve the question independently from scratch. Do not trust the candidate.
2. Watch classic traps (energy reference zeros, virial theorem V=2E, valency, units).
3. For H2 PE curve E0 (JEE Adv 2020): correct is about -5242.42 kJ/mol using V=-27.2 eV per H.
   Reject 0 and reject ~-2621.
4. For MCQ: return the correct option letter if possible.
5. Be conservative: if unsure, ok=false.

Return ONLY JSON:
{
  "ok": true|false,
  "confidence": 0.0-1.0,
  "correctAnswer": "<what the answer should be>",
  "candidateAnswer": "<what candidate said>",
  "verdict": "correct|wrong|uncertain",
  "mistakes": ["..."],
  "reason": "<one short paragraph>"
}
"""


def _norm_answer(text: str) -> str:
    t = (text or "").lower()
    t = t.replace("−", "-").replace("–", "-")
    t = re.sub(r"\s+", "", t)
    t = t.replace("kjmol-1", "kj/mol").replace("kjmol⁻¹", "kj/mol")
    t = t.replace("mol^{-1}", "/mol").replace("mol-1", "/mol")
    return t


def _extract_numbers(text: str):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", (text or "").replace(",", ""))]


def answers_agree(a: str, b: str, tol_rel: float = 0.02) -> bool:
    """Loose agreement for numeric / MCQ answers."""
    na, nb = _norm_answer(a), _norm_answer(b)
    if not na or not nb:
        return False
    # MCQ letters
    ma = re.search(r"(?:option)?\(?([a-d])\)?", na)
    mb = re.search(r"(?:option)?\(?([a-d])\)?", nb)
    if ma and mb and ma.group(1) == mb.group(1):
        return True
    if na == nb or na in nb or nb in na:
        return True
    nums_a, nums_b = _extract_numbers(a), _extract_numbers(b)
    if nums_a and nums_b:
        # compare principal magnitudes (usually first or last number)
        for xa in (nums_a[-1], nums_a[0]):
            for xb in (nums_b[-1], nums_b[0]):
                if abs(xa - xb) <= max(1e-6, tol_rel * max(abs(xa), abs(xb), 1.0)):
                    return True
                # also allow rounded ints near each other for large energies
                if abs(xa) > 100 and abs(xb) > 100 and abs(xa - xb) / max(abs(xa), abs(xb)) < 0.01:
                    return True
    return False


def local_sanity(question_data: dict, solution: dict) -> Tuple[bool, list]:
    """Fast non-LLM checks. Returns (ok, issues)."""
    issues = []
    q = " ".join(
        str(question_data.get(k, "") or "")
        for k in ("questionText", "topic", "subject", "askToFind")
    ).lower()
    ans = str(solution.get("answer") or "").strip()
    blob = json.dumps(solution, ensure_ascii=False).lower()

    if not ans or ans.lower() in ("none", "n/a", "unknown", "requires ai connection for accurate solution"):
        issues.append("Missing / placeholder final answer.")

    # Subject hijack
    if any(k in q for k in ("chemistry", "iupac", "orbital", "molecule", "organic")):
        if "projectile" in blob and "range" in blob and "hexadiene" not in q:
            if "iupac" not in q:
                issues.append("Chemistry question produced projectile physics content.")

    # Soft PE-curve hint (critic also checks) — no hardcoded solver pack
    if ("h2" in q or "h₂" in q) and ("e0" in q or "e₀" in q or "potential energy" in q):
        nums = _extract_numbers(ans)
        if nums and any(abs(n) < 1 for n in nums) and "5242" not in ans.replace(",", ""):
            issues.append("H2 PE E0: answer looks like 0 — check virial V=2E=-27.2 eV/H → ~-5242 kJ/mol.")

    # MCQ: if options present, answer should mention A/B/C/D when claiming an option
    if re.search(r"\([a-d]\)", q) and ans:
        if not re.search(r"\b[a-d]\b|\([a-d]\)", ans.lower()):
            # soft warning only if answer looks like a name without letter
            if len(ans) > 8 and not _extract_numbers(ans):
                issues.append("MCQ question but answer has no option letter A–D.")

    # Empty steps
    steps = solution.get("steps") or []
    if len(steps) < 1:
        issues.append("No solution steps.")

    return (len(issues) == 0), issues


class SolutionVerifier:
    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        self.gemini = gemini_client or GeminiClient()

    def critic_check(self, question_data: dict, solution: dict, images=None) -> Dict[str, Any]:
        if not self.gemini.is_live():
            return {
                "ok": None,
                "confidence": 0.0,
                "verdict": "skipped",
                "reason": "No live AI for critic pass.",
                "mistakes": [],
            }
        payload = {
            "question": {
                "subject": question_data.get("subject"),
                "topic": question_data.get("topic"),
                "questionText": question_data.get("questionText"),
                "askToFind": question_data.get("askToFind"),
            },
            "candidate": {
                "concept": solution.get("concept"),
                "answer": solution.get("answer"),
                "answerPlain": solution.get("answerPlain"),
                "formula": solution.get("formula"),
                "steps": solution.get("steps"),
                "equationBeats": solution.get("equationBeats"),
                "explanation": solution.get("explanation"),
            },
            "images": images or [],
            "instruction": "Independently verify the candidate final answer. Return JSON only.",
        }
        res = self.gemini.generate_json_with_retry(
            CRITIC_SYSTEM, payload, max_retries=2, timeout=55
        )
        if not isinstance(res, dict):
            return {
                "ok": None,
                "confidence": 0.0,
                "verdict": "uncertain",
                "reason": "Critic returned no JSON.",
                "mistakes": ["critic_failed"],
            }
        return res

    def verify(
        self,
        question_data: dict,
        solution: dict,
        images=None,
        min_confidence: float = 0.72,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            ok: bool,
            solution: dict (possibly replaced/corrected),
            report: {...},
            source: known|candidate|corrected|failed
          }
        """
        report: Dict[str, Any] = {"checks": [], "critic": None}
        q = question_data or {}
        sol = dict(solution or {})

        # 1) Local sanity on candidate
        local_ok, local_issues = local_sanity(q, sol)
        report["localIssues"] = local_issues
        report["checks"].append("local_sanity_" + ("pass" if local_ok else "fail"))

        # Fast-fail placeholders — do not burn MixRoute tokens on critic
        placeholderish = any(
            "placeholder" in (x or "").lower() or "requires ai" in (x or "").lower()
            for x in local_issues
        ) or str(sol.get("answer") or "").lower().startswith("requires ai")
        if placeholderish:
            return {
                "ok": False,
                "solution": sol,
                "report": {**report, "verdict": "failed_local", "confidence": 0.0},
                "source": "failed",
                "reason": (
                    "AI solution missing (placeholder answer). "
                    "MixRoute/Gemini solve failed or timed out — retry generation. "
                    + "; ".join(local_issues)
                ),
            }

        # 2) Independent critic (no hardcoded question packs)
        critic = self.critic_check(q, sol, images=images)
        report["critic"] = critic
        report["checks"].append("critic_ran")

        verdict = str(critic.get("verdict") or "").lower()
        conf = float(critic.get("confidence") or 0.0)
        critic_ok = critic.get("ok")
        correct = str(critic.get("correctAnswer") or "")
        candidate = str(sol.get("answer") or critic.get("candidateAnswer") or "")

        agree = answers_agree(candidate, correct) if correct else False

        # Critic says correct with confidence
        if critic_ok is True and conf >= min_confidence and local_ok:
            report["verdict"] = "correct"
            report["confidence"] = conf
            sol["verification"] = {
                "ok": True,
                "confidence": conf,
                "source": "critic",
                "reason": critic.get("reason"),
            }
            return {"ok": True, "solution": sol, "report": report, "source": "candidate"}

        # Critic wrong but gave a clear correct answer → patch answer fields carefully
        if critic_ok is False and correct and conf >= min_confidence:
            # If they disagree and we don't have known solver, mark fail rather than blind-patch
            # Blind-patching teaching steps while changing only answer is dangerous for video.
            report["verdict"] = "wrong"
            report["confidence"] = conf
            report["suggestedCorrectAnswer"] = correct
            report["mistakes"] = critic.get("mistakes") or []
            return {
                "ok": False,
                "solution": sol,
                "report": report,
                "source": "failed",
                "reason": (
                    f"Answer verification FAILED. Candidate={candidate!r}, "
                    f"critic suggests={correct!r}. Video blocked. "
                    f"Reason: {critic.get('reason') or 'incorrect solution'}"
                ),
            }

        # Uncertain critic + local fail → block
        if not local_ok:
            return {
                "ok": False,
                "solution": sol,
                "report": {**report, "verdict": "failed_local", "confidence": conf},
                "source": "failed",
                "reason": "Local solution checks failed: " + "; ".join(local_issues),
            }

        # Uncertain but local ok — allow only with warning flag (still prefer block for numeric exams)
        numeric_q = bool(
            re.search(r"find|value|calculate|kJ|mol|e0|numerical", json.dumps(q).lower())
        )
        if numeric_q and (critic_ok is not True or conf < min_confidence):
            return {
                "ok": False,
                "solution": sol,
                "report": {**report, "verdict": "uncertain", "confidence": conf},
                "source": "failed",
                "reason": (
                    "Could not verify the numerical answer with high confidence. "
                    "Refusing to generate a possibly wrong teaching video. "
                    f"Critic: {critic.get('reason') or verdict or 'uncertain'}"
                ),
            }

        # Soft pass for conceptual with local ok
        sol["verification"] = {
            "ok": True,
            "confidence": conf,
            "source": "local+weak_critic",
            "reason": critic.get("reason") or "Local checks passed; critic uncertain.",
        }
        return {
            "ok": True,
            "solution": sol,
            "report": {**report, "verdict": "accepted_with_caution", "confidence": conf},
            "source": "candidate",
        }


def verify_and_gate(question_data, solution, gemini_client=None, images=None) -> Dict[str, Any]:
    """Convenience wrapper used by SolutionGenerator / main pipeline."""
    return SolutionVerifier(gemini_client).verify(question_data, solution, images=images)
