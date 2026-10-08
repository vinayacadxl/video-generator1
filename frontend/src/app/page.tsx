"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles, Video, FileText, Upload, Cpu, Layers, Volume2, CheckCircle2, Clock, Download, Play, RotateCcw, AlertCircle, Copy, ChevronRight, Atom, Binary, Compass, FileCode, Sliders, Check, Clipboard, Image as ImageIcon, X, Trash2, Terminal, Filter, RefreshCw, Bug
} from "lucide-react";
import confetti from "canvas-confetti";

interface LogEntry {
  timestamp: string;
  level: "INFO" | "SUCCESS" | "WARN" | "ERROR";
  message: string;
}

interface PreviewScene {
  id: string;
  type?: string;
  visualMode?: string;
  engine?: string;
  boardLayout?: string;
  force3D?: boolean;
  duration?: number;
  status?: string;
  url?: string;
  ok?: boolean;
  issues?: string[];
}

interface VisualAudit {
  ok?: boolean;
  questionPreview?: string;
  concept?: string;
  topic?: string;
  subject?: string;
  simulation?: {
    type?: string;
    allowedForQuestion?: boolean;
    sanitizedFrom?: string;
    describe?: string;
  };
  diagramSpec?: {
    present?: boolean;
    elementCount?: number;
    phaseCount?: number;
    title?: string;
  };
  enginesUsed?: string[];
  sceneCount?: number;
  scenes?: Array<{
    id?: string;
    type?: string;
    engine?: string;
    visualMode?: string;
    force3D?: boolean;
    expectedLane?: string;
    beats?: number;
    ok?: boolean;
    issues?: string[];
    onScreenTitle?: string;
    narrationPreview?: string;
  }>;
  issues?: string[];
  demotedFake3D?: string[];
  formatChecklist?: Array<{
    index?: number;
    id?: string;
    type?: string;
    engine?: string;
    duration?: number;
    beats?: number;
    ok?: boolean;
    issues?: string[];
  }>;
  formatBlueprint?: Array<{
    order?: number;
    sceneType?: string;
    purpose?: string;
    screenShows?: string[];
  }>;
}

interface LivePreview {
  studioUrl?: string;
  lessonReady?: boolean;
  scenes?: PreviewScene[];
  activeSceneUrl?: string | null;
  visualAudit?: VisualAudit | null;
}

interface PipelineJob {
  status: "IDLE" | "RUNNING" | "COMPLETED" | "ERROR";
  stage: string;
  progress: number;
  error?: string | null;
  result?: any;
  preview?: LivePreview;
  visualAudit?: VisualAudit | null;
  logs?: LogEntry[];
}

