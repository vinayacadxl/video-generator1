# DoubtSolve.ai — Remotion 2D + Three.js 3D Educational Video Engine

Converts any student question (text / image / PDF) into a synchronized educational MP4.

```text
USER (Image / PDF / Text)
        ↓
Gemini Vision + AI
        ↓
Question + Correct Solution
        ↓
Visual Lesson JSON
        ↓
Scene Director
   ├── Remotion 2D  (text, equations, graphs, diagrams, arrows)
   └── Three.js 3D  (train, rocket, earth, particles, molecules, physics)
        ↓
Remotion Timeline
        ↓
ElevenLabs (voice + timing)
        ↓
FFmpeg
        ↓
FINAL MP4
```

Blender is **not** used.

## Setup

```bash
# Python
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY / ELEVENLABS_API_KEY

# Remotion engine (Node 18+)
npm run engine:install

# Studio UI (optional)
npm run ui:dev
```

## Run (user app first)

```bash
# USER STUDIO — upload text / image / PDF (THIS is the main screen)
npm run dev
# → http://127.0.0.1:8000

# Optional: Next.js live UI (also upload screen)
npm run ui:dev
# → http://127.0.0.1:3000

# CLI sample (projectile motion)
npm run generate:sample

# Remotion developer composition preview ONLY (not the upload UI)
npm run engine:studio
# → http://127.0.0.1:3333
```

Flow for students/teachers:
1. Open upload studio (`npm run dev`)
2. Paste/upload question → Generate
3. Preview MP4 in the right panel
4. Download when satisfied


## Quality presets

| Preset | Resolution |
|--------|------------|
| `FAST_PREVIEW` | 960×540 |
| `QUALITY_PREVIEW` | 1280×720 |
| `FINAL_RENDER` | 1920×1080 |

## Layout

```text
ai/                 Gemini analyze / solve / lesson plan / validate
remotion/           Remotion + Three.js engine + Scene Director
render/             Python bridge to Remotion + FFmpeg helpers
tts/                ElevenLabs (+ Edge-TTS fallback)
video/              Timeline, compositor, subtitles, ffmpeg utils
frontend/           Next.js studio UI
config/             Shared settings / quality presets
assets/             Reusable 2D/3D educational assets
engine_2d/          Emergency PIL fallback only
```
