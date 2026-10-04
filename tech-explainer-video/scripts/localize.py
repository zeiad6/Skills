#!/usr/bin/env python3
"""Localize ANY video: detect language → transcribe → (Claude translates) → dub + subtitles.

Step 1 — prepare (fully automatic):
    python3 localize.py prepare <video> <workdir> [--to ar] [--model small]
  • detects the spoken language (multilingual Whisper) and transcribes with timestamps
  • splits speech into subtitle-sized cues on sentence/clause boundaries
  • detects a burned-in caption band to cover (heuristic; verify on <workdir>/band.jpg)
  • writes <workdir>/job.json with empty "text"/"dub" fields + contact sheet <workdir>/sheet.jpg

Step 2 — translate (Claude): fill every cue in job.json:
    "text": natural, idiomatic subtitle in the target language (≤ ~45 chars)
    "dub":  the spoken line — condensed (~35% shorter than literal for Arabic), same meaning
  Keep tech terms in English. Use sheet.jpg / band.jpg to fix ASR errors and confirm "cover".

Step 3 — finish (automatic):
    python3 localize.py finish <workdir> <out.mp4> [--mode dub|subs|both] [--voice ar-female]
  dub  : neural voice + subtitles re-timed to it (default)   subs: burned subtitles only, original audio
"""
import argparse, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CACHE = os.path.expanduser("~/.cache/tech-explainer-video")
REL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"


def fetch_model(name):
    import tarfile, urllib.request
    d = os.path.join(CACHE, f"sherpa-onnx-whisper-{name}")
    if not os.path.isdir(d):
        os.makedirs(CACHE, exist_ok=True)
        tb = d + ".tar.bz2"
        print("downloading whisper", name, "(one-time)", file=sys.stderr)
        urllib.request.urlretrieve(REL + f"sherpa-onnx-whisper-{name}.tar.bz2", tb)
        with tarfile.open(tb) as t:
            t.extractall(CACHE)
        os.remove(tb)
    vad = os.path.join(CACHE, "silero_vad.onnx")
    if not os.path.exists(vad):
        urllib.request.urlretrieve(REL + "silero_vad.onnx", vad)
    return d, vad


def transcribe(src, model="small", lang=""):
    """Returns (language, [{start, end, text}]). lang="" auto-detects (multilingual models)."""
    import numpy as np, sherpa_onnx, wave
    d, vad_path = fetch_model(model)
    p = lambda s: os.path.join(d, f"{model}-{s}")
    pick = lambda s: p(s.replace(".onnx", ".int8.onnx")) if os.path.exists(p(s.replace(".onnx", ".int8.onnx"))) else p(s)
    multi = not model.endswith(".en")
    wav = os.path.join(CACHE, "_in.wav")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "16000", wav])
    w = wave.open(wav); sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768

    def recognizer(language):
        return sherpa_onnx.OfflineRecognizer.from_whisper(encoder=pick("encoder.onnx"), decoder=pick("decoder.onnx"),
                                                          tokens=p("tokens.txt"), language=language if multi else "",
                                                          task="transcribe", num_threads=4)
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = vad_path
    cfg.silero_vad.min_silence_duration = 0.15
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = 12
    cfg.sample_rate = sr
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=900)
    chunks = []
    for i in range(0, len(x), cfg.silero_vad.window_size):
        vad.accept_waveform(x[i:i + cfg.silero_vad.window_size])
        while not vad.empty():
            chunks.append((vad.front.start / sr, np.array(vad.front.samples, dtype=np.float32))); vad.pop()
    vad.flush()
    while not vad.empty():
        chunks.append((vad.front.start / sr, np.array(vad.front.samples, dtype=np.float32))); vad.pop()

    rec = recognizer(lang)
    detected = lang or "en"
    if multi and not lang and chunks:
        # language detection on the longest chunk (whisper's own language token)
        st = rec.create_stream(); st.accept_waveform(sr, max(chunks, key=lambda c: len(c[1]))[1]); rec.decode_stream(st)
        detected = getattr(st.result, "lang", "") or "en"
        detected = detected.strip("<|>") or "en"
        rec = recognizer(detected)
    segs = []
    for st0, smp in chunks:
        s = rec.create_stream(); s.accept_waveform(sr, smp); rec.decode_stream(s)
        t = s.result.text.strip()
        if t:
            segs.append({"start": round(st0, 2), "end": round(st0 + len(smp) / sr, 2), "text": t})
            print(f"{st0:7.2f}  {t}", file=sys.stderr)
    return detected, segs


def split_cues(segs, max_chars=70):
    """Split each speech segment on sentence/clause punctuation; time proportional to text length.
    Cues inside one segment are contiguous (they form one breath group for dubbing)."""
    cues = []
    for sg in segs:
        parts = [p.strip() for p in re.split(r"(?<=[.!?;:,])\s+", sg["text"]) if p.strip()]
        merged = []                                   # merge tiny clauses, split long ones on words
        for p in parts:
            if merged and len(merged[-1]) < 22 and len(merged[-1]) + len(p) < max_chars:
                merged[-1] += " " + p
            else:
                merged.append(p)
        final = []
        for p in merged:
            while len(p) > max_chars:
                cut = p.rfind(" ", 0, max_chars)
                cut = cut if cut > 20 else max_chars
                final.append(p[:cut].strip()); p = p[cut:].strip()
            final.append(p)
        tot = sum(len(p) for p in final); t = sg["start"]
        for p in final:
            d = (sg["end"] - sg["start"]) * len(p) / tot
            cues.append({"start": round(t, 2), "end": round(t + d, 2), "src": p, "text": "", "dub": ""}); t += d
    return cues


