"""FastAPI Backend Server for DoubtSolve.ai Educational Video Studio.
Gemini → Lesson JSON → Remotion (2D) / Three.js (3D) → ElevenLabs → FFmpeg.
"""

import os
import sys
import json
import shutil
import asyncio
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from main import PipelineOrchestrator

app = FastAPI(title="AI Doubt - Educational Video Studio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = os.path.abspath(os.getenv("OUTPUT_DIR", "output"))
TEMP_DIR = os.path.abspath(os.getenv("TEMP_DIR", "temp"))
DEBUG_DIR = os.path.abspath("debug")
UPLOAD_DIR = os.path.abspath(os.path.join(TEMP_DIR, "uploads"))
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Pipeline State with Live Execution Logs + Remotion-style preview
current_job = {
    "status": "IDLE", # IDLE, RUNNING, COMPLETED, ERROR
    "stage": "Idle",
    "progress": 0,
    "error": None,
    "result": None,
    "preview": {
        "studioUrl": "http://127.0.0.1:3333/LessonVideo",
        "lessonReady": False,
        "scenes": [],
        "activeSceneUrl": None,
    },
    "logs": [
        {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": "INFO",
            "message": "AI Educational Video Engine initialized. Ready for question input."
        }
    ]
}

_remotion_studio_proc = None


def ensure_remotion_studio():
    """Start Remotion Studio (scrub/play LessonVideo) if not already listening on :3333."""
    global _remotion_studio_proc
    import socket
    import subprocess
    import webbrowser

    def port_open(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            return s.connect_ex(("127.0.0.1", port)) == 0

    remotion_dir = os.path.join(os.path.dirname(__file__), "remotion")
    if not os.path.isdir(remotion_dir):
        add_log("WARN", "Remotion folder missing — cannot open live Studio preview.")
        return False

    if not port_open(3333):
        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            _remotion_studio_proc = subprocess.Popen(
                ["npm", "run", "studio"],
                cwd=remotion_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=(sys.platform == "win32"),
                creationflags=creationflags,
            )
            add_log("INFO", "Starting Remotion Studio on http://127.0.0.1:3333/LessonVideo ...")
            for _ in range(40):
                if port_open(3333):
                    break
                import time
                time.sleep(0.25)
        except Exception as e:
            add_log("WARN", f"Could not auto-start Remotion Studio: {e}")
            return False

    if port_open(3333):
        try:
            webbrowser.open("http://127.0.0.1:3333/LessonVideo")
        except Exception:
            pass
        add_log("SUCCESS", "Remotion live preview opened — scrub/play LessonVideo like Studio.")
        return True
    add_log("WARN", "Remotion Studio did not become ready on :3333")
    return False


def on_preview(event_type: str, payload: dict):
    """Receive live lesson / scene clip updates from PipelineOrchestrator."""
    global current_job
    preview = current_job.setdefault(
        "preview",
        {"studioUrl": "http://127.0.0.1:3333/LessonVideo", "lessonReady": False, "scenes": [], "activeSceneUrl": None},
    )
    if event_type == "lesson":
        preview["lessonReady"] = True
        preview["studioUrl"] = payload.get("studioUrl") or preview["studioUrl"]
        preview["scenes"] = payload.get("scenes") or []
        preview["activeSceneUrl"] = None
        preview["visualAudit"] = payload.get("visualAudit")
        current_job["visualAudit"] = payload.get("visualAudit")
        current_job["stage"] = "Live Remotion Preview Ready"
        current_job["progress"] = max(current_job.get("progress", 0), 52)
        # Open the same scrub/play Studio UI the user already knows
        try:
            ensure_remotion_studio()
        except Exception as e:
            add_log("WARN", f"Studio open failed: {e}")
    elif event_type == "scene":
        sid = payload.get("id")
        scenes = preview.get("scenes") or []
        found = False
        for i, sc in enumerate(scenes):
            if sc.get("id") == sid:
                scenes[i] = {**sc, **payload}
                found = True
                break
        if not found:
            scenes.append(payload)
        preview["scenes"] = scenes
        if payload.get("url"):
            preview["activeSceneUrl"] = payload["url"]
        current_job["progress"] = min(90, max(current_job.get("progress", 0), 70))


def add_log(level: str, message: str):
    global current_job
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    entry = {"timestamp": timestamp, "level": level.upper(), "message": message}
    if "logs" not in current_job or current_job["logs"] is None:
        current_job["logs"] = []
    current_job["logs"].append(entry)
    if len(current_job["logs"]) > 500:
        current_job["logs"] = current_job["logs"][-500:]
        
    # Dynamically advance stage and progress bar only while job is running
    if current_job.get("status") == "RUNNING":
        msg_l = message.lower()
        if "final mp4" in msg_l or "completed successfully" in msg_l:
            current_job["stage"] = "Completed"
            current_job["progress"] = 100
        elif "stage 6" in msg_l or "assembling" in msg_l or "compositing" in msg_l:
            current_job["stage"] = "Stage 6: Master Audio-Video Assembly"
            current_job["progress"] = 92
        elif "stage 5" in msg_l and "stage 5 & 6" not in msg_l or "remotion" in msg_l or "three.js" in msg_l or "rendering [" in msg_l:
            current_job["stage"] = "Stage 5: Remotion / Three.js Scene Rendering"
            current_job["progress"] = 80
        elif "stage 4" in msg_l or "voiceover" in msg_l:
            current_job["stage"] = "Stage 4: Voiceover Narration Synthesis"
            current_job["progress"] = 65
        elif "stage 3" in msg_l:
            current_job["stage"] = "Stage 3: Visual Lesson Planning"
            current_job["progress"] = 50
        elif "stage 2" in msg_l:
            current_job["stage"] = "Stage 2: Scientific Derivation & Equations"
            current_job["progress"] = 35
        elif "stage 1" in msg_l:
            current_job["stage"] = "Stage 1: Question Understanding & OCR"
            current_job["progress"] = 15


def run_pipeline_task(input_data, visual_mode, quality):
    global current_job
    try:
        current_job["status"] = "RUNNING"
        current_job["stage"] = "Question Understanding"
        current_job["progress"] = 10
        add_log("INFO", f"Task started. Mode: {visual_mode}, Quality: {quality}")
        add_log("INFO", f"Analyzing input source: {os.path.basename(str(input_data))}")

        orchestrator = PipelineOrchestrator(
            debug=True,
            quality=quality,
            log_callback=add_log,
            preview_callback=on_preview,
        )
        
        current_job["stage"] = "Scientific Derivation & Solution Synthesis"
        current_job["progress"] = 30
        add_log("INFO", "Stage 1: Question Multimodal Analysis & Intent Check complete.")
        add_log("INFO", "Stage 2: Computing derivation steps, governing equations, and target variables...")

        current_job["stage"] = "Visual Strategy & 3D/2D Master Plan"
        current_job["progress"] = 55
        add_log("INFO", f"Stage 3: Visual Strategy Engine decided on {visual_mode} mode.")
        add_log("INFO", "Stage 4: Synthesizing scene timelines and voice narration...")

        res = orchestrator.run(
            input_data=input_data,
            visual_mode_override=visual_mode,
            output_filename="final_video.mp4"
        )

        if res.get("success"):
            current_job["status"] = "COMPLETED"
            current_job["stage"] = "Completed"
            current_job["progress"] = 100
            current_job["result"] = {
                "videoUrl": "/api/video",
                "duration": res.get("totalDuration"),
                "analysis": res.get("analysis"),
                "solution": res.get("solution"),
                "plan": res.get("plan"),
                "timeline": res.get("timeline"),
                "visualAudit": res.get("visualAudit") or current_job.get("visualAudit"),
            }
            current_job["visualAudit"] = current_job["result"]["visualAudit"]
            add_log("SUCCESS", "Stage 5 & 6: Remotion/Three.js rendering & FFmpeg composition completed successfully.")
            add_log("SUCCESS", f"Final MP4 video generated ({res.get('totalDuration', 0):.1f}s). Video URL: /api/video")
        else:
            reason = res.get("reason", "Generation failed.")
            current_job["status"] = "ERROR"
            current_job["stage"] = "Failed"
            current_job["error"] = reason
            add_log("ERROR", f"Pipeline execution failed: {reason}")
    except Exception as e:
        err_msg = str(e)
        current_job["status"] = "ERROR"
        current_job["stage"] = "Failed"
        current_job["error"] = err_msg
        add_log("ERROR", f"Unhandled Exception in pipeline runner: {err_msg}")


@app.get("/api/status")
def get_status():
    return current_job


@app.get("/api/logs")
def get_logs():
    return {"logs": current_job.get("logs", [])}


@app.post("/api/generate")
async def generate_video(
    background_tasks: BackgroundTasks,
    text: Optional[str] = Form(None),
    visualMode: Optional[str] = Form("HYBRID"),
    quality: Optional[str] = Form("QUALITY_PREVIEW"),
    file: Optional[UploadFile] = File(None)
):
    global current_job
    if current_job["status"] == "RUNNING":
        add_log("WARN", "Attempted to launch job while another task is already RUNNING.")
        raise HTTPException(status_code=400, detail="A video generation task is already in progress.")

    target_input = text
    if file and file.filename:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        target_input = file_path
        add_log("INFO", f"Uploaded/Pasted file received: {file.filename}")

    if not target_input:
        add_log("ERROR", "No text or file input provided in /api/generate request.")
        raise HTTPException(status_code=400, detail="Please provide a question text or upload an image/PDF file.")

    current_job = {
        "status": "RUNNING",
        "stage": "Starting Pipeline",
        "progress": 5,
        "error": None,
        "result": None,
        "visualAudit": None,
        "preview": {
            "studioUrl": "http://127.0.0.1:3333/LessonVideo",
            "lessonReady": False,
            "scenes": [],
            "activeSceneUrl": None,
            "visualAudit": None,
        },
        "logs": [
            {
                "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "level": "INFO",
                "message": f"New generation requested. VisualMode={visualMode}, Quality={quality}"
            }
        ]
    }

    # Clear stale scene clips / live-lesson so old projectile never shows for new Q
    try:
        if os.path.isdir(TEMP_DIR):
            for name in os.listdir(TEMP_DIR):
                if name.endswith("_rendered.mp4") or name == "live_lesson.json":
                    try:
                        os.remove(os.path.join(TEMP_DIR, name))
                    except OSError:
                        pass
        live_pub = os.path.join(os.path.dirname(__file__), "remotion", "public", "live-lesson.json")
        if os.path.exists(live_pub):
            os.remove(live_pub)
        add_log("INFO", "Cleared previous live-lesson + scene renders (anti-stale).")
    except Exception as clear_err:
        add_log("WARN", f"Could not fully clear temp previews: {clear_err}")

    background_tasks.add_task(run_pipeline_task, target_input, visualMode, quality)
    return {"message": "Job started", "status": current_job}


@app.get("/api/live-lesson")
def get_live_lesson():
    """Latest LessonVideo props written after Stage 3 (for Remotion Studio / UI)."""
    candidates = [
        os.path.join(TEMP_DIR, "live_lesson.json"),
        os.path.join(os.path.dirname(__file__), "remotion", "public", "live-lesson.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(status_code=404, detail="Live lesson not ready yet. Upload + Generate first.")


@app.get("/api/visual-audit")
def get_visual_audit():
    """Scene/engine/sim audit for debugging wrong-topic animations."""
    if current_job.get("visualAudit"):
        return current_job["visualAudit"]
    preview = current_job.get("preview") or {}
    if preview.get("visualAudit"):
        return preview["visualAudit"]
    result = current_job.get("result") or {}
    if result.get("visualAudit"):
        return result["visualAudit"]
    # Fallback: read from live lesson / debug dump
    for path in (
        os.path.join(TEMP_DIR, "live_lesson.json"),
        os.path.join(DEBUG_DIR, "pipeline_audit.json"),
    ):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "visualAudit" in data:
                return data["visualAudit"]
            if "scenes" in data and "simulation" in data:
                return data
    raise HTTPException(status_code=404, detail="Visual audit not ready yet.")


@app.get("/api/preview/scene/{scene_id}")
def get_scene_preview(scene_id: str):
    """Serve a finished scene clip for in-app scrub/play while the full video assembles."""
    safe = "".join(c for c in scene_id if c.isalnum() or c in ("_", "-"))
    video_path = os.path.join(TEMP_DIR, f"{safe}_rendered.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Scene preview '{safe}' not ready.")
    return FileResponse(video_path, media_type="video/mp4", filename=f"{safe}.mp4")


@app.post("/api/preview/open-studio")
def open_remotion_studio():
    ok = ensure_remotion_studio()
    return {
        "ok": ok,
        "studioUrl": "http://127.0.0.1:3333/LessonVideo",
        "message": "Remotion Studio opened" if ok else "Could not start Remotion Studio",
    }


@app.get("/api/video")
def get_video():
    video_path = os.path.join(OUTPUT_DIR, "final_video.mp4")
    if not os.path.exists(video_path):
        add_log("ERROR", "Video file requested at /api/video but final_video.mp4 does not exist.")
        raise HTTPException(status_code=404, detail="Video not generated yet.")
    return FileResponse(video_path, media_type="video/mp4", filename="educational_explanation.mp4")


@app.get("/api/debug/{file_name}")
def get_debug_file(file_name: str):
    file_path = os.path.join(DEBUG_DIR, file_name)
    if not os.path.exists(file_path):
        add_log("WARN", f"Debug file requested but missing: {file_name}")
        raise HTTPException(status_code=404, detail=f"Debug file '{file_name}' not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Serve Static UI: Prefer Next.js production build in frontend/out, fallback to web/
FRONTEND_OUT = os.path.join(os.path.dirname(__file__), "frontend", "out")
WEB_DIR = FRONTEND_OUT if os.path.exists(FRONTEND_OUT) else os.path.join(os.path.dirname(__file__), "web")
if os.path.exists(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="static")


def free_port(port=8000):
    """Automatically frees the port if an orphaned server process is occupying it."""
    try:
        import subprocess
        res = subprocess.run(f"netstat -ano | findstr :{port}", shell=True, capture_output=True, text=True)
        for line in res.stdout.strip().splitlines():
            if "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid and pid.isdigit() and int(pid) != os.getpid():
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading

    free_port(8000)

    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:8000")).start()

    print("\n" + "="*60)
    print("  DoubtSolve.ai USER STUDIO (Upload UI)")
    print("  Open: http://127.0.0.1:8000")
    print("  Upload text / image / PDF here first.")
    print("  Remotion developer preview is separate: npm run engine:studio")
    print("  (that opens http://127.0.0.1:3333 — not the upload screen)")
    print("="*60 + "\n")

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)