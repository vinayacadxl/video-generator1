"""Remotion renderer bridge — Remotion 2D + Three.js 3D."""

import json
import os
import shutil
import subprocess

from config.settings import FPS, REMOTION_DIR, resolve_quality


def find_npm():
    return shutil.which("npm") or shutil.which("npm.cmd")


def find_npx():
    return shutil.which("npx") or shutil.which("npx.cmd")


class RemotionRenderer:
    """Renders Lesson JSON scenes via Remotion (2D) + Three.js (3D)."""

    def __init__(self, quality="QUALITY_PREVIEW", remotion_dir=None):
        self.quality_name = quality
        self.quality = resolve_quality(quality)
        self.remotion_dir = remotion_dir or REMOTION_DIR
        self.fps = FPS

    def ensure_dependencies(self):
        node_modules = os.path.join(self.remotion_dir, "node_modules", "remotion")
        if os.path.isdir(node_modules):
            return True
        npm = find_npm()
        if not npm:
            print("[Remotion] npm not found. Install Node.js to render videos.")
            return False
        print("[Remotion] Installing engine dependencies (first run)...")
        try:
            subprocess.run(
                [npm, "install"],
                cwd=self.remotion_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except Exception as e:
            print(f"[Remotion] npm install failed: {e}")
            return False

    def _build_render_cmd(self, composition, output_mp4, props_file):
        q = self.quality
        width = int(q.get("width", 1920))
        height = int(q.get("height", 1080))
        crf = int(q.get("crf", 18))
        jpeg_q = int(q.get("jpeg_quality", 90))

        # Never pass scale<1 with reduced width (double-downscale caused 480p mush).
        cmd = [
            find_npx(),
            "remotion",
            "render",
            "src/index.ts",
            composition,
            os.path.abspath(output_mp4),
            f"--props={os.path.abspath(props_file)}",
            f"--width={width}",
            f"--height={height}",
            "--scale=1",
            f"--crf={crf}",
            f"--jpeg-quality={jpeg_q}",
            "--image-format=jpeg",
            "--gl=angle",
            "--log=error",
        ]
        return cmd

    def render_scene(
        self,
        scene_spec,
        output_mp4,
        solution=None,
        title="",
        subject="",
        topic="",
        duration=None,
        props_path=None,
    ):
        if not self.ensure_dependencies():
            return False
        if not find_npx():
            print("[Remotion] npx not found.")
            return False

        duration_s = float(duration or scene_spec.get("duration") or 6.0)
        props = {
            "scene": scene_spec,
            "solution": solution or {},
            "title": title,
            "subject": subject,
            "topic": topic,
            "durationInSeconds": duration_s,
            "fps": self.fps,
        }

        props_file = props_path or (output_mp4 + ".props.json")
        os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump(props, f, indent=2)

        cmd = self._build_render_cmd("SceneClip", output_mp4, props_file)
        print(
            f"[Remotion] Rendering {scene_spec.get('id')} "
            f"({scene_spec.get('visualMode', '2D')}, {self.quality.get('width')}x{self.quality.get('height')}) "
            f"→ {os.path.basename(output_mp4)}"
        )
        try:
            res = subprocess.run(
                cmd,
                cwd=self.remotion_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                err = (res.stderr or res.stdout or "").strip()
                print(f"[Remotion ERROR] {scene_spec.get('id')}: {err[-2000:]}")
                return False
            return os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 1000
        except Exception as e:
            print(f"[Remotion ERROR] {e}")
            return False

    def render_full_lesson(self, lesson, output_mp4, timeline=None):
        if not self.ensure_dependencies() or not find_npx():
            return False
        props = {"lesson": lesson, "fps": self.fps, "timeline": timeline or []}
        props_file = output_mp4 + ".lesson.props.json"
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump(props, f, indent=2)
        cmd = self._build_render_cmd("LessonVideo", output_mp4, props_file)
        try:
            res = subprocess.run(cmd, cwd=self.remotion_dir, capture_output=True, text=True)
            return res.returncode == 0 and os.path.exists(output_mp4)
        except Exception as e:
            print(f"[Remotion ERROR] full lesson: {e}")
            return False