def detect_caption_band(src, cues, w, h):
    """Heuristic: rows in the lower 60% that hold high-contrast, changing text in nearly every frame
    sampled during speech are burned-in captions. Returns (y, height) in source pixels, or None."""
    import numpy as np
    times = [(c["start"] + c["end"]) / 2 for c in cues][:: max(1, len(cues) // 24)]
    sw = 360; sh = int(h * sw / w) // 2 * 2
    frames = []
    for t in times:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf",
                              f"scale={sw}:{sh},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        if len(raw) == sw * sh:
            frames.append(np.frombuffer(raw, np.uint8).reshape(sh, sw).astype(np.float32))
    if len(frames) < 4:
        return None
    F = np.stack(frames)
    edges = (np.abs(np.diff(F, axis=2)) > 60).mean(axis=2)          # per-row horizontal edge density
    busy = (edges > 0.04).mean(axis=0)                               # fraction of frames with text-like rows
    change = np.abs(np.diff(F, axis=0)).mean(axis=(0, 2))            # text changes between cues
    score = busy * (change > 6)
    lo = int(sh * 0.4)
    rows = [r for r in range(lo, sh) if score[r] >= 0.75]
    if not rows:
        return None
    # largest contiguous run
    runs, cur = [], [rows[0]]
    for r in rows[1:]:
        if r - cur[-1] <= 3:
            cur.append(r)
        else:
            runs.append(cur); cur = [r]
    runs.append(cur)
    run = max(runs, key=len)
    if len(run) < sh * 0.015:
        return None
    k = h / sh
    pad = int(0.022 * h)
    y0 = max(0, int(run[0] * k) - pad); y1 = min(h, int(run[-1] * k) + pad)
    return [y0, y1 - y0]


def prepare(a):
    sys.path.insert(0, HERE)
    from dub_video import probe
    os.makedirs(a.workdir, exist_ok=True)
    w, h, dur = probe(a.video)
    lang, segs = transcribe(a.video, a.model, a.lang)
    cues = split_cues(segs)
    band = detect_caption_band(a.video, cues, w, h) if cues else None
    # contact sheet + band preview for Claude to verify visually
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf",
                    f"fps={max(0.05, 32 / max(dur, 1)):.4f},scale=200:-2,tile=8x4", "-frames:v", "1",
                    os.path.join(a.workdir, "sheet.jpg")])
    if cues:
        mid = (cues[len(cues) // 2]["start"] + cues[len(cues) // 2]["end"]) / 2
        box = f",drawbox=x=0:y={band[0]}:w=iw:h={band[1]}:color=red@0.9:t=4" if band else ""
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{mid:.2f}", "-i", a.video, "-frames:v", "1", "-vf",
                        f"scale={w}:{h}{box}", os.path.join(a.workdir, "band.jpg")])
    job = {"video": os.path.abspath(a.video), "source_lang": lang, "target_lang": a.to, "width": w, "height": h,
           "duration": round(dur, 2), "cover": band, "voice": "ar-female" if a.to == "ar" else f"{a.to}-female",
           "segments": segs, "cues": cues}
    json.dump(job, open(os.path.join(a.workdir, "job.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"language: {lang} · {len(segs)} segments · {len(cues)} cues · caption band: {band or 'none detected'}")
    print(f"next: fill text/dub in {a.workdir}/job.json, check band.jpg + sheet.jpg, then `localize.py finish`")


def finish(a):
    from dub_video import dub
    from burn_subs import srt_time
    job = json.load(open(os.path.join(a.workdir, "job.json"), encoding="utf-8"))
    cues = job["cues"]
    missing = [i for i, c in enumerate(cues) if not c.get("text")]
    if missing:
        sys.exit(f"cues without a translation: {missing[:20]}{'…' if len(missing) > 20 else ''}")
    cover = tuple(job["cover"]) if job.get("cover") else None
    voice = a.voice or job.get("voice", "ar-female")
    if a.mode == "subs":
        cj = os.path.join(a.workdir, "_cues.json")
        json.dump([{"start": c["start"], "end": c["end"], "text": c["text"]} for c in cues], open(cj, "w", encoding="utf-8"), ensure_ascii=False)
        args = [sys.executable, os.path.join(HERE, "burn_subs.py"), job["video"], cj, a.out]
        if cover:
            args += ["--cover", f"{cover[0]},{cover[1]}"]
        subprocess.check_call(args)
        return
    for c in cues:
        c.setdefault("dub", "")
        c["dub"] = c["dub"] or c["text"]
    factors = dub(job["video"], cues, a.out, cover, voice, a.speed, a.keep_bg, subs=(a.mode != "dub-nosubs"),
                  log=lambda m: print(m, file=sys.stderr))
    if max(factors) > 1.21:
        print("⚠ some sections were slowed > 20% — shorten their `dub` lines and run finish again", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("video"); p.add_argument("workdir")
    p.add_argument("--to", default="ar"); p.add_argument("--model", default="small", help="small | medium | small.en …")
    p.add_argument("--lang", default="", help="force source language code (skip detection)")
    f = sp.add_parser("finish"); f.add_argument("workdir"); f.add_argument("out")
    f.add_argument("--mode", default="dub", choices=["dub", "subs", "dub-nosubs"])
    f.add_argument("--voice"); f.add_argument("--speed", type=float, default=1.0)
    f.add_argument("--keep-bg", type=float, default=0.0)
    a = ap.parse_args()
    prepare(a) if a.cmd == "prepare" else finish(a)


if __name__ == "__main__":
    main()
