"""Gemini AI API Client.
Handles Multimodal input (Text, Image, PDF), MixRoute OpenAI-compatible proxy,
native Gemini SDK, retry logic with exponential backoff, RGBA-safe image encoding, and structured JSON parsing.
"""

import os
import io
import time
import json
import base64
import requests
from PIL import Image

try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None


class GeminiClient:
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = os.getenv("GEMINI_BASE_URL", "").rstrip("/")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self._configured = False
        self.use_mixroute = bool(self.base_url and self.api_key)

        if self.use_mixroute:
            self._configured = True
            print(f"[GeminiClient] Using MixRoute Gateway: {self.base_url} (Model: {self.model_name})")
        elif self.api_key and genai:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self._configured = True
                print(f"[GeminiClient] Using Direct Google Gemini SDK (Model: {self.model_name})")
            except Exception as e:
                print(f"[GeminiClient WARNING] Failed to configure Gemini SDK: {e}")
                self._configured = False
        else:
            self._configured = False

    def is_live(self):
        return self._configured

    @staticmethod
    def extract_text_or_images_from_input(input_path_or_text):
        """
        Parses text, image, or PDF files.
        Returns:
            dict: {"text": str, "images": list[PIL.Image]}
        """
        if not input_path_or_text:
            return {"text": "", "images": []}

        # Check if it's a file path
        if isinstance(input_path_or_text, str) and os.path.exists(input_path_or_text):
            ext = os.path.splitext(input_path_or_text)[1].lower()
            
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                img = Image.open(input_path_or_text)
                # Keep helper text empty-ish so analyzer never treats it as the question body
                return {
                    "text": "",
                    "images": [img],
                    "sourcePath": input_path_or_text,
                    "sourceType": "image",
                }
            
            elif ext == ".pdf":
                extracted_text = ""
                images = []
                if fitz:
                    doc = fitz.open(input_path_or_text)
                    for page_idx in range(min(len(doc), 3)):
                        page = doc[page_idx]
                        extracted_text += page.get_text() + "\n"
                        pix = page.get_pixmap(dpi=160)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        images.append(img)
                    doc.close()
                return {
                    "text": extracted_text.strip(),
                    "images": images,
                    "sourcePath": input_path_or_text,
                    "sourceType": "pdf",
                }
            
            elif ext in [".txt", ".md"]:
                with open(input_path_or_text, "r", encoding="utf-8") as f:
                    return {"text": f.read().strip(), "images": []}

        # Treat as raw text
        return {"text": str(input_path_or_text).strip(), "images": []}

    def _call_mixroute(self, system_instruction, user_content, timeout=90):
        """Calls OpenAI-compatible MixRoute API endpoint with RGBA-safe image encoding."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        content_parts = []
        user_text = ""
        images = []

        if isinstance(user_content, dict):
            images = user_content.get("images", []) or []
            # Prefer explicit text; never JSON-dump PIL images
            if user_content.get("text"):
                user_text = str(user_content["text"])
            else:
                safe = {
                    k: v
                    for k, v in user_content.items()
                    if k not in ("images",) and not hasattr(v, "mode")
                }
                user_text = json.dumps(safe, indent=2) if safe else (
                    "Read the attached image(s) carefully and follow the system instruction."
                    if images
                    else ""
                )
        else:
            user_text = str(user_content)

        if images:
            if user_text:
                content_parts.append({"type": "text", "text": user_text})
            else:
                content_parts.append({
                    "type": "text",
                    "text": "Read the attached academic question image and respond in JSON.",
                })
            for img in images:
                # Convert RGBA/P/LA to RGB with clean white background
                if img.mode in ("RGBA", "LA", "P"):
                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "RGBA":
                        rgb_img.paste(img, mask=img.split()[3])
                    else:
                        rgb_img.paste(img.convert("RGB"))
                    img_to_send = rgb_img
                elif img.mode != "RGB":
                    img_to_send = img.convert("RGB")
                else:
                    img_to_send = img

                # Keep images small — MixRoute often hangs on huge multimodal payloads
                max_dim = int(os.getenv("MIXROUTE_IMAGE_MAX_DIM", "1024"))
                if max(img_to_send.size) > max_dim:
                    img_to_send.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                buf = io.BytesIO()
                img_to_send.save(buf, format="JPEG", quality=78)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })
        else:
            content_parts = user_text

        messages = [
            {"role": "system", "content": system_instruction + "\nRespond strictly in valid JSON format."},
            {"role": "user", "content": content_parts}
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1
        }

        # (connect, read) — fail stuck reads faster than a single giant hang
        read_timeout = max(20, int(timeout))
        res = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=(15, read_timeout),
        )
        if res.status_code == 200:
            data = res.json()
            return data["choices"][0]["message"]["content"]
        else:
            raise RuntimeError(f"MixRoute API Error {res.status_code}: {res.text[:800]}")

    def generate_json_with_retry(self, system_instruction, user_content, max_retries=3, timeout=90):
        """
        Generates structured JSON output with exponential backoff.
        """
        if not self._configured:
            return None

        # Vision calls need more time than plain text
        has_images = isinstance(user_content, dict) and bool(user_content.get("images"))
        call_timeout = max(timeout, 120 if has_images else timeout)

        backoff = 1.5
        for attempt in range(max_retries):
            try:
                if self.use_mixroute:
                    raw_text = self._call_mixroute(
                        system_instruction, user_content, timeout=call_timeout
                    )
                else:
                    prompt_parts = []
                    if isinstance(user_content, dict):
                        if user_content.get("text"):
                            prompt_parts.append(user_content["text"])
                        if user_content.get("images"):
                            for img in user_content["images"]:
                                if img.mode != "RGB":
                                    img = img.convert("RGB")
                                prompt_parts.append(img)
                    else:
                        prompt_parts.append(str(user_content))
                    prompt_parts.insert(0, f"System Instruction:\n{system_instruction}\n\nRespond ONLY in valid parseable JSON.")
                    response = self.model.generate_content(prompt_parts)
                    raw_text = response.text

                raw_text = raw_text.strip()
                parsed = self._parse_json_loose(raw_text)
                if parsed is not None:
                    return parsed
                raise RuntimeError(f"JSON parse failed. Head: {raw_text[:240]!r}")
            except Exception as e:
                print(f"[GeminiClient Attempt {attempt+1} ERROR] {e}")
                time.sleep(backoff)
                backoff *= 1.5

        return None

    @staticmethod
    def _parse_json_loose(raw_text: str):
        """Parse model JSON; tolerate markdown fences and truncated trailing braces."""
        if not raw_text:
            return None
        clean = raw_text.strip()
        if "```json" in clean:
            clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean:
            clean = clean.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Extract outermost object
        start = clean.find("{")
        end = clean.rfind("}")
        if start >= 0 and end > start:
            chunk = clean[start : end + 1]
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                # Truncated JSON: close open braces/brackets
                repaired = chunk.rstrip().rstrip(",")
                open_curly = repaired.count("{") - repaired.count("}")
                open_square = repaired.count("[") - repaired.count("]")
                # Trim to last complete-looking string/value
                if repaired.count('"') % 2 == 1:
                    repaired += '"'
                repaired += "]" * max(0, open_square) + "}" * max(0, open_curly)
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    return None
        return None
