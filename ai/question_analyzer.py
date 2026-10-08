"""Question Analyzer — extracts teaching-ready question context for the video pipeline."""

import re
from .gemini import GeminiClient


OCR_FAIL_MARKERS = (
    "please transcribe",
    "transcribe the academic",
    "solve it completely",
    "from this image and solve",
    "from this pdf and solve",
    "waiting for upload",
)

ANALYZER_SYSTEM_PROMPT = """You are an expert academic multimodal OCR and teaching triage system for DoubtSolve.ai.

You will receive an IMAGE and/or TEXT of a student question (screenshot, handwritten, exam paper, PDF page, or typed text).

YOUR MANDATORY TASKS:
1. READ the actual question from the image/text. Do OCR carefully (chemistry formulas, subscripts, options).
2. Decide if it is a genuine educational question (Math, Physics, Chemistry, Biology, CS, Science/Engineering).
3. If NOT educational, return:
{
  "isEducationalQuestion": false,
  "reason": "The uploaded input does not contain an educational question."
}
4. If YES:
   - Put the FULL verbatim question (+ options if MCQ) into questionText
   - Detect the REAL subject (Chemistry stays Chemistry — never invent a different subject)
   - NEVER copy system instructions into questionText
   - NEVER invent a different sample problem (no default projectile / water molecule examples)

Return ONLY this JSON:
{
  "isEducationalQuestion": true,
  "subject": "Physics | Mathematics | Chemistry | Biology | Computer Science | General Science",
  "classLevel": "10 | 11 | 12 | College | General",
  "topic": "<specific topic from THIS question>",
  "subtopic": "<specific subtopic>",
  "difficulty": "Easy | Medium | Hard",
  "language": "English | Hindi | Mixed",
  "questionText": "<VERBATIM QUESTION AND OPTIONS FROM THE INPUT>",
  "questionType": "numerical | conceptual | derivation | mcq | prove | graph",
  "requiredCalculation": true,
  "visualizable": true,
  "suggestedVisual": "projectile | free_fall | circular | vectors | graph | molecule | diagram | equation_board | cavity | field",
  "knownValues": ["list values actually present in the question"],
  "askToFind": "<what student must find>",
  "studentNeed": "<one sentence: what confusion this video should clear>",
  "ocrConfidence": "high | medium | low"
}
"""

OCR_RETRY_PROMPT = """OCR RETRY — previous pass failed to extract a real question.

Look ONLY at the attached image. Transcribe EVERY readable line of the academic question.
Preserve chemical formulas, charges, subscripts, and MCQ options exactly.

Return ONLY JSON with the same schema as before.
If the image is unreadable, return:
{"isEducationalQuestion": false, "reason": "Could not read a clear academic question from the image."}
"""


def looks_like_failed_ocr(question_text: str) -> bool:
    text = (question_text or "").strip().lower()
    if not text or len(text) < 12:
        return True
    if any(m in text for m in OCR_FAIL_MARKERS):
        return True
    # Meta / instruction leakage
    if text.startswith("please ") and "question" in text and len(text) < 120:
        return True
    return False


def is_usable_analysis(analysis: dict) -> bool:
    if not isinstance(analysis, dict):
        return False
    if not analysis.get("isEducationalQuestion"):
        return False
    return not looks_like_failed_ocr(analysis.get("questionText", ""))


class QuestionAnalyzer:
    def __init__(self, gemini_client=None):
        self.gemini = gemini_client or GeminiClient()

    def analyze(self, input_path_or_text):
        parsed_input = GeminiClient.extract_text_or_images_from_input(input_path_or_text)
        images = parsed_input.get("images") or []
        raw_text = (parsed_input.get("text") or "").strip()

        # Pure image uploads: do not treat the helper instruction as the question body
        user_payload = {
            "text": (
                "The academic question is in the attached image. "
                "Transcribe it verbatim into questionText. "
                "Do not invent another problem."
                if images and (not raw_text or looks_like_failed_ocr(raw_text))
                else raw_text
            ),
            "images": images,
        }

        if self.gemini.is_live():
            res = self.gemini.generate_json_with_retry(
                ANALYZER_SYSTEM_PROMPT, user_payload, max_retries=3, timeout=90
            )
            if is_usable_analysis(res):
                return res

            # Strong vision-only retry when first pass leaked instructions or failed OCR
            if images:
                print("[QuestionAnalyzer] OCR weak/failed — retrying with vision-only prompt...")
                retry_payload = {
                    "text": "Transcribe the question shown in this image. Return JSON only.",
                    "images": images,
                }
                res2 = self.gemini.generate_json_with_retry(
                    OCR_RETRY_PROMPT + "\n\n" + ANALYZER_SYSTEM_PROMPT,
                    retry_payload,
                    max_retries=2,
                    timeout=120,
                )
                if is_usable_analysis(res2):
                    return res2

            if isinstance(res, dict) and res.get("isEducationalQuestion") is False:
                return res

        # Offline / failed path — only accept real typed text, never OCR helper strings
        if images and looks_like_failed_ocr(raw_text):
            return {
                "isEducationalQuestion": False,
                "reason": (
                    "Could not read the question from the uploaded image (OCR failed). "
                    "Check Gemini API / MixRoute vision, or paste the question as text."
                ),
                "ocrFailed": True,
            }

        if not raw_text or len(raw_text) < 5 or looks_like_failed_ocr(raw_text):
            return {
                "isEducationalQuestion": False,
                "reason": "No readable academic question found in the input.",
                "ocrFailed": True,
            }

        lower = raw_text.lower()
        if any(k in lower for k in ["meme", "selfie", "random wallpaper"]):
            return {
                "isEducationalQuestion": False,
                "reason": "The uploaded input does not contain an educational question.",
            }

        subject = "General Science"
        suggested = "equation_board"
        if any(k in lower for k in ("chemistry", "molecule", "atom", "bond", "orbital", "hybrid", "organic", "inorganic", "mole", "acid", "base", "ph ", "reaction")):
            subject = "Chemistry"
            suggested = "molecule"
        elif any(k in lower for k in ("physics", "projectile", "thrown", "force", "velocity", "electric", "magnetic", "optics")):
            subject = "Physics"
            if any(k in lower for k in ("projectile", "thrown", "range", "trajectory")):
                suggested = "projectile"
        elif any(k in lower for k in ("math", "algebra", "triangle", "integral", "derivative", "geometry")):
            subject = "Mathematics"
        elif any(k in lower for k in ("biology", "cell", "dna", "enzyme")):
            subject = "Biology"

        topic_guess = "General"
        m = re.search(r"(?:topic|chapter)\s*[:\-]\s*([A-Za-z0-9 \-/]+)", raw_text, re.I)
        if m:
            topic_guess = m.group(1).strip()[:60]

        return {
            "isEducationalQuestion": True,
            "subject": subject,
            "classLevel": "12",
            "topic": topic_guess,
            "subtopic": topic_guess,
            "difficulty": "Medium",
            "language": "English",
            "questionText": raw_text,
            "questionType": "numerical",
            "requiredCalculation": True,
            "visualizable": True,
            "suggestedVisual": suggested,
            "knownValues": [],
            "askToFind": "",
            "studentNeed": "Understand the concept and reach the correct answer step by step.",
            "ocrConfidence": "low",
        }
