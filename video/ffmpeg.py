"""FFmpeg Utilities for Video Processing, Merging, and Export."""

import os
import subprocess
import shutil
import glob
import sys


def find_ffmpeg_exe():
    sys_path = shutil.which("ffmpeg")
    if sys_path:
        return sys_path
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    user_home = os.path.expanduser("~")
    patterns = [
        os.path.join(sys.prefix, "Lib", "site-packages", "imageio_ffmpeg", "binaries", "ffmpeg*.exe"),
        os.path.join(user_home, "AppData", "Local", "Programs", "Python", "Python*", "Lib", "site-packages", "imageio_ffmpeg", "binaries", "ffmpeg*.exe"),
    ]
    for p in patterns:
        matches = glob.glob(p)
        if matches:
            return matches[0]
    return "ffmpeg"


class FFmpegUtils:
    @staticmethod
    def get_ffmpeg_path():
        return find_ffmpeg_exe()

    @staticmethod
    def probe_audio_bitrate_kbps(path):
        """Return approximate audio bitrate in kb/s, or 0 if missing."""
        try:
            cmd = [FFmpegUtils.get_ffmpeg_path(), "-i", path, "-hide_banner"]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
            for line in (res.stderr or "").splitlines():
                if "Audio:" in line and "kb/s" in line:
                    # e.g. ... fltp, 192 kb/s
                    part = line.split("kb/s")[0].strip().split()[-1]
                    return float(part)
        except Exception:
            pass
        return 0.0

    @staticmethod
    def concat_videos(video_list, output_path):
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        list_file = output_path + ".txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for v in video_list:
                safe_path = os.path.abspath(v).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        cmd = [
            FFmpegUtils.get_ffmpeg_path(), "-y",
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x070B14",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            if os.path.exists(list_file):
                os.remove(list_file)
            return True
        except Exception as e:
            print(f"[FFmpeg ERROR concat] {e}")
            if os.path.exists(list_file):
                os.remove(list_file)
            return False

    @staticmethod
    def merge_audio_and_video(video_path, audio_path, output_path, duration=None):
        """Reliable narration mux — verifies audible AAC bitrate after encode."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        ff = FFmpegUtils.get_ffmpeg_path()
        dur = float(duration) if duration else None

        attempts = []
        # Attempt A: simple map (most reliable on Windows imageio ffmpeg)
        cmd_a = [
            ff, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest",
            output_path,
        ]
        if dur:
            cmd_a.extend(["-t", str(dur)])
        attempts.append(cmd_a)

        # Attempt B: apad to exact duration
        if dur:
            attempts.append([
                ff, "-y",
                "-i", video_path,
                "-i", audio_path,
                "-filter_complex",
                f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur={dur}[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(dur),
                output_path,
            ])

        for idx, cmd in enumerate(attempts):
            res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
            if res.returncode != 0 or not os.path.exists(output_path):
                print(f"[FFmpeg mux attempt {idx+1} failed] {(res.stderr or '')[-500:]}")
                continue
            br = FFmpegUtils.probe_audio_bitrate_kbps(output_path)
            if br >= 32:
                print(f"[FFmpeg] Mux OK audio~{br:.0f} kb/s -> {os.path.basename(output_path)}")
                return True
            print(f"[FFmpeg WARNING] Mux attempt {idx+1} produced weak audio ({br} kb/s), retrying...")

        return False

    @staticmethod
    def match_video_duration(input_video, target_duration, output_video):
        os.makedirs(os.path.dirname(os.path.abspath(output_video)), exist_ok=True)
        cmd = [
            FFmpegUtils.get_ffmpeg_path(), "-y",
            "-i", input_video,
            "-vf", f"tpad=stop_mode=clone:stop_duration={max(float(target_duration), 0.1)}",
            "-t", str(target_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-an",
            output_video,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except Exception as e:
            print(f"[FFmpeg ERROR match_dur] {e}")
            return False
