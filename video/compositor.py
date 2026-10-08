"""Master Video Compositor — mux narration + concatenate scenes to final MP4."""

import os
import shutil
import subprocess
from .ffmpeg import FFmpegUtils
from .subtitles import SubtitleGenerator


class VideoCompositor:
    @staticmethod
    def composite_final_video(
        rendered_scene_files,
        timeline_data,
        output_filepath="output/final_video.mp4",
        temp_dir="temp/composition",
        burn_subtitles=False,
    ):
        # Always use a fresh composition folder so stale 2kb/s mux files cannot leak in
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

        timeline = timeline_data.get("timeline", [])
        synced_clips = []

        print(f"[Compositor] Synchronizing and assembling {len(rendered_scene_files)} scenes...")

        for entry in timeline:
            scene_id = entry["sceneId"]
            target_dur = float(entry["duration"])
            audio_path = entry.get("audioPath")
            raw_video = rendered_scene_files.get(scene_id)
            if not raw_video or not os.path.exists(raw_video):
                print(f"[Compositor WARNING] Missing video for {scene_id}, skipping")
                continue

            dur_matched_video = os.path.join(temp_dir, f"{scene_id}_dur_matched.mp4")
            if not FFmpegUtils.match_video_duration(raw_video, target_dur, dur_matched_video):
                continue

            muxed_clip = os.path.join(temp_dir, f"{scene_id}_muxed.mp4")
            if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
                ok = FFmpegUtils.merge_audio_and_video(
                    dur_matched_video, audio_path, muxed_clip, duration=target_dur
                )
                if not ok:
                    raise RuntimeError(
                        f"[Compositor ERROR] Could not mux audible narration for {scene_id}. "
                        f"Audio file: {audio_path}"
                    )
            else:
                raise RuntimeError(
                    f"[Compositor ERROR] Missing narration MP3 for {scene_id}. Refusing silent video."
                )

            synced_clips.append(muxed_clip)

        if not synced_clips:
            raise RuntimeError("[Compositor ERROR] No valid scene clips to concatenate!")

        concat_output = os.path.join(temp_dir, "master_concatenated.mp4")
        if not FFmpegUtils.concat_videos(synced_clips, concat_output):
            raise RuntimeError("[Compositor ERROR] Concatenation failed!")

        br = FFmpegUtils.probe_audio_bitrate_kbps(concat_output)
        if br < 32:
            raise RuntimeError(f"[Compositor ERROR] Concat audio too weak ({br} kb/s). Aborting.")

        srt_path = os.path.join(temp_dir, "subtitles.srt")
        SubtitleGenerator.generate_srt(timeline, srt_path)
        final_mp4 = os.path.abspath(output_filepath)

        # Keep audio bitstream — do NOT re-encode to silent AAC
        cmd = [
            FFmpegUtils.get_ffmpeg_path(), "-y",
            "-i", concat_output,
            "-i", srt_path,
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-map", "1:0",
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=eng",
            "-movflags", "+faststart",
            final_mp4,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
        if res.returncode != 0 or not os.path.exists(final_mp4):
            shutil.copyfile(concat_output, final_mp4)
            print(f"[Compositor WARNING] Subtitle attach failed; shipped concat with audio. {(res.stderr or '')[-300:]}")

        final_br = FFmpegUtils.probe_audio_bitrate_kbps(final_mp4)
        print(
            f"[Compositor SUCCESS] {final_mp4} | size={os.path.getsize(final_mp4)} | audio~{final_br:.0f} kb/s"
        )
        if final_br < 32:
            raise RuntimeError("[Compositor ERROR] Final video has no audible audio track.")
        return final_mp4
