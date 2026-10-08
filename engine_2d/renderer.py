"""2D Scene Video Renderer with Progressive Step-by-Step Revelation.
Renders high-fidelity educational slides dynamically synced to the narration flow.
Steps and elements appear only when actively explained, and the Final Answer Box is
strictly reserved for the conclusion phase.
"""

import os
import re
import subprocess
from typing import List, TypedDict
from PIL import Image

from video.ffmpeg import FFmpegUtils
from .templates import Scene2DTemplates


class RenderPhase(TypedDict):
    """A single rendered slide and the time it remains on screen."""
    img: Image.Image
    duration: float


class Engine2DRenderer:
    @classmethod
    def _split_narration_sentences(cls, narration):
        """Splits narration text into clean, non-empty sentences."""
        if not narration:
            return ["Explaining core scientific principles..."]
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', str(narration)) if s.strip()]
        return sentences if sentences else [str(narration).strip()]

    @classmethod
    def render_scene_video(cls, scene_spec, output_path, global_video_meta=None, duration=None, fps=24, is_last_scene=False):
        """Renders an educational scene video with progressive step-by-step disclosure."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        dur = float(duration or scene_spec.get("duration", 5.0))
        scene_type = str(scene_spec.get("type", "EXPLANATION")).upper()
        scene_id = str(scene_spec.get("id", "scene"))
        narration = scene_spec.get("narration", "").strip()

        meta = global_video_meta or {}
        subject = meta.get("subject", "Science")
        title = meta.get("title", scene_spec.get("id", "Explanation").replace("_", " ").title())
        topic = meta.get("topic", "Concept")
        solution = meta.get("solution", {})

        sentences = cls._split_narration_sentences(narration)

        # Determine pedagogical role of the scene
        is_intro = (scene_type == "INTRO" or "intro" in scene_id.lower())
        is_conclusion = (
            is_last_scene
            or scene_type == "CONCLUSION"
            or "conclusion" in scene_id.lower()
            or scene_spec.get("is_last_scene", False)
        )
        scene_actions = scene_spec.get("actions", [])
        option_labels = [
            str(action.get("label", "")).strip()
            for action in scene_actions
            if str(action.get("action", "")).upper() == "CREATE"
            and re.match(r"^[A-D][.)]", str(action.get("label", "")).strip(), re.IGNORECASE)
        ]
        narration_lower = narration.lower()
        is_option_check = (
            bool(option_labels)
            or any(phrase in narration_lower for phrase in (
                "compare the options", "compare our derived", "check the options",
                "evaluate each option", "verify our result", "option verification"
            ))
        )

        phases: List[RenderPhase] = []

        # -------------------------------------------------------------
        # CASE 1: INTRO SCENE (Progressive Title -> Question Statement)
        # -------------------------------------------------------------
        if is_intro:
            q_text = meta.get("questionText", "")
            spoken_lines = sentences or ["Let's read the problem and identify what we need to find."]
            weights = [max(1, len(line.split())) + 2 * line.count(",") + 3 * line.count(";") for line in spoken_lines]
            total_weight = sum(weights)
            elapsed = 0.0
            for index, (line, weight) in enumerate(zip(spoken_lines, weights)):
                phase_duration = round(dur * weight / total_weight, 2)
                if index == len(spoken_lines) - 1:
                    phase_duration = max(0.5, round(dur - elapsed, 2))
                img = Scene2DTemplates.create_title_slide(
                    title=title, subject=subject, topic=topic,
                    question_text=q_text, visible_question=bool(q_text),
                    spoken_text=line, active_narration=""
                )
                phases.append({"img": img, "duration": phase_duration})
                elapsed += phase_duration

        # -------------------------------------------------------------
        # CASE 2: CONCLUSION SCENE (Takeaways -> FINAL ANSWER REVEAL)
        # -------------------------------------------------------------
        elif is_conclusion:
            formula = solution.get("formula", "")
            answer = solution.get("answer", "")
            takeaways = solution.get("steps", [])

            # Phase 1: Conceptual Summary & Key Takeaways (NO Final Answer Box visible yet!)
            # Phase 2: Final Answer Revelation (with prominent glowing emerald celebration card)
            if dur >= 4.0 and answer:
                t1 = round(dur * 0.55, 2)
                t2 = round(dur - t1, 2)

                sent_phase1 = sentences[0] if sentences else "Summarizing governing concepts and key rules..."
                sent_phase2 = sentences[-1] if len(sentences) > 1 else sent_phase1

                img1 = Scene2DTemplates.create_conclusion_slide(
                    title="Conclusion & Problem Synthesis",
                    subject=subject,
                    topic=topic,
                    takeaways_list=takeaways,
                    formula_tex=formula,
                    answer_str=answer,
                    show_answer=False,  # ANSWER HIDDEN in initial phase!
                    active_narration=sent_phase1
                )
                img2 = Scene2DTemplates.create_conclusion_slide(
                    title="Definitive Solution & Final Answer",
                    subject=subject,
                    topic=topic,
                    takeaways_list=takeaways,
                    formula_tex=formula,
                    answer_str=answer,
                    show_answer=True,  # ANSWER REVEALED in closing phase!
                    active_narration=sent_phase2
                )
                phases = [{"img": img1, "duration": t1}, {"img": img2, "duration": t2}]
            else:
                img = Scene2DTemplates.create_conclusion_slide(
                    title="Definitive Solution & Final Answer",
                    subject=subject,
                    topic=topic,
                    takeaways_list=takeaways,
                    formula_tex=formula,
                    answer_str=answer,
                    show_answer=True,
                    active_narration=sentences[0] if sentences else ""
                )
                phases = [{"img": img, "duration": dur}]

        # -------------------------------------------------------------
        # CASE 3: DERIVATION / EXPLANATION SCENE (Progressive Step-by-Step)
        # -------------------------------------------------------------
        elif is_option_check:
            # An option-check scene follows the derivation. Show the answer choices
            # and the spoken reasoning instead of replaying every solution step.
            formula = solution.get("formula", "")
            weights = [max(1, len(line.split())) + 2 * line.count(",") + 3 * line.count(";") for line in sentences]
            total_weight = sum(weights) or 1
            elapsed = 0.0
            for index, (line, weight) in enumerate(zip(sentences, weights)):
                phase_duration = round(dur * weight / total_weight, 2)
                if index == len(sentences) - 1:
                    phase_duration = max(0.5, round(dur - elapsed, 2))
                option_match = re.search(r"\b(?:option|choice)\s*([A-D])\b", line, re.IGNORECASE)
                active_option = option_match.group(1) if option_match else ""
                img = Scene2DTemplates.create_comparison_slide(
                    title=title,
                    subject=subject,
                    formula_tex=formula,
                    options=option_labels,
                    active_narration=line,
                    active_option=active_option,
                )
                phases.append({"img": img, "duration": phase_duration})
                elapsed += phase_duration

        else:
            given = solution.get("given", [])
            formula = solution.get("formula", "")
            steps = solution.get("steps", [])

            # Check if scene actions specify an equation override
            for act in scene_actions:
                if act.get("action") == "SHOW_EQUATION" and act.get("equation"):
                    formula = act.get("equation")

            num_steps = max(1, min(len(steps), 4))
            # Calculate phase durations
            # Phase 0: Given & Formula introductory setup (~20% of dur)
            # Subsequent phases: Step 1, Step 2, Step 3... revealed one by one!
            if dur >= 6.0 and num_steps > 0:
                t_setup = max(2.0, round(dur * 0.20, 2))
                t_remaining = max(1.0, dur - t_setup)
                t_per_step = round(t_remaining / num_steps, 2)

                # Phase 0: Setup card with formula
                img0 = Scene2DTemplates.create_derivation_slide(
                    title=title, given_list=given, formula_tex=formula,
                    steps_list=steps, visible_steps=0, active_step_idx=-1,
                    subject=subject, active_narration=sentences[0] if sentences else ""
                )
                phases.append({"img": img0, "duration": t_setup})

                # Progressive Step Phases
                for s_i in range(num_steps):
                    # Match narration sentence to step if available
                    sent_idx = min(s_i + 1, len(sentences) - 1)
                    s_dur = t_per_step if s_i < num_steps - 1 else round(dur - sum(p["duration"] for p in phases), 2)
                    img_step = Scene2DTemplates.create_derivation_slide(
                        title=title, given_list=given, formula_tex=formula,
                        steps_list=steps, visible_steps=s_i + 1, active_step_idx=s_i,
                        subject=subject, active_narration=sentences[sent_idx]
                    )
                    phases.append({"img": img_step, "duration": max(0.5, s_dur)})
            else:
                img = Scene2DTemplates.create_derivation_slide(
                    title=title, given_list=given, formula_tex=formula,
                    steps_list=steps, visible_steps=num_steps, active_step_idx=num_steps - 1,
                    subject=subject, active_narration=sentences[0] if sentences else ""
                )
                phases = [{"img": img, "duration": dur}]

        # -------------------------------------------------------------
        # COMPILE PHASES INTO SEAMLESS MP4
        # -------------------------------------------------------------
        ffmpeg_exe = FFmpegUtils.get_ffmpeg_path()
        temp_files = []

        try:
            if len(phases) == 1:
                # Single phase: Direct render
                temp_img = output_path.replace(".mp4", "_f0.png")
                temp_files.append(temp_img)
                phase_image = phases[0]["img"]
                if not isinstance(phase_image, Image.Image):
                    raise TypeError(f"Expected a PIL image for {scene_id}, got {type(phase_image).__name__}")
                phase_image.save(temp_img)

                cmd = [
                    ffmpeg_exe, "-y",
                    "-loop", "1",
                    "-i", temp_img,
                    "-t", str(phases[0]["duration"]),
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-tune", "stillimage",
                    "-pix_fmt", "yuv420p",
                    "-r", str(fps),
                    output_path
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                return True

            # Multi-phase progressive video: render each phase clip and concatenate
            clip_paths = []
            for p_idx, phase in enumerate(phases):
                p_img_path = output_path.replace(".mp4", f"_p{p_idx}.png")
                p_clip_path = output_path.replace(".mp4", f"_p{p_idx}.mp4")
                temp_files.extend([p_img_path, p_clip_path])

                phase_image = phase["img"]
                if not isinstance(phase_image, Image.Image):
                    raise TypeError(f"Expected a PIL image for {scene_id} phase {p_idx}, got {type(phase_image).__name__}")
                phase_image.save(p_img_path)
                p_dur = max(0.5, phase["duration"])

                cmd = [
                    ffmpeg_exe, "-y",
                    "-loop", "1",
                    "-i", p_img_path,
                    "-t", str(p_dur),
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-tune", "stillimage",
                    "-pix_fmt", "yuv420p",
                    "-r", str(fps),
                    p_clip_path
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                if os.path.exists(p_clip_path):
                    clip_paths.append(p_clip_path)

            if not clip_paths:
                raise RuntimeError("No phase clips were generated successfully.")

            # Concat all phase clips into master scene output
            concat_success = FFmpegUtils.concat_videos(clip_paths, output_path)
            return concat_success and os.path.exists(output_path) and os.path.getsize(output_path) > 0

        except Exception as e:
            print(f"[Engine2D ERROR] Failed to render scene {scene_id}: {e}")
            return False
        finally:
            for tf in temp_files:
                try:
                    if os.path.exists(tf):
                        os.remove(tf)
                except Exception:
                    pass