export default function EducationalVideoStudio() {
  const [inputType, setInputType] = useState<"text" | "file">("text");
  const [questionText, setQuestionText] = useState("A ball is thrown vertically upward with velocity 20 m/s. Find maximum height.");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);
  const [visualMode, setVisualMode] = useState<"HYBRID" | "2D" | "3D">("HYBRID");
  const [quality, setQuality] = useState<"FAST_PREVIEW" | "QUALITY_PREVIEW" | "FINAL_RENDER">("QUALITY_PREVIEW");
  const [isDragging, setIsDragging] = useState(false);
  const [pasteNotification, setPasteNotification] = useState<string | null>(null);

  const [logs, setLogs] = useState<LogEntry[]>([
    { timestamp: new Date().toLocaleTimeString(), level: "INFO", message: "AI Educational Video Engine Console initialized. Ready for user input." }
  ]);
  const [logFilter, setLogFilter] = useState<"ALL" | "INFO" | "WARN" | "ERROR">("ALL");
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);
  const consoleBottomRef = useRef<HTMLDivElement>(null);

  const [pipelineState, setPipelineState] = useState<PipelineJob>({
    status: "IDLE", stage: "", progress: 0, error: null, result: null, preview: undefined, logs: []
  });

  const [activeTab, setActiveTab] = useState<"solution" | "format" | "audit" | "plan" | "timeline" | "raw">("format");
  const [liveAudit, setLiveAudit] = useState<VisualAudit | null>(null);
  const [activeSceneId, setActiveSceneId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedLogs, setCopiedLogs] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const previewScenes = pipelineState.preview?.scenes || [];
  const readyScenes = previewScenes.filter((s) => s.status === "ready" && s.url);
  const visualAudit: VisualAudit | null =
    liveAudit ||
    pipelineState.visualAudit ||
    pipelineState.preview?.visualAudit ||
    pipelineState.result?.visualAudit ||
    null;
  const selectedSceneUrl =
    (activeSceneId && readyScenes.find((s) => s.id === activeSceneId)?.url) ||
    pipelineState.preview?.activeSceneUrl ||
    readyScenes[readyScenes.length - 1]?.url ||
    null;

  const appendLog = (level: "INFO" | "SUCCESS" | "WARN" | "ERROR", message: string) => {
    const timestamp = new Date().toLocaleTimeString() + "." + String(Date.now() % 1000).padStart(3, "0");
    setLogs((prev) => [...prev, { timestamp, level, message }]);
  };

  useEffect(() => {
    if (autoScrollLogs && consoleBottomRef.current) {
      consoleBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScrollLogs]);

  useEffect(() => {
    if (!selectedFile) {
      setFilePreviewUrl(null);
      return;
    }
    if (selectedFile.type.startsWith("image/")) {
      const url = URL.createObjectURL(selectedFile);
      setFilePreviewUrl(url);
      appendLog("INFO", `Loaded image file for preview: ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)`);
      return () => URL.revokeObjectURL(url);
    } else {
      setFilePreviewUrl(null);
      appendLog("INFO", `Loaded document file: ${selectedFile.name}`);
    }
  }, [selectedFile]);

  useEffect(() => {
    const handleGlobalPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.indexOf("image") !== -1) {
          const blob = item.getAsFile();
          if (blob) {
            const pastedFile = new File([blob], `pasted_screenshot_${Date.now()}.png`, { type: blob.type || "image/png" });
            setSelectedFile(pastedFile);
            setInputType("file");
            showPasteToast("Screenshot pasted from Clipboard!");
            appendLog("SUCCESS", `Image pasted from clipboard: ${pastedFile.name}`);
            e.preventDefault();
            return;
          }
        }
      }
    };
    window.addEventListener("paste", handleGlobalPaste);
    return () => window.removeEventListener("paste", handleGlobalPaste);
  }, []);

  const showPasteToast = (msg: string) => {
    setPasteNotification(msg);
    setTimeout(() => setPasteNotification(null), 3500);
  };

  const handlePasteFromClipboardButton = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.read) {
        const clipboardItems = await navigator.clipboard.read();
        for (const item of clipboardItems) {
          for (const type of item.types) {
            if (type.startsWith("image/")) {
              const blob = await item.getType(type);
              const file = new File([blob], `pasted_image_${Date.now()}.png`, { type });
              setSelectedFile(file);
              setInputType("file");
              showPasteToast("Screenshot pasted successfully!");
              appendLog("SUCCESS", `Image pasted via Clipboard API button: ${file.name}`);
              return;
            }
          }
        }
      }
      showPasteToast("Press Ctrl+V anywhere on screen to paste copied image");
      appendLog("WARN", "Clipboard API: No image found in clipboard. Press Ctrl+V.");
    } catch (err) {
      showPasteToast("Press Ctrl+V on your keyboard to paste copied screenshot");
      appendLog("WARN", "Clipboard access denied. Please press Ctrl+V directly.");
    }
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file); setInputType("file");
      showPasteToast(`File loaded: ${file.name}`);
      appendLog("INFO", `File dropped onto upload zone: ${file.name}`);
    }
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (pipelineState.status === "RUNNING") {
      interval = setInterval(async () => {
        try {
          const res = await fetch("/api/status");
          if (res.ok) {
            const data: PipelineJob = await res.json();
            setPipelineState(data);
            if (data.logs && data.logs.length > 0) {
              setLogs((prevLogs) => {
                const existingMsgs = new Set(prevLogs.map((l) => l.timestamp + l.message));
                const newEntries = data.logs!.filter((l) => !existingMsgs.has(l.timestamp + l.message));
                return newEntries.length > 0 ? [...prevLogs, ...newEntries] : prevLogs;
              });
            }
            if (data.preview?.activeSceneUrl) {
              setActiveSceneId((prev) => prev || data.preview!.scenes?.find((s) => s.url === data.preview!.activeSceneUrl)?.id || prev);
            }
            if (data.visualAudit || data.preview?.visualAudit) {
              setLiveAudit(data.visualAudit || data.preview?.visualAudit || null);
            } else if (data.preview?.lessonReady) {
              try {
                const ar = await fetch("/api/visual-audit");
                if (ar.ok) setLiveAudit(await ar.json());
              } catch (_) {}
            }
            if (data.status === "COMPLETED") {
              confetti({ particleCount: 80, spread: 70, origin: { y: 0.6 } });
              appendLog("SUCCESS", "Video synthesis pipeline finished cleanly. MP4 ready.");
            } else if (data.status === "ERROR") {
              appendLog("ERROR", `Server execution error: ${data.error || "Unknown Error"}`);
            }
          }
        } catch (err) { console.error("Polling error:", err); }
      }, 1200);
    }
    return () => clearInterval(interval);
  }, [pipelineState.status]);

  useEffect(() => {
    async function loadLastVideo() {
      try {
        const res = await fetch("/api/status");
        if (res.ok) {
          const data = await res.json();
          if (data.status === "COMPLETED") {
            setPipelineState(data);
            if (data.logs && data.logs.length > 0) setLogs(data.logs);
          }
        }
      } catch (e) {}
    }
    loadLastVideo();
  }, []);

  const handleGenerate = async () => {
    try {
      const formData = new FormData();
      if (inputType === "file" && selectedFile) {
        formData.append("file", selectedFile);
        appendLog("INFO", `Sending file request: ${selectedFile.name}`);
      } else {
        formData.append("text", questionText);
        appendLog("INFO", `Sending text prompt: "${questionText.slice(0, 50)}..."`);
      }
      formData.append("visualMode", visualMode);
      formData.append("quality", quality);

      setPipelineState({
        status: "RUNNING",
        stage: "Starting Pipeline",
        progress: 5,
        error: null,
        result: null,
        preview: { studioUrl: "http://127.0.0.1:3333/LessonVideo", lessonReady: false, scenes: [], activeSceneUrl: null },
      });
      setActiveSceneId(null);
      setLiveAudit(null);
      setActiveTab("format");
      appendLog("INFO", `API POST /api/generate requested (VisualMode=${visualMode}, Quality=${quality})`);
      appendLog("INFO", "After lesson plan: Remotion Studio (scrub/play) will open automatically.");

      const res = await fetch("/api/generate", { method: "POST", body: formData });
      if (!res.ok) {
        const errData = await res.json();
        const errMsg = errData.detail || "Failed to start generation";
        appendLog("ERROR", `HTTP ${res.status} Response: ${errMsg}`);
        throw new Error(errMsg);
      } else {
        appendLog("SUCCESS", "Generation request accepted by backend. Processing task launched...");
      }
    } catch (err: any) {
      setPipelineState({ status: "ERROR", stage: "Failed", progress: 0, error: err.message, result: null });
      appendLog("ERROR", `Client Exception: ${err.message}`);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const copyConsoleLogs = () => {
    const formatted = logs.map((l) => `[${l.timestamp}] [${l.level}] ${l.message}`).join("\n");
    navigator.clipboard.writeText(formatted);
    setCopiedLogs(true);
    setTimeout(() => setCopiedLogs(false), 2000);
  };

  const clearLogs = () => {
    setLogs([{ timestamp: new Date().toLocaleTimeString(), level: "INFO", message: "Console cleared by user." }]);
  };

  const filteredLogs = logs.filter((log) => {
    if (logFilter === "ALL") return true;
    if (logFilter === "INFO") return log.level === "INFO" || log.level === "SUCCESS";
    return log.level === logFilter;
  });

  const samplePrompts = [
    { label: "Vertical Motion", text: "A ball is thrown vertically upward with velocity 20 m/s. Find maximum height." },
    { label: "Right Triangle", text: "Find the area and hypotenuse of a right-angled triangle with base 6 m and height 8 m." },
    { label: "Water Molecule", text: "Explain the molecular geometry, bond angle, and polarity of a water molecule (H2O)." }
  ];

  return (
    <div className="min-h-screen text-slate-100 flex flex-col p-4 md:p-8 max-w-[1720px] mx-auto relative">
      <AnimatePresence>
        {pasteNotification && (
          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="fixed top-6 right-6 z-50 bg-gradient-to-r from-indigo-600 to-sky-500 text-white font-semibold text-xs md:text-sm px-5 py-3 rounded-2xl shadow-2xl border border-white/20 flex items-center gap-3 backdrop-blur-xl">
            <Clipboard className="w-5 h-5 text-cyan-300 animate-bounce" />
            <span>{pasteNotification}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <header className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-800/80 gap-4 mb-8">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-sky-500 flex items-center justify-center font-black text-white shadow-lg shadow-indigo-500/25">
            <Sparkles className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl md:text-3xl font-extrabold bg-gradient-to-r from-indigo-400 via-sky-300 to-purple-400 bg-clip-text text-transparent">
                DoubtSolve<span className="text-indigo-400 font-bold">.ai</span>
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                LABS 2.0
              </span>
            </div>
            <p className="text-xs md:text-sm text-slate-400">
              Less doubt. More brilliant. • Gemini • Remotion 2D • Three.js 3D • Live Console
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            Remotion + Three.js Active
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 text-xs font-semibold">
            <Cpu className="w-3.5 h-3.5" />
            FFmpeg 8.1 Active
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-400 text-xs font-semibold">
            <Volume2 className="w-3.5 h-3.5" />
            ElevenLabs Studio
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-5 flex flex-col gap-6">
          <div className="glass-panel rounded-3xl p-6 flex flex-col gap-5 border border-sky-500/15 bg-slate-900/60 backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-400" />
                Question & Parameters
              </h2>
              <span className="text-xs px-2.5 py-1 rounded-full bg-indigo-950/80 text-indigo-300 border border-indigo-700/50 font-mono">Local Studio</span>
            </div>

            <div className="grid grid-cols-2 p-1 rounded-xl bg-slate-950/80 border border-slate-800 text-xs font-semibold">
              <button type="button" onClick={() => setInputType("text")} className={`py-2.5 rounded-lg transition-all flex items-center justify-center gap-2 ${inputType === "text" ? "bg-indigo-600 text-white shadow-md border border-indigo-400/40" : "text-slate-400 hover:text-slate-200"}`}>
                <FileText className="w-4 h-4" /> Text Question
              </button>
              <button type="button" onClick={() => setInputType("file")} className={`py-2.5 rounded-lg transition-all flex items-center justify-center gap-2 ${inputType === "file" ? "bg-indigo-600 text-white shadow-md border border-indigo-400/40" : "text-slate-400 hover:text-slate-200"}`}>
                <Upload className="w-4 h-4" /> Upload / Paste Photo / PDF
              </button>
            </div>

            {inputType === "text" ? (
              <div className="flex flex-col gap-3">
                <textarea rows={4} value={questionText} onChange={(e) => setQuestionText(e.target.value)} placeholder="Enter an academic question (Mathematics, Physics, Chemistry, Biology, CS)..." className="w-full bg-slate-950/90 border border-slate-800 rounded-2xl p-4 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 resize-none transition-all placeholder:text-slate-500" />
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="text-[11px] text-slate-400 font-medium">Quick Examples:</span>
                  {samplePrompts.map((p, idx) => (
                    <button key={idx} type="button" onClick={() => setQuestionText(p.text)} className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 hover:text-indigo-300 transition-all">
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <div onClick={() => fileInputRef.current?.click()} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3 relative overflow-hidden ${isDragging ? "border-indigo-400 bg-indigo-500/15 scale-[1.01]" : selectedFile ? "border-emerald-500/50 bg-emerald-500/5" : "border-indigo-500/30 hover:border-indigo-400 bg-slate-950/60"}`}>
                  {filePreviewUrl ? (
                    <div className="relative w-full flex flex-col items-center gap-3">
                      <div className="relative group max-h-48 overflow-hidden rounded-xl border border-emerald-500/40 shadow-lg">
                        <img src={filePreviewUrl} alt="Preview" className="max-h-48 object-contain rounded-xl" />
                        <button type="button" onClick={(e) => { e.stopPropagation(); setSelectedFile(null); }} className="absolute top-2 right-2 p-1.5 rounded-full bg-rose-600 text-white hover:bg-rose-500 shadow-md">
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-emerald-400 font-semibold bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/30">
                        <CheckCircle2 className="w-4 h-4" /> Ready: {selectedFile?.name}
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                        <Upload className="w-6 h-6" />
                      </div>
                      <div className="space-y-1">
                        <div className="text-sm font-semibold text-slate-200">{selectedFile ? selectedFile.name : "Click to select, Drag & Drop, or Press Ctrl+V"}</div>
                        <p className="text-xs text-indigo-300/80 font-medium">Supports PNG, JPG, JPEG, PDF & Direct Clipboard Screenshot Paste</p>
                      </div>
                    </>
                  )}
                  <input ref={fileInputRef} type="file" className="hidden" accept="image/*,application/pdf" onChange={(e) => { if (e.target.files && e.target.files[0]) setSelectedFile(e.target.files[0]); }} />
                </div>
                <button type="button" onClick={handlePasteFromClipboardButton} className="w-full py-2.5 px-4 rounded-xl bg-slate-950 border border-indigo-500/30 hover:border-indigo-400 text-indigo-300 hover:text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all active:scale-98">
                  <Clipboard className="w-4 h-4 text-cyan-400" /> Paste Copied Screenshot / Image (Ctrl + V)
                </button>
              </div>
            )}

            <div className="flex flex-col gap-2.5">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-400" /> Visual Strategy Mode
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {[
                  { id: "HYBRID", title: "Hybrid", desc: "Remotion + Three.js" },
                  { id: "3D", title: "3D Only", desc: "Three.js Spatial" },
                  { id: "2D", title: "2D Only", desc: "Remotion Motion" },
                ].map((mode) => (
                  <button key={mode.id} type="button" onClick={() => setVisualMode(mode.id as any)} className={`p-3 rounded-2xl border text-left transition-all flex flex-col justify-between ${visualMode === mode.id ? "bg-indigo-600/20 border-indigo-500 text-white shadow-lg" : "bg-slate-950/60 border-slate-800 text-slate-400"}`}>
                    <span className="text-xs font-bold">{mode.title}</span>
                    <span className="text-[10px] opacity-75 mt-1">{mode.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-2.5">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-sky-400" /> Render Quality
              </label>
              <select value={quality} onChange={(e) => setQuality(e.target.value as any)} className="w-full bg-slate-950/90 border border-slate-800 rounded-2xl p-3 text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
                <option value="FAST_PREVIEW">FAST_PREVIEW (960×540 quick check)</option>
                <option value="QUALITY_PREVIEW">QUALITY_PREVIEW (1280×720 full animation)</option>
                <option value="FINAL_RENDER">FINAL_RENDER (1920×1080 production)</option>
              </select>
            </div>

            <button type="button" disabled={pipelineState.status === "RUNNING"} onClick={handleGenerate} className={`w-full py-4 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-lg ${pipelineState.status === "RUNNING" ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700" : "bg-gradient-to-r from-indigo-600 via-indigo-700 to-purple-600 text-white shadow-indigo-500/30 active:scale-98"}`}>
              <Sparkles className="w-5 h-5 animate-spin" />
              <span>{pipelineState.status === "RUNNING" ? "Generating Video Pipeline..." : "Generate Educational Video"}</span>
            </button>
          </div>

          <div className="glass-panel rounded-3xl p-6 flex flex-col gap-4 border border-slate-800/80 bg-slate-900/40">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Clock className="w-4 h-4 text-sky-400" /> Pipeline Execution Status
              </span>
              <span className="text-xs font-mono font-bold text-indigo-400">{pipelineState.progress}%</span>
            </div>
            <div className="w-full bg-slate-950 h-3 rounded-full overflow-hidden border border-slate-800 p-0.5">
              <div className="bg-gradient-to-r from-indigo-500 via-sky-400 to-purple-500 h-full rounded-full transition-all duration-500 shadow-md" style={{ width: `${pipelineState.progress}%` }} />
            </div>
            <div className="text-xs text-slate-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
              <span>Current Stage: {pipelineState.stage || "Idle"}</span>
            </div>
            {pipelineState.error && (
              <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                <div>
                  <div className="font-bold text-rose-300">Execution Error Encountered</div>
                  <p className="text-[11px] opacity-90 mt-0.5">{pipelineState.error}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-7 flex flex-col gap-6">
          <div className="glass-panel rounded-3xl p-6 flex flex-col gap-4 border border-indigo-500/20 bg-slate-900/80 backdrop-blur-xl shadow-2xl">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Video className="w-5 h-5 text-indigo-400" /> Live Scene Preview
              </h3>
              <div className="flex items-center gap-2 flex-wrap">
                {(pipelineState.preview?.lessonReady || pipelineState.status === "RUNNING" || pipelineState.status === "COMPLETED") && (
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await fetch("/api/preview/open-studio", { method: "POST" });
                        window.open(pipelineState.preview?.studioUrl || "http://127.0.0.1:3333/LessonVideo", "_blank");
                        appendLog("SUCCESS", "Opened Remotion Studio — scrub / play LessonVideo.");
                      } catch {
                        window.open("http://127.0.0.1:3333/LessonVideo", "_blank");
                      }
                    }}
                    className="px-3 py-1.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md"
                  >
                    <Play className="w-3.5 h-3.5" /> Remotion Studio (scrub/play)
                  </button>
                )}
                {pipelineState.result?.videoUrl && (
                  <>
                    <span className="text-[11px] text-emerald-400 font-semibold px-2 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                      Final MP4 ready
                    </span>
                    <a href={pipelineState.result.videoUrl} download className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md">
                      <Download className="w-3.5 h-3.5" /> Download MP4
                    </a>
                  </>
                )}
              </div>
            </div>

            {readyScenes.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {previewScenes.map((sc) => {
                  const ready = sc.status === "ready" && !!sc.url;
                  const active = ready && (sc.url === selectedSceneUrl || sc.id === activeSceneId);
                  return (
                    <button
                      key={sc.id}
                      type="button"
                      disabled={!ready}
                      onClick={() => ready && setActiveSceneId(sc.id)}
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-all ${
                        active
                          ? "bg-indigo-600 text-white border-indigo-400"
                          : sc.ok === false
                            ? "bg-rose-950/50 text-rose-300 border-rose-500/40"
                            : ready
                            ? "bg-slate-900 text-emerald-300 border-emerald-500/40 hover:border-emerald-400"
                            : "bg-slate-950 text-slate-500 border-slate-800 cursor-wait"
                      }`}
                      title={[sc.engine, sc.visualMode, ...(sc.issues || [])].filter(Boolean).join(" · ")}
                    >
                      {sc.id}{sc.engine ? ` · ${sc.engine}` : ""} {ready ? "●" : "…"}
                      {sc.ok === false ? " !" : ""}
                    </button>
                  );
                })}
              </div>
            )}

            <div className="relative aspect-video rounded-2xl bg-slate-950 overflow-hidden border border-slate-800 flex items-center justify-center">
              {pipelineState.result?.videoUrl ? (
                <video
                  ref={videoRef}
                  key={pipelineState.result.videoUrl}
                  src={`${pipelineState.result.videoUrl}?t=${Date.now()}`}
                  controls
                  autoPlay
                  playsInline
                  className="w-full h-full object-contain bg-black"
                />
              ) : selectedSceneUrl ? (
                <video
                  key={selectedSceneUrl}
                  src={selectedSceneUrl}
                  controls
                  autoPlay
                  playsInline
                  className="w-full h-full object-contain bg-black"
                />
              ) : pipelineState.preview?.lessonReady ? (
                <div className="flex flex-col items-center justify-center p-8 text-center gap-3">
                  <div className="w-16 h-16 rounded-full bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
                    <Play className="w-8 h-8" />
                  </div>
                  <div className="text-sm font-semibold text-slate-200">Lesson plan ready — Remotion Studio open ho chuka hoga</div>
                  <p className="text-xs text-slate-500 max-w-md">
                    Wahan timeline scrub / play karo (jaise pehle LessonVideo me). Scene clips yahan bhi aate rahenge jaise render finish hote hain.
                  </p>
                  <button
                    type="button"
                    onClick={() => window.open(pipelineState.preview?.studioUrl || "http://127.0.0.1:3333/LessonVideo", "_blank")}
                    className="mt-1 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold"
                  >
                    Open LessonVideo Studio
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center p-8 text-center gap-3">
                  <div className="w-16 h-16 rounded-full bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                    <Upload className="w-8 h-8 opacity-70" />
                  </div>
                  <div className="text-sm font-semibold text-slate-300">Step 1: Upload question → Generate</div>
                  <p className="text-xs text-slate-500 max-w-sm">
                    Image/PDF upload ke baad Remotion Studio (scrub/play) auto-open hoga — wahi LessonVideo preview.
                  </p>
                </div>
              )}
            </div>
          </div>

          {(pipelineState.result || visualAudit || pipelineState.preview?.lessonReady) && (
            <div className="glass-panel rounded-3xl p-6 flex flex-col gap-5 border border-slate-800 bg-slate-900/60">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex flex-wrap items-center gap-2">
                  {[
                    { id: "format", label: "Video Format" },
                    { id: "audit", label: "Visual Audit" },
                    { id: "solution", label: "Solution" },
                    { id: "plan", label: "Scenes / Engines" },
                    { id: "timeline", label: "Timeline" },
                    { id: "raw", label: "Raw JSON" },
                  ].map((tab) => (
                    <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id as any)} className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${activeTab === tab.id ? "bg-indigo-600 text-white shadow-md" : "text-slate-400 hover:text-slate-200"}`}>
                      {tab.label}
                    </button>
                  ))}
                </div>
                <button type="button" onClick={() => copyToClipboard(JSON.stringify(visualAudit || pipelineState.result, null, 2))} className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 text-xs flex items-center gap-1 border border-slate-700">
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? "Copied" : "Copy"}</span>
                </button>
              </div>

              <div className="max-h-[420px] overflow-y-auto p-2">
                {activeTab === "format" && (
                  <div className="flex flex-col gap-3 text-xs text-slate-300">
                    <p className="text-slate-400 leading-relaxed">
                      Har video isi order me chalega. Neeche checklist batati hai ki is run me kaunse scene format follow kar rahe hain.
                    </p>
                    {(pipelineState.result?.plan?.video?.formatBlueprint ||
                      (visualAudit as any)?.formatBlueprint ||
                      [
                        { order: 1, sceneType: "HOOK", purpose: "Question + given + find (answer nahi)" },
                        { order: 2, sceneType: "INTUITION", purpose: "Concept / figure" },
                        { order: 3, sceneType: "DIAGRAM", purpose: "Figure step-by-step" },
                        { order: 4, sceneType: "EXPLANATION", purpose: "Flow/scheme synced beats" },
                        { order: 5, sceneType: "CALCULATION", purpose: "Equations stepwise" },
                        { order: 6, sceneType: "RECAP", purpose: "Answer" },
                      ]).map((slot: any) => (
                      <div key={slot.order} className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                        <div className="font-semibold text-sky-400">
                          {slot.order}. {slot.sceneType}
                        </div>
                        <div className="text-slate-300 mt-1">{slot.purpose}</div>
                        {slot.screenShows ? (
                          <ul className="mt-2 text-slate-500 list-disc pl-4 space-y-0.5">
                            {(slot.screenShows as string[]).slice(0, 4).map((l, i) => (
                              <li key={i}>{l}</li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    ))}
                    {(visualAudit?.formatChecklist || pipelineState.result?.plan?.visualAudit?.formatChecklist) && (
                      <>
                        <div className="font-bold text-slate-200 pt-2">Is run ki scenes</div>
                        {(visualAudit?.formatChecklist || pipelineState.result?.plan?.visualAudit?.formatChecklist || []).map(
                          (row: any) => (
                            <div
                              key={row.id || row.index}
                              className={`p-2 rounded-lg border ${row.ok ? "border-slate-800 bg-slate-950/80" : "border-amber-500/40 bg-amber-950/20"}`}
                            >
                              <span className="text-indigo-300">{row.id}</span> · {row.type} · {row.engine} · {row.beats} beats
                              {(row.issues || []).map((iss: string, i: number) => (
                                <div key={i} className="text-amber-300">→ {iss}</div>
                              ))}
                            </div>
                          )
                        )}
                      </>
                    )}
                  </div>
                )}
                {activeTab === "audit" && (
                  <div className="flex flex-col gap-3 text-xs text-slate-300">
                    {!visualAudit ? (
                      <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-slate-500">
                        Stage 3 ke baad yahan dikhega: sim type, diagram elements, har scene ka engine, aur mismatch warnings.
                      </div>
                    ) : (
                      <>
                        <div className={`p-4 rounded-2xl border ${visualAudit.ok ? "bg-emerald-950/30 border-emerald-500/40" : "bg-rose-950/30 border-rose-500/40"}`}>
                          <div className="font-bold uppercase text-[10px] tracking-wider mb-1">
                            {visualAudit.ok ? "AUDIT PASS" : "AUDIT FLAGS"}
                          </div>
                          <div className="text-sm font-semibold text-slate-100">
                            {visualAudit.concept || visualAudit.topic || "Lesson"} · sim=
                            <span className="text-sky-300">{visualAudit.simulation?.type || "?"}</span>
                            {visualAudit.simulation?.sanitizedFrom ? (
                              <span className="text-amber-300"> (was {visualAudit.simulation.sanitizedFrom})</span>
                            ) : null}
                          </div>
                          <p className="text-slate-400 mt-1 leading-relaxed">{visualAudit.questionPreview || "—"}</p>
                          <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                            <span className="px-2 py-0.5 rounded-lg bg-slate-900 border border-slate-700">
                              diagram: {visualAudit.diagramSpec?.elementCount ?? 0} els / {visualAudit.diagramSpec?.phaseCount ?? 0} phases
                            </span>
                            <span className="px-2 py-0.5 rounded-lg bg-slate-900 border border-slate-700">
                              engines: {(visualAudit.enginesUsed || []).join(", ") || "—"}
                            </span>
                            {(visualAudit.demotedFake3D || []).length > 0 && (
                              <span className="px-2 py-0.5 rounded-lg bg-amber-950 border border-amber-600/40 text-amber-300">
                                demoted fake 3D: {visualAudit.demotedFake3D!.join(", ")}
                              </span>
                            )}
                          </div>
                        </div>
                        {(visualAudit.issues || []).length > 0 && (
                          <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/30 space-y-1">
                            {visualAudit.issues!.map((iss, i) => (
                              <div key={i} className="text-rose-200">⚠ {iss}</div>
                            ))}
                          </div>
                        )}
                        <div className="font-bold text-slate-200 text-xs">Per-scene engines (actual plan input)</div>
                        {(visualAudit.scenes || []).map((sc) => (
                          <div
                            key={sc.id}
                            className={`p-3 rounded-xl border ${sc.ok ? "bg-slate-950/80 border-slate-800" : "bg-rose-950/20 border-rose-500/30"}`}
                          >
                            <div className="flex flex-wrap items-center gap-2 font-semibold">
                              <span className="text-sky-400">{sc.id}</span>
                              <span className="text-slate-500">{sc.type}</span>
                              <span className="px-1.5 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/50">
                                {sc.engine}
                              </span>
                              <span className="text-slate-400">{sc.visualMode}</span>
                              <span className="text-slate-500">lane={sc.expectedLane}</span>
                              <span className="text-slate-500">beats={sc.beats}</span>
                              {sc.force3D ? <span className="text-amber-400">force3D</span> : null}
                              <span className={sc.ok ? "text-emerald-400" : "text-rose-400"}>{sc.ok ? "OK" : "BAD"}</span>
                            </div>
                            {sc.onScreenTitle ? <div className="text-slate-400 mt-1">title: {sc.onScreenTitle}</div> : null}
                            {(sc.issues || []).map((iss, i) => (
                              <div key={i} className="text-rose-300 mt-0.5">→ {iss}</div>
                            ))}
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                )}
                {activeTab === "solution" && (
                  <div className="flex flex-col gap-4 text-xs text-slate-300">
                    <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800">
                      <div className="font-bold text-indigo-400 uppercase text-[10px] tracking-wider mb-1">Core Concept & Problem Type</div>
                      <div className="text-sm font-semibold text-slate-100">{pipelineState.result?.analysis?.concept || visualAudit?.concept || "Scientific Concept"}</div>
                    </div>
                    {pipelineState.result?.solution?.steps && (
                      <div className="flex flex-col gap-3">
                        <div className="font-bold text-slate-200 text-xs">Step-by-Step Derivation:</div>
                        {pipelineState.result.solution.steps.map((step: any, idx: number) => {
                          const title = typeof step === "string" ? `Step ${idx + 1}` : (step.title || `Step ${idx + 1}`);
                          const explanation = typeof step === "string" ? step : (step.explanation || step.say || "");
                          const formula = typeof step === "string" ? "" : (step.formula || step.calculation || "");
                          return (
                          <div key={idx} className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800">
                            <div className="font-semibold text-sky-400 mb-1">{title}</div>
                            <p className="text-slate-300 leading-relaxed">{explanation}</p>
                            {formula && <div className="mt-2 font-mono text-indigo-300 bg-indigo-950/40 p-2 rounded-lg border border-indigo-900/50">{formula}</div>}
                          </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
                {activeTab === "plan" && (
                  <div className="flex flex-col gap-2 text-xs">
                    {(pipelineState.result?.plan?.scenes || previewScenes).map((sc: any) => (
                      <div key={sc.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex flex-wrap gap-2 items-center">
                        <span className="font-semibold text-sky-400">{sc.id}</span>
                        <span className="text-slate-400">{sc.type}</span>
                        <span className="text-indigo-300">{sc.engine || "—"}</span>
                        <span className="text-slate-500">{sc.visualMode}</span>
                        <span className="text-slate-500">{sc.duration}s</span>
                        {sc.status ? <span className="text-emerald-400">{sc.status}</span> : null}
                      </div>
                    ))}
                  </div>
                )}
                {activeTab === "timeline" && (
                  <pre className="p-4 rounded-2xl bg-slate-950 font-mono text-[11px] text-sky-300 overflow-x-auto border border-slate-800">
                    {JSON.stringify(pipelineState.result?.timeline || { note: "Timeline after Stage 4" }, null, 2)}
                  </pre>
                )}
                {activeTab === "raw" && (
                  <pre className="p-4 rounded-2xl bg-slate-950 font-mono text-[11px] text-sky-300 overflow-x-auto border border-slate-800">
                    {JSON.stringify({ visualAudit, result: pipelineState.result }, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}

          {/* LIVE SYSTEM TERMINAL & DEBUG CONSOLE WIDGET */}
          <div className="glass-panel rounded-3xl p-6 flex flex-col gap-4 border border-indigo-500/25 bg-slate-950/90 shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Terminal className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <span>Live System & Debug Console</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    {filteredLogs.length} logs
                  </span>
                </h3>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs">
                <div className="flex items-center bg-slate-900 rounded-xl p-1 border border-slate-800 text-[11px] font-semibold">
                  {(["ALL", "INFO", "WARN", "ERROR"] as const).map((filter) => (
                    <button key={filter} type="button" onClick={() => setLogFilter(filter)} className={`px-2.5 py-1 rounded-lg transition-all ${logFilter === filter ? "bg-indigo-600 text-white shadow-sm" : "text-slate-400 hover:text-slate-200"}`}>
                      {filter}
                    </button>
                  ))}
                </div>

                <button type="button" onClick={copyConsoleLogs} className="px-2.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 font-semibold flex items-center gap-1 border border-slate-800 transition-all" title="Copy Console Logs">
                  {copiedLogs ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedLogs ? "Copied" : "Copy Logs"}</span>
                </button>

                <button type="button" onClick={clearLogs} className="px-2.5 py-1.5 rounded-xl bg-slate-900 hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 font-semibold flex items-center gap-1 border border-slate-800 transition-all" title="Clear Console">
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Clear</span>
                </button>
              </div>
            </div>

            <div className="bg-[#050811] rounded-2xl p-4 font-mono text-[11px] max-h-72 overflow-y-auto border border-slate-800/80 space-y-1.5 shadow-inner">
              {filteredLogs.length === 0 ? (
                <div className="text-slate-600 italic py-4 text-center">No logs match the current filter.</div>
              ) : (
                filteredLogs.map((log, idx) => (
                  <div key={idx} className="flex items-start gap-2 leading-relaxed hover:bg-slate-900/40 p-1 rounded transition-colors">
                    <span className="text-slate-500 shrink-0">[{log.timestamp}]</span>
                    <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold shrink-0 ${log.level === "INFO" ? "bg-sky-500/10 text-sky-400 border border-sky-500/30" : log.level === "SUCCESS" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30" : log.level === "WARN" ? "bg-amber-500/10 text-amber-400 border border-amber-500/30" : "bg-rose-500/10 text-rose-400 border border-rose-500/30"}`}>
                      {log.level}
                    </span>
                    <span className={`break-all ${log.level === "ERROR" ? "text-rose-300 font-semibold" : log.level === "WARN" ? "text-amber-300" : log.level === "SUCCESS" ? "text-emerald-300 font-semibold" : "text-slate-300"}`}>
                      {log.message}
                    </span>
                  </div>
                ))
              )}
              <div ref={consoleBottomRef} />
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono pt-1">
              <div className="flex items-center gap-2">
                <span className="text-emerald-400 font-bold">&gt;</span>
                <span>Live System Console • Real-time backend execution stream & error tracking</span>
              </div>
              <button type="button" onClick={() => setAutoScrollLogs(!autoScrollLogs)} className={`text-[10px] font-semibold px-2 py-0.5 rounded border transition-all ${autoScrollLogs ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" : "bg-slate-900 text-slate-500 border-slate-800"}`}>
                {autoScrollLogs ? "Auto-Scroll: ON" : "Auto-Scroll: OFF"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
