# -*- coding: utf-8 -*-
"""Transcreve mentoria 16/03/2026 na GPU (faster-whisper large-v3, int8_float16)."""
import sys, os, time, tempfile, subprocess, glob
from pathlib import Path

# CUDA DLLs no PATH ANTES de importar faster_whisper
try:
    import nvidia
    for _base in list(nvidia.__path__):
        for _sub in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
            _b = os.path.join(_base, _sub, "bin")
            if os.path.isdir(_b):
                os.environ["PATH"] = _b + os.pathsep + os.environ["PATH"]
except Exception as ex:
    print(f"[WARN] nvidia path setup: {ex}")

from faster_whisper import WhisperModel

AUDIO  = Path(r"C:\Users\jorge\Documents\CLAUDE\corretor-impugnacao\_build\mentoria\marco16_audio.wav")
OUT    = Path(r"C:\Users\jorge\Documents\CLAUDE\corretor-impugnacao\_build\mentoria\marco16_transcricao.txt")
FFMPEG = r"C:\Users\jorge\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.EXE"
FFPROBE= r"C:\Users\jorge\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.EXE"
CHUNK  = 600  # 10 min por fatia

def hms(s):
    s = int(s); return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

t0 = time.time()
r = subprocess.run([FFPROBE,"-v","error","-show_entries","format=duration","-of",
                    "default=noprint_wrappers=1:nokey=1", str(AUDIO)],
                   capture_output=True, text=True)
try: dur = float((r.stdout or "").strip() or 0)
except ValueError: dur = 0.0
print(f"Audio: {AUDIO.name} | duracao: {hms(dur)}", flush=True)

segs = []
with tempfile.TemporaryDirectory(prefix="ment_") as td:
    td = Path(td)
    print("[1/3] fatiando audio...", flush=True)
    subprocess.run([FFMPEG, "-y", "-i", str(AUDIO), "-f", "segment",
                    "-segment_time", str(CHUNK), str(td / "chunk_%03d.wav")],
                   capture_output=True)
    chunks = sorted(glob.glob(str(td / "chunk_*.wav")))
    print(f"    {len(chunks)} pedacos | {(time.time()-t0):.0f}s", flush=True)

    print("[2/3] carregando modelo large-v3 (GPU, int8)...", flush=True)
    m = WhisperModel("large-v3", device="cuda", compute_type="int8")
    print(f"    modelo carregado | {(time.time()-t0):.0f}s", flush=True)

    for i, ch in enumerate(chunks):
        off = i * CHUNK
        sr, _ = m.transcribe(ch, language="pt", vad_filter=True,
                             beam_size=1, condition_on_previous_text=True)
        n = 0
        for s in sr:
            txt = (s.text or "").strip()
            if txt:
                segs.append({"start": off + float(s.start), "text": txt}); n += 1
        print(f"    pedaco {i+1}/{len(chunks)} ({hms(off)}) -> {n} falas | {(time.time()-t0)/60:.1f}min", flush=True)

print(f"[3/3] {len(segs)} falas. salvando em {OUT}...", flush=True)
lines = [
    f"# Transcricao — Mentoria Coletiva 16/03/2026",
    f"",
    f"**Aula:** Mentoria Coletiva 16/03 (lesson 3244, videoId 491f6d3f-5b8a-4ba1-883c-76b831dbe664)",
    f"**Duracao:** {hms(dur)}  |  **Modelo:** faster-whisper large-v3 (GPU, int8)",
    f"**Processo exercicio:** 0100912-64.2025.5.01.0005 — Alberto Teixeira Marins x Sunflow Suplementos",
    f"",
    f"> Transcricao automatica. Conferir trechos criticos no audio.",
    f"",
    f"## Texto com marcacao de tempo",
    f"",
]
for s in segs:
    lines.append(f"[{hms(s['start'])}] {s['text']}")
lines += ["", "---", "", "## Texto corrido", "", " ".join(s["text"] for s in segs)]
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"SALVO: {OUT}", flush=True)
print(f"FIM em {(time.time()-t0)/60:.1f} min | {len(segs)} falas | duracao {hms(dur)}", flush=True)
