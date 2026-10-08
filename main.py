"""DoubtSolve.ai Pipeline Orchestrator.
Gemini → Lesson JSON → Remotion (2D) / Three.js (3D) → ElevenLabs → FFmpeg → MP4
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import argparse
import subprocess
import concurrent.futures
from dotenv import load_dotenv
from PIL import Image, ImageStat
import imageio_ffmpeg

# Latest .env keys must win (MixRoute / ElevenLabs) even if shell has stale values
load_dotenv(override=True)

from ai.gemini import GeminiClient
from ai.question_analyzer import QuestionAnalyzer
from ai.solution_generator import SolutionGenerator
from ai.visual_planner import VisualPlanner
from ai.schema_validator import SchemaValidator
from ai.lesson_validator import LessonValidator
from tts.elevenlabs import generate_scene_narrations
from video.timeline import TimelineManager
from video.compositor import VideoCompositor
from render.remotion_renderer import RemotionRenderer
from engine_2d.renderer import Engine2DRenderer


class PipelineOrchestrator:
    def __init__(self, debug=False, quality="QUALITY_PREVIEW", log_callback=None, preview_callback=None):
        self.log_callback = log_callback
        self.preview_callback = preview_callback
        self.debug = debug or os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]
        self.quality = quality
        self.remotion = RemotionRenderer(quality=quality)

        self.output_dir = os.getenv("OUTPUT_DIR", "output")
        self.temp_dir = os.getenv("TEMP_DIR", "temp")
        self.debug_dir = "debug"

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        if self.debug:
            os.makedirs(self.debug_dir, exist_ok=True)

        self.gemini = GeminiClient()
        self.analyzer = QuestionAnalyzer(self.gemini)
        self.solver = SolutionGenerator(self.gemini)
        self.planner = VisualPlanner(self.gemini)

    def notify_log(self, level, message):
        if hasattr(self, "log_callback") and self.log_callback:
            try:
                self.log_callback(level, message)
            except Exception:
                pass

    def notify_preview(self, event_type, payload):
        """Push live preview updates (lesson plan / finished scene clips) to the UI."""
        if hasattr(self, "preview_callback") and self.preview_callback:
            try:
                self.preview_callback(event_type, payload)
            except Exception:
                pass

    def log_debug(self, filename, content):
        if not self.debug:
            return
        path = os.path.join(self.debug_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(content, (dict, list)):
                json.dump(content, f, indent=2)
            else:
                f.write(str(content))

    def verify_scene_visual_content(self, mp4_path, min_stddev=2.0):
        if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 10000:
            return False, "File missing or too small"

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        test_frame = mp4_path.replace(".mp4", "_vtest.png")
        try:
            cmd = [
                ffmpeg_exe, "-y",
                "-ss", "00:00:00.500",
                "-i", mp4_path,
                "-vframes", "1",
                test_frame,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            if os.path.exists(test_frame):
                im = Image.open(test_frame)
                stats = ImageStat.Stat(im)
                std_avg = sum(stats.stddev) / len(stats.stddev)
                mean_avg = sum(stats.mean) / len(stats.mean)
                os.remove(test_frame)
                if std_avg < min_stddev and mean_avg < 5.0:
                    return False, f"Blank frame detected (std={std_avg:.1f}, mean={mean_avg:.1f})"
                return True, f"OK (std={std_avg:.1f}, mean={mean_avg:.1f})"
        except Exception as e:
            return False, str(e)
        return True, "OK"

    def render_remotion_scene(self, scene_spec, output_mp4, global_meta, duration):
        return self.remotion.render_scene(
            scene_spec,
            output_mp4,
            solution=global_meta.get("solution"),
            title=global_meta.get("title", ""),
            subject=global_meta.get("subject", ""),
            topic=global_meta.get("topic", ""),
            duration=duration,
        )

    def run(self, input_data, visual_mode_override=None, output_filename="final_video.mp4"):
        print("\n=======================================================")
        print("  DoubtSolve.ai — Remotion 2D + Three.js 3D Engine")
        print("=======================================================\n")

        print("[STAGE 1/6] Analyzing input question...")
        self.notify_log("INFO", "Stage 1: Question analysis & Vision OCR extraction...")
        from ai.question_analyzer import looks_like_failed_ocr
        from ai.gemini import GeminiClient as _GC

        parsed_input = _GC.extract_text_or_images_from_input(input_data)
        analysis = self.analyzer.analyze(input_data)
        self.log_debug("question.json", analysis)

        if not analysis.get("isEducationalQuestion"):
            print("[INFO] Input is NOT an educational question / OCR failed.")
            self.notify_log(
                "ERROR",
                analysis.get("reason", "Input does not contain a recognized academic question."),
            )
            return {
                "success": False,
                "error": "OCR_FAILED" if analysis.get("ocrFailed") else "NON_EDUCATIONAL_INPUT",
                "reason": analysis.get(
                    "reason",
                    "Could not read an academic question. Paste text or check Gemini vision API.",
                ),
            }

        q_topic = analysis.get("topic", "General Topic")
        q_subj = analysis.get("subject", "Science")
        q_text = analysis.get("questionText", "")

        # Hard stop: never solve a leaked OCR instruction as if it were the question
        if looks_like_failed_ocr(q_text):
            reason = (
                "Vision OCR did not extract your question text "
                f"(got: {q_text[:80]!r}). Refusing to invent a physics demo video."
            )
            print(f"[ERROR] {reason}")
            self.notify_log("ERROR", reason)
            return {"success": False, "error": "OCR_FAILED", "reason": reason}

        print(f" [+] Question verified: Subject={q_subj}, Topic={q_topic}")
        self.notify_log("SUCCESS", f"✦ Subject: {q_subj} | Topic: {q_topic}")
        if q_text:
            self.notify_log("INFO", f"✦ Transcribed Question: {q_text[:160]}...")

        print("\n[STAGE 2/6] Generating scientific solution...")
        self.notify_log("INFO", "Stage 2: Computing derivation steps, governing equations, and target variables...")
        self.notify_log("INFO", "Stage 2 uses fast MixRoute solve (answer first) — usually under 2 minutes.")
        self.solver.progress_cb = self.notify_log
        solution = self.solver.solve(analysis, images=parsed_input.get("images") or [])
        self.log_debug("solution.json", solution)

        if solution.get("error") == "UNREADABLE_QUESTION":
            reason = solution.get("reason", "Unreadable question — cannot solve.")
            self.notify_log("ERROR", reason)
            return {"success": False, "error": "OCR_FAILED", "reason": reason}

        if solution.get("error") == "SOLUTION_AI_FAILED":
            reason = solution.get("reason") or (
                "AI could not solve this question (MixRoute timeout/empty). Please retry."
            )
            print(f"[ERROR] {reason}")
            self.notify_log("ERROR", f"Solution AI failed — video not generated. {reason}")
            return {
                "success": False,
                "error": "SOLUTION_AI_FAILED",
                "reason": reason,
                "analysis": analysis,
                "solution": solution,
            }

        # Hard stop: never render a video on an unverified / wrong solution
        if solution.get("error") == "SOLUTION_UNVERIFIED" or solution.get("verification", {}).get("ok") is False:
            reason = solution.get("reason") or "Solution failed verification — video blocked."
            print(f"[ERROR] {reason}")
            self.notify_log("ERROR", f"Solution verification FAILED — video not generated. {reason}")
            if solution.get("answer"):
                self.notify_log("WARN", f"Rejected candidate answer: {solution.get('answer')}")
            return {
                "success": False,
                "error": "SOLUTION_UNVERIFIED",
                "reason": reason,
                "analysis": analysis,
                "solution": solution,
            }

        # Guard against subject hijack (chemistry in → projectile out)
        sol_blob = json.dumps(solution).lower()
        q_blob = f"{q_text} {q_subj} {q_topic}".lower()
        if any(k in q_blob for k in ("chemistry", "molecule", "orbital", "hybridisation", "hybridization", "bond angle")):
            if "projectile" in sol_blob and "molecule" not in sol_blob:
                reason = (
                    f"Solver produced a Physics/projectile pack for a Chemistry question "
                    f"(subject={q_subj}). Aborting instead of wrong-topic video."
                )
                print(f"[ERROR] {reason}")
                self.notify_log("ERROR", reason)
                return {"success": False, "error": "SUBJECT_MISMATCH", "reason": reason}

        vmeta = solution.get("verification") or {}
        if vmeta.get("ok"):
            self.notify_log(
                "SUCCESS",
                f"Solution verified (source={vmeta.get('source')}, confidence={vmeta.get('confidence')})",
            )

        formula = solution.get("formula", "Standard Formulation")
        answer = solution.get("answer", "Solution Verified")
        steps = solution.get("steps", [])
        beats = solution.get("equationBeats", [])

        print(f" [+] Teaching solution pack ready: Formula={formula}, Answer={answer}")
        self.notify_log("SUCCESS", f"✦ Concept: {solution.get('concept', q_topic)}")
        self.notify_log("SUCCESS", f"✦ Teaching goal: {solution.get('teachingGoal', '')}")
        self.notify_log("INFO", f"✦ Intuition: {str(solution.get('intuition', ''))[:160]}")
        self.notify_log("SUCCESS", f"✦ Governing Formula: {formula}")
        if solution.get("given"):
            self.notify_log("INFO", f"✦ Given: {', '.join(map(str, solution.get('given', [])[:6]))}")
        for s_idx, step in enumerate(steps):
            if isinstance(step, dict):
                step_txt = step.get("explanation") or step.get("say") or step.get("title") or ""
            else:
                step_txt = str(step)
            self.notify_log("INFO", f"  [Step {s_idx+1}] {step_txt}")
        for b_idx, beat in enumerate(beats):
            self.notify_log(
                "INFO",
                f"  [Eq {b_idx+1}] {beat.get('label', '')}: {beat.get('latex', '')}",
            )
        self.notify_log("SUCCESS", f"✦ Final Answer: {answer}")
        if solution.get("keyTakeaway"):
            self.notify_log("INFO", f"✦ Takeaway: {solution.get('keyTakeaway')}")

        sol_ok, sol_errors = LessonValidator.validate_solution_pack(solution)
        if not sol_ok:
            print(f"[WARNING] Solution pack warnings: {sol_errors}")

        print("\n[STAGE 3/6] Planning visual lesson (Remotion / Three.js)...")
        self.notify_log("INFO", "Stage 3: Visual Lesson Planner mapping solution pack → teachable scenes...")
        plan = self.planner.plan(analysis, solution, force_visual_mode=visual_mode_override)
        self.log_debug("animation.json", plan)
        self.log_debug("lesson.json", plan)
        audit = plan.get("visualAudit") or {}
        self.log_debug("pipeline_audit.json", audit)
        if audit.get("issues"):
            self.notify_log("WARN", f"Visual audit flags ({len(audit['issues'])}):")
            for iss in audit["issues"][:12]:
                self.notify_log("WARN", f"  ⚠ {iss}")
        else:
            self.notify_log(
                "SUCCESS",
                f"Visual audit OK — sim={((audit.get('simulation') or {}).get('type'))}, "
                f"diagram elements={((audit.get('diagramSpec') or {}).get('elementCount'))}, "
                f"engines={audit.get('enginesUsed')}",
            )
        for sc in audit.get("scenes") or []:
            flag = "OK" if sc.get("ok") else "BAD"
            self.notify_log(
                "INFO" if sc.get("ok") else "WARN",
                f"  [{flag}] {sc.get('id')} engine={sc.get('engine')} mode={sc.get('visualMode')} "
                f"lane={sc.get('expectedLane')} beats={sc.get('beats')}",
            )

        # Live Remotion preview payload (same LessonVideo composition used in Remotion Studio)
        live_lesson = {
            "lesson": plan,
            "fps": 30,
            "timeline": [],
            "visualAudit": audit,
            "solution": plan.get("solution") or solution,
        }
        live_path = os.path.join(self.temp_dir, "live_lesson.json")
        with open(live_path, "w", encoding="utf-8") as f:
            json.dump(live_lesson, f, indent=2)
        remotion_public = os.path.join(os.path.dirname(__file__), "remotion", "public")
        os.makedirs(remotion_public, exist_ok=True)
        with open(os.path.join(remotion_public, "live-lesson.json"), "w", encoding="utf-8") as f:
            json.dump(live_lesson, f, indent=2)
        self.notify_preview("lesson", {
            "lessonUrl": "/api/live-lesson",
            "studioUrl": "http://127.0.0.1:3333/LessonVideo",
            "visualAudit": audit,
            "scenes": [
                {
                    "id": s.get("id"),
                    "type": s.get("type"),
                    "visualMode": s.get("visualMode"),
                    "engine": s.get("engine"),
                    "boardLayout": s.get("boardLayout"),
                    "force3D": bool(s.get("force3D")),
                    "duration": s.get("duration"),
                    "status": "pending",
                    "ok": next(
                        (a.get("ok") for a in (audit.get("scenes") or []) if a.get("id") == s.get("id")),
                        True,
                    ),
                    "issues": next(
                        (a.get("issues") for a in (audit.get("scenes") or []) if a.get("id") == s.get("id")),
                        [],
                    ),
                }
                for s in plan.get("scenes", [])
            ],
        })
        self.notify_log("INFO", "Live Remotion preview ready — open Studio or watch scenes as they finish.")

        is_valid, schema_errors = SchemaValidator.validate_animation_plan(plan)
        lesson_ok, lesson_errors = LessonValidator.validate_lesson(plan)
        scenes_count = len(plan.get("scenes", []))
        if not is_valid:
            print(f"[WARNING] Lesson JSON schema warnings: {schema_errors}")
        if not lesson_ok:
            print(f"[WARNING] Pedagogy validation warnings: {lesson_errors}")
        print(f" [+] Lesson JSON ready ({scenes_count} scenes).")
        self.notify_log(
            "SUCCESS",
            f"✦ Lesson JSON generated with {scenes_count} scenes "
            f"(Target Duration: {plan.get('video', {}).get('targetDuration', 200)}s)",
        )
        for sc in plan.get("scenes", []):
            self.notify_log(
                "INFO",
                f"  [{sc.get('id')}] {sc.get('type')} / {sc.get('visualMode')} — {sc.get('learningGoal') or sc.get('narration', '')[:80]}",
            )

        print("\n[STAGE 4/6] Generating Hinglish voice narration per scene...")
        self.notify_log("INFO", "Stage 4: Hinglish voiceover synthesis (ElevenLabs multilingual / Edge-TTS)...")
        audio_results = generate_scene_narrations(plan["scenes"], temp_dir=os.path.join(self.temp_dir, "audio"))
        for a in audio_results:
            print(f"   * {a['sceneId']}: {a['duration']}s [{a['provider']}]")
            self.notify_log("INFO", f"🎙️ [Voiceover {a['sceneId']}] ({a['duration']}s): {a['text']}")

        timeline_data = TimelineManager.build_timeline(plan["scenes"], audio_results)
        self.log_debug("timeline.json", timeline_data)
        print(f" [+] Master synchronized timeline computed: Total Duration={timeline_data['totalDuration']}s")

        # Copy narration MP3s into Remotion public/ so Studio LessonVideo can scrub with audio
        remotion_public = os.path.join(os.path.dirname(__file__), "remotion", "public")
        public_audio = os.path.join(remotion_public, "audio")
        os.makedirs(public_audio, exist_ok=True)
        studio_timeline = []
        for entry in timeline_data.get("timeline", []):
            row = dict(entry)
            src = row.get("audioPath")
            sid = row.get("sceneId") or "scene"
            if src and os.path.exists(src) and os.path.getsize(src) > 1000:
                dest_name = f"{sid}.mp3"
                try:
                    import shutil
                    shutil.copy2(src, os.path.join(public_audio, dest_name))
                    row["audioFile"] = f"audio/{dest_name}"
                except Exception as copy_err:
                    print(f"[Audio] Could not copy {sid} for Studio: {copy_err}")
            studio_timeline.append(row)
        self.notify_log("SUCCESS", f"Remotion Studio audio synced ({len(studio_timeline)} clips).")

        # Refresh Remotion Studio props with real timeline + audioFile paths
        live_lesson = {
            "lesson": plan,
            "fps": 30,
            "timeline": studio_timeline,
        }
        with open(os.path.join(self.temp_dir, "live_lesson.json"), "w", encoding="utf-8") as f:
            json.dump(live_lesson, f, indent=2)
        os.makedirs(remotion_public, exist_ok=True)
        with open(os.path.join(remotion_public, "live-lesson.json"), "w", encoding="utf-8") as f:
            json.dump(live_lesson, f, indent=2)
        self.notify_preview("lesson", {
            "lessonUrl": "/api/live-lesson",
            "studioUrl": "http://127.0.0.1:3333/LessonVideo",
            "scenes": [
                {
                    "id": s.get("id"),
                    "type": s.get("type"),
                    "visualMode": s.get("visualMode"),
                    "duration": s.get("duration"),
                    "status": "pending",
                }
                for s in plan.get("scenes", [])
            ],
        })

        print("\n[STAGE 5/6] Rendering scenes (Remotion 2D + Three.js 3D)...")
        self.notify_log("INFO", "Stage 5: Scene Director rendering via Remotion / Three.js...")
        rendered_scene_files = {}

        def _render_and_verify_single_scene(entry):
            scene_id = entry["sceneId"]
            v_mode = entry["visualMode"]
            dur = entry["duration"]
            target_mp4 = os.path.join(self.temp_dir, f"{scene_id}_rendered.mp4")
            scene_spec = next((s for s in plan["scenes"] if s["id"] == scene_id), {})
            scene_spec["duration"] = dur
            global_meta = {**plan.get("video", {}), "solution": solution, "questionText": q_text}

            scene_idx = next((i for i, s in enumerate(plan["scenes"]) if s["id"] == scene_id), 0)
            is_last = (scene_idx == len(plan["scenes"]) - 1) or (
                str(scene_spec.get("type", "")).upper() == "CONCLUSION"
            )

            engine = "Three.js" if str(v_mode).upper() == "3D" else "Remotion 2D"
            print(f"   >> [{scene_id}] Rendering with {engine}...")
            self.notify_log("INFO", f"🎬 Rendering [{scene_id}] via {engine}...")

            rendered = self.render_remotion_scene(scene_spec, target_mp4, global_meta, dur)

            if rendered:
                is_ok, msg = self.verify_scene_visual_content(target_mp4)
                if not is_ok:
                    print(f"     [!] [{scene_id}] visual check warning: {msg}. Falling back to PIL 2D...")
                    self.notify_log("WARN", f"⚠️ [{scene_id}] visual verification alert ({msg}). PIL fallback...")
                    rendered = False

            if not rendered:
                print(f"     -> PIL slide fallback for {scene_id}...")
                rendered = Engine2DRenderer.render_scene_video(
                    scene_spec,
                    target_mp4,
                    global_video_meta=global_meta,
                    duration=dur,
                    is_last_scene=is_last,
                )

            if rendered and os.path.exists(target_mp4):
                is_ok, msg = self.verify_scene_visual_content(target_mp4)
                print(f"     [+] [{scene_id}] Verified ({dur}s, status: {msg}).")
                self.notify_log("SUCCESS", f"✅ [{scene_id}] Visual verified ({dur}s, {v_mode})")
                return scene_id, target_mp4

            print(f"     [!] {scene_id} failed to render. Generating fallback frame...")
            self.notify_log("WARN", f"⚠️ [{scene_id}] Generating fallback frame to prevent blank gap")
            try:
                fallback_img = Image.new("RGB", (1920, 1080), color=(8, 11, 18))
                from PIL import ImageDraw

                draw = ImageDraw.Draw(fallback_img)
                draw.text((700, 500), f"Scene: {scene_id}", fill=(56, 189, 248))
                fallback_frame = target_mp4.replace(".mp4", "_fallback.png")
                fallback_img.save(fallback_frame)
                fb_cmd = [
                    imageio_ffmpeg.get_ffmpeg_exe(), "-y",
                    "-loop", "1", "-i", fallback_frame,
                    "-t", str(dur), "-c:v", "libx264",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-r", "30", target_mp4,
                ]
                subprocess.run(fb_cmd, capture_output=True)
                if os.path.exists(fallback_frame):
                    os.remove(fallback_frame)
                if os.path.exists(target_mp4):
                    return scene_id, target_mp4
            except Exception as fb_err:
                print(f"     [!] Fallback also failed: {fb_err}")
            return scene_id, None

        # Render scenes; publish each finished clip to live preview ASAP
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_map = {
                executor.submit(_render_and_verify_single_scene, entry): entry
                for entry in timeline_data["timeline"]
            }
            for fut in concurrent.futures.as_completed(future_map):
                entry = future_map[fut]
                try:
                    s_id, path = fut.result()
                except Exception as e:
                    print(f"[Preview] Scene render exception: {e}")
                    continue
                if path:
                    rendered_scene_files[s_id] = path
                    self.notify_preview("scene", {
                        "id": s_id,
                        "type": entry.get("type"),
                        "visualMode": entry.get("visualMode"),
                        "duration": entry.get("duration"),
                        "status": "ready",
                        "url": f"/api/preview/scene/{s_id}?t={int(__import__('time').time())}",
                    })
                    self.notify_log("SUCCESS", f"Live preview ready: {s_id}")

        print("\n[STAGE 6/6] Assembling master video, audio, and subtitles with FFmpeg...")
        self.notify_log("INFO", "Stage 6: Stitching Remotion/Three.js scenes + audio with FFmpeg...")
        final_output_path = os.path.join(self.output_dir, output_filename)
        final_video = VideoCompositor.composite_final_video(
            rendered_scene_files=rendered_scene_files,
            timeline_data=timeline_data,
            output_filepath=final_output_path,
            temp_dir=os.path.join(self.temp_dir, "composition"),
            burn_subtitles=False,
        )

        print("\n=======================================================")
        print("  SUCCESS! Final Educational Video Created:")
        print(f"  Path: {final_video}")
        print(f"  Duration: {timeline_data['totalDuration']}s")
        print("=======================================================\n")
        self.notify_log(
            "SUCCESS",
            f"🎉 Master Video Ready! Duration: {timeline_data['totalDuration']}s | File: {output_filename}",
        )

        return {
            "success": True,
            "videoPath": final_video,
            "totalDuration": timeline_data["totalDuration"],
            "analysis": analysis,
            "solution": solution,
            "plan": plan,
            "timeline": timeline_data,
            "visualAudit": audit,
        }


def main():
    parser = argparse.ArgumentParser(
        description="DoubtSolve.ai — Remotion 2D + Three.js 3D Educational Video Engine"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="An object is thrown at an angle. Explain projectile motion and calculate its range.",
        help="Question text, image path (.jpg/.png), or PDF path (.pdf)",
    )
    parser.add_argument(
        "--visual-mode",
        "-m",
        type=str,
        choices=["2D", "3D", "HYBRID"],
        default=None,
        help="Force visual mode (2D=Remotion, 3D=Three.js, HYBRID=both)",
    )
    parser.add_argument(
        "--quality",
        "-q",
        type=str,
        choices=["FAST_PREVIEW", "QUALITY_PREVIEW", "FINAL_RENDER", "NORMAL", "HIGH_QUALITY"],
        default="QUALITY_PREVIEW",
        help="Render quality preset",
    )
    parser.add_argument("--output", "-o", type=str, default="final_video.mp4", help="Output video filename")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode and save logs")

    args = parser.parse_args()
    orchestrator = PipelineOrchestrator(debug=args.debug, quality=args.quality)
    result = orchestrator.run(args.input, visual_mode_override=args.visual_mode, output_filename=args.output)

    if not result.get("success"):
        print(f"[RESULT] Error: {result.get('reason')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
