"""Central settings for DoubtSolve.ai Remotion + Three.js pipeline."""

import os
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REMOTION_DIR = os.path.join(ROOT_DIR, "remotion")
OUTPUT_DIR = os.path.abspath(os.getenv("OUTPUT_DIR", os.path.join(ROOT_DIR, "output")))
TEMP_DIR = os.path.abspath(os.getenv("TEMP_DIR", os.path.join(ROOT_DIR, "temp")))
DEBUG_DIR = os.path.join(ROOT_DIR, "debug")

FPS = 30

# IMPORTANT: never combine reduced width/height with scale < 1 (that double-downscales).
QUALITY_PRESETS = {
    "FAST_PREVIEW": {
        "width": 1280,
        "height": 720,
        "scale": 1,
        "crf": 20,
        "jpeg_quality": 80,
        "label": "Fast preview (720p)",
    },
    "QUALITY_PREVIEW": {
        "width": 1920,
        "height": 1080,
        "scale": 1,
        "crf": 18,
        "jpeg_quality": 90,
        "label": "Quality preview (1080p)",
    },
    "FINAL_RENDER": {
        "width": 1920,
        "height": 1080,
        "scale": 1,
        "crf": 15,
        "jpeg_quality": 95,
        "label": "Final production (1080p)",
    },
    "NORMAL": {
        "width": 1920,
        "height": 1080,
        "scale": 1,
        "crf": 18,
        "jpeg_quality": 90,
        "label": "Quality preview (1080p)",
    },
    "HIGH_QUALITY": {
        "width": 1920,
        "height": 1080,
        "scale": 1,
        "crf": 15,
        "jpeg_quality": 95,
        "label": "Final production (1080p)",
    },
}


def resolve_quality(name=None):
    key = (name or "QUALITY_PREVIEW").upper()
    return QUALITY_PRESETS.get(key, QUALITY_PRESETS["QUALITY_PREVIEW"])
