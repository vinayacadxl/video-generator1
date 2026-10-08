"""ElevenLabs Voice Generation & Intelligent Fallback TTS.
Female Hinglish voice, slightly fast + smooth. Parallel scene generation.
"""

import os
import asyncio
import requests
import subprocess
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

from video.ffmpeg import FFmpegUtils

# Female multilingual default (Rachel). Override with ELEVENLABS_VOICE_ID.
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
# Female Hindi neural fallback
DEFAULT_EDGE_VOICE = "hi-IN-SwaraNeural"


def get_audio_duration(file_path):
    """Calculates exact audio duration in seconds using ffmpeg."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return 5.0
    try:
        ffmpeg_exe = FFmpegUtils.get_ffmpeg_path()
        cmd = [ffmpeg_exe, "-i", file_path, "-f", "null", "-"]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
        for line in res.stderr.split("\n"):
            if "Duration:" in line:
                part = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = part.split(":")
                dur = float(h) * 3600 + float(m) * 60 + float(s)
                return max(dur, 2.0)
    except Exception:
        pass
    return 5.0


def _apply_tempo(input_path, speed: float):
    """Speed up / slow down without pitch shift when possible (atempo)."""
    speed = max(0.7, min(1.35, float(speed or 1.0)))
    if abs(speed - 1.0) < 0.02:
        return
    ffmpeg_exe = FFmpegUtils.get_ffmpeg_path()
    tmp = input_path + ".tempo.mp3"
    # atempo valid range 0.5–2.0
    cmd = [
        ffmpeg_exe, "-y", "-i", input_path,
        "-filter:a", f"atempo={speed}",
        "-vn", tmp,
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
        os.replace(tmp, input_path)
    elif os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass


def generate_voice_elevenlabs(text, voice_id, output_path, api_key):
    """Direct HTTP call to ElevenLabs TTS API (female, smoother defaults)."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }
    model_id = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    # Slightly lower stability = smoother expressive Hinglish; moderate style
    stability = float(os.getenv("ELEVENLABS_STABILITY", "0.32"))
    similarity = float(os.getenv("ELEVENLABS_SIMILARITY", "0.78"))
    style = float(os.getenv("ELEVENLABS_STYLE", "0.42"))
    speed = float(os.getenv("ELEVENLABS_SPEED", "1.12"))

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity,
            "style": style,
            "use_speaker_boost": True,
        },
    }
    # Some ElevenLabs models accept top-level speed
    if speed and abs(speed - 1.0) >= 0.02:
        payload["voice_settings"]["speed"] = max(0.7, min(1.2, speed))

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    if response.status_code == 200:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        # Ensure "thodi fast" even if API ignored speed
        _apply_tempo(output_path, speed)
        return True, "ElevenLabs"
    raise RuntimeError(f"ElevenLabs API Error {response.status_code}: {response.text[:500]}")


async def _generate_voice_edge_tts(text, output_path, voice=None):
    """Female Indian Edge-TTS fallback for Hinglish."""
    import edge_tts

    voice = voice or os.getenv("EDGE_TTS_VOICE", DEFAULT_EDGE_VOICE)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    rate = os.getenv("EDGE_TTS_RATE", "+12%")
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)
    return True


def generate_voice(text, voice_id=None, output_path="temp/narration.mp3"):
    """
    Female Hinglish narration (slightly fast + smooth).
    1. ElevenLabs multilingual female voice
    2. Edge-TTS hi-IN-SwaraNeural fallback
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    api_key = os.getenv("ELEVENLABS_API_KEY")
    # Default: female teacher voice (Rachel). Set NARRATION_VOICE=male to keep custom IDs.
    if (os.getenv("NARRATION_VOICE", "female") or "female").lower() == "female":
        vid = (
            voice_id
            or os.getenv("ELEVENLABS_FEMALE_VOICE_ID")
            or DEFAULT_VOICE_ID
        )
    else:
        vid = voice_id or os.getenv("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID
    if not os.getenv("ELEVENLABS_MODEL"):
        os.environ["ELEVENLABS_MODEL"] = "eleven_multilingual_v2"

    provider = "Fallback Neural TTS"
    success = False

    if api_key and api_key.strip():
        try:
            success, provider = generate_voice_elevenlabs(text, vid, output_path, api_key)
        except Exception as e:
            print(f"[TTS WARNING] ElevenLabs failed: {e}. Falling back to Edge-TTS female.")

    if not success:
        try:
            edge_voice = os.getenv("EDGE_TTS_VOICE", DEFAULT_EDGE_VOICE)
            asyncio.run(_generate_voice_edge_tts(text, output_path, voice=edge_voice))
            speed = float(os.getenv("ELEVENLABS_SPEED", "1.12"))
            _apply_tempo(output_path, speed)
            provider = f"Edge-TTS ({edge_voice})"
            success = True
        except Exception as e:
            print(f"[TTS ERROR] Edge-TTS also failed: {e}. Silent timing fallback.")
            ffmpeg_exe = FFmpegUtils.get_ffmpeg_path()
            subprocess.run(
                [
                    ffmpeg_exe, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "5", "-q:a", "9", "-acodec", "libmp3lame", output_path,
                ],
                capture_output=True,
            )
            provider = "Silent Fallback"

    dur = get_audio_duration(output_path)
    return {
        "path": output_path,
        "duration": dur,
        "provider": provider,
        "text": text,
    }


def generate_scene_narrations(scenes, temp_dir="temp/audio"):
    """Generate individual audio files for each scene in parallel."""
    from tts.pronounce import speakable

    os.makedirs(temp_dir, exist_ok=True)

    def _gen_single_scene(item):
        idx, scene = item
        scene_id = scene.get("id", f"scene_{idx+1:02d}")
        text = scene.get("narration", "").strip()
        if not text:
            text = f"Ab next step {idx+1}."
        # Keep original for subtitles; speak a pronunciation-safe version
        speak_text = speakable(text)

        out_file = os.path.join(temp_dir, f"{scene_id}.mp3")
        voice_res = generate_voice(speak_text, output_path=out_file)
        return {
            "index": idx,
            "sceneId": scene_id,
            "audioPath": out_file,
            "duration": voice_res["duration"],
            "provider": voice_res["provider"],
            "text": text,
            "spokenText": speak_text,
        }

    items = list(enumerate(scenes))
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max(len(scenes), 1), 4)) as executor:
        results = list(executor.map(_gen_single_scene, items))

    results.sort(key=lambda x: x["index"])
    return results
