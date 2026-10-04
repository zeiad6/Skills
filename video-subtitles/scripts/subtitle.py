#!/usr/bin/env python3
"""Film-style translated subtitles for any video — the original video and audio are left untouched.

    python3 subtitle.py prepare <video> <work>  [--lang auto|en|es|ar|…] [--model auto|parakeet|whisper-medium|whisper-large-v3]
    #  → work/cues.json  (timed source-language cues, empty "text" for the translation)
    #    work/transcript.txt, work/sheet.jpg (contact sheet), work/frame.jpg (placement preview)
    #  Claude now translates every cue: fill "text" in work/cues.json
    python3 subtitle.py check  <work>                         # line length, reading speed, empty cues
    python3 subtitle.py render <work> <out.mp4> [--mode burn|soft|both] [--size 1.0] [--position auto|bottom|top]

ASR: Parakeet-TDT 0.6B v3 (English + 24 European languages) gives per-word timestamps, so cues start
and end exactly on speech. Other languages use Whisper on short VAD chunks. Models download once from
GitHub releases (k2-fsa/sherpa-onnx) and run offline on CPU.
"""
import argparse, json, os, re, subprocess, sys, tarfile, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "assets", "fonts")
CACHE = os.path.expanduser("~/.cache/video-subtitles")
REL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
PARAKEET = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
PARAKEET_LANGS = set("bg hr cs da nl en et fi fr de el hu it lv lt mt pl pt ro sk sl es sv ru uk".split())
RTL = ("ar", "fa", "ur", "he", "ps", "ckb")

# Subtitle rules (broadcast/streaming conventions)
MAX_LINE = 42          # characters per line
MAX_CUE_CHARS = 84     # two lines
MIN_DUR, MAX_DUR = 1.0, 6.5
GAP = 0.084            # >= 2 frames between consecutive cues
LEAD, HOLD = 0.05, 0.25


# ----------------------------------------------------------------------------- models
def _deps():
    try:
        import sherpa_onnx, numpy  # noqa
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "sherpa-onnx", "numpy"])


def fetch(name):
    os.makedirs(CACHE, exist_ok=True)
    for alt in (os.path.join(CACHE, name), os.path.expanduser(f"~/.cache/tech-explainer-video/{name}")):
        if os.path.exists(alt):
            return alt
    dest = os.path.join(CACHE, name)
    url = REL + (name if name.endswith(".onnx") else name + ".tar.bz2")
    print(f"downloading {name} (one-time)…", file=sys.stderr)
    if name.endswith(".onnx"):
        urllib.request.urlretrieve(url, dest)
    else:
        urllib.request.urlretrieve(url, dest + ".tar.bz2")
        with tarfile.open(dest + ".tar.bz2") as t:
            t.extractall(CACHE)
        os.remove(dest + ".tar.bz2")
    return dest


def load_audio(src):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def vad_chunks(x, max_len):
    import numpy as np, sherpa_onnx
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = fetch("silero_vad.onnx")
    cfg.silero_vad.min_silence_duration = 0.25
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = max_len
    cfg.sample_rate = 16000
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=max(60, len(x) / 16000 + 10))
    out, win = [], cfg.silero_vad.window_size
    for i in range(0, len(x), win):
        vad.accept_waveform(x[i:i + win])
        while not vad.empty():
            out.append((vad.front.start / 16000, np.array(vad.front.samples, dtype=np.float32))); vad.pop()
    vad.flush()
    while not vad.empty():
        out.append((vad.front.start / 16000, np.array(vad.front.samples, dtype=np.float32))); vad.pop()
    return out


def whisper(name, lang):
    import sherpa_onnx
    d = fetch(f"sherpa-onnx-whisper-{name}")
    p = lambda s: os.path.join(d, f"{name}-{s}")
    pick = lambda s: p(s.replace(".onnx", ".int8.onnx")) if os.path.exists(p(s.replace(".onnx", ".int8.onnx"))) else p(s)
    return sherpa_onnx.OfflineRecognizer.from_whisper(encoder=pick("encoder.onnx"), decoder=pick("decoder.onnx"),
                                                      tokens=p("tokens.txt"), language=lang, task="transcribe",
                                                      num_threads=os.cpu_count() or 4)


def detect_language(chunks):
    rec = whisper("small", "")
    longest = max(chunks, key=lambda c: len(c[1]))[1]
    st = rec.create_stream(); st.accept_waveform(16000, longest); rec.decode_stream(st)
    return (getattr(st.result, "lang", "") or "en").strip("<|> ") or "en"


def words_parakeet(chunks):
    import sherpa_onnx
    d = fetch(PARAKEET)
    f = lambda k: os.path.join(d, next(x for x in os.listdir(d) if x.startswith(k) and x.endswith(".onnx")))
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=f("encoder"), decoder=f("decoder"), joiner=f("joiner"),
                                                        tokens=os.path.join(d, "tokens.txt"), model_type="nemo_transducer",
                                                        num_threads=os.cpu_count() or 4)
    words = []
    for t0, smp in chunks:
        st = rec.create_stream(); st.accept_waveform(16000, smp); rec.decode_stream(st)
        r, end = st.result, t0 + len(smp) / 16000
        cur = None
        for tok, ts in zip(r.tokens, r.timestamps):
            if tok.startswith(" ") or cur is None:
                if cur:
                    words.append(cur)
                cur = {"w": tok.strip(), "s": t0 + ts, "e": t0 + ts + 0.12}
            else:
                cur["w"] += tok; cur["e"] = t0 + ts + 0.12
        if cur:
            words.append(cur)
        # a word lasts until the next one starts (within the chunk), never past the chunk end
        chunk_words = [w for w in words if t0 <= w["s"] <= end]
        for a, b in zip(chunk_words, chunk_words[1:]):
            a["e"] = min(max(a["e"], b["s"] - 0.02), b["s"])
        if chunk_words:
            chunk_words[-1]["e"] = min(end, chunk_words[-1]["e"] + 0.15)
    return [w for w in words if w["w"]]


def words_whisper(chunks, model, lang):
    rec = whisper(model, lang)
    words = []
    for t0, smp in chunks:
        st = rec.create_stream(); st.accept_waveform(16000, smp); rec.decode_stream(st)
        text = st.result.text.strip()
        toks = text.split()
        if not toks:
            continue
        dur = len(smp) / 16000
        tot = sum(len(t) + 1 for t in toks); acc = 0
        for t in toks:     # Whisper gives no word times: spread over the (short) VAD chunk by length
            s = t0 + dur * acc / tot; acc += len(t) + 1
            words.append({"w": t, "s": s, "e": t0 + dur * acc / tot})
    return words


# ----------------------------------------------------------------------------- segmentation
def segment(words):
    """Group timed words into subtitle cues: sentence-aware, ≤ 2 lines, 1–6.5 s, split at pauses."""
    cues, cur = [], []

    def flush():
        if cur:
            cues.append({"start": cur[0]["s"], "end": cur[-1]["e"], "src": " ".join(w["w"] for w in cur)})
            cur.clear()

    for i, w in enumerate(words):
        if cur:
            text = " ".join(x["w"] for x in cur)
            pause = w["s"] - cur[-1]["e"]
            dur = w["e"] - cur[0]["s"]
            sent_end = re.search(r"[.!?…]$", cur[-1]["w"])
            clause = re.search(r"[,;:]$", cur[-1]["w"])
            too_long = len(text) + 1 + len(w["w"]) > MAX_CUE_CHARS or dur > MAX_DUR
            if pause > 0.6 or (sent_end and len(text) >= 12) or (clause and len(text) > 45) or too_long:
                if too_long and not (sent_end or clause or pause > 0.3):
                    # back off to the last clause/pause boundary inside the cue, if any
                    for k in range(len(cur) - 1, 0, -1):
                        if re.search(r"[,;:.!?]$", cur[k - 1]["w"]) or cur[k]["s"] - cur[k - 1]["e"] > 0.25:
                            rest = cur[k:]; del cur[k:]; flush(); cur.extend(rest); break
                    else:
                        flush()
                    if cur and (len(" ".join(x["w"] for x in cur)) + len(w["w"]) > MAX_CUE_CHARS):
                        flush()
                else:
                    flush()
        cur.append(w)
    flush()
    # timing polish: lead-in, hold, minimum duration, 2-frame gaps
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else c["end"] + 5
        prv = cues[i - 1]["end"] if i else 0
        c["start"] = max(prv + GAP if i else 0, c["start"] - LEAD)
        c["end"] = min(nxt - GAP, max(c["end"] + HOLD, c["start"] + MIN_DUR))
        c["start"], c["end"] = round(c["start"], 3), round(c["end"], 3)
    return cues


# ----------------------------------------------------------------------------- burned-in caption detection
def probe(src):
    w, h = map(int, subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height", "-of", "csv=p=0:s=x", src]).decode().split("x")[:2])
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]))
    return w, h, dur


def detect_caption_band(src, cues, w, h):
    """Rows holding high-contrast text that changes with speech in nearly every sampled frame = burned-in
    captions. Returns [y, height] in source pixels or None."""
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
    busy = ((np.abs(np.diff(F, axis=2)) > 60).mean(axis=2) > 0.04).mean(axis=0)
    change = np.abs(np.diff(F, axis=0)).mean(axis=(0, 2))
    rows = [r for r in range(int(sh * 0.4), sh) if busy[r] >= 0.75 and change[r] > 6]
    if not rows:
        return None
    runs, cur = [], [rows[0]]
    for r in rows[1:]:
        (cur.append(r) if r - cur[-1] <= 3 else (runs.append(cur), cur := [r]))
    runs.append(cur)
    run = max(runs, key=len)
    if len(run) < sh * 0.015:
        return None
    k, pad = h / sh, int(0.022 * h)
    y0, y1 = max(0, int(run[0] * k) - pad), min(h, int(run[-1] * k) + pad)
    return [y0, y1 - y0]


# ----------------------------------------------------------------------------- commands
def cmd_prepare(a):
    _deps()
    os.makedirs(a.work, exist_ok=True)
    w, h, dur = probe(a.video)
    x = load_audio(a.video)
    lang = a.lang
    chunks = vad_chunks(x, 20)
    if not chunks:
        sys.exit("no speech found in the video")
    if lang == "auto":
        lang = detect_language(chunks)
        print(f"detected language: {lang}", file=sys.stderr)
    model = a.model
    if model == "auto":
        model = "parakeet" if lang in PARAKEET_LANGS else "whisper-medium"
    if model == "parakeet":
        words = words_parakeet(chunks)
    else:
        words = words_whisper(vad_chunks(x, 8), model.replace("whisper-", ""), lang)
    cues = segment(words)
    band = detect_caption_band(a.video, cues, w, h) if cues else None
    for i, c in enumerate(cues):
        c.update({"i": i + 1, "text": ""})
    job = {"video": os.path.abspath(a.video), "source_lang": lang, "target_lang": a.to, "asr": model,
           "width": w, "height": h, "duration": round(dur, 3), "existing_captions": band, "cues": cues}
    json.dump(job, open(os.path.join(a.work, "cues.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(words, open(os.path.join(a.work, "words.json"), "w", encoding="utf-8"), ensure_ascii=False)
    with open(os.path.join(a.work, "transcript.txt"), "w", encoding="utf-8") as f:
        for c in cues:
            f.write(f"[{c['i']:>3}] {c['start']:7.2f}-{c['end']:7.2f}  {c['src']}\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf",
                    f"fps={max(0.05, 32 / max(dur, 1)):.4f},scale=200:-2,tile=8x4", "-frames:v", "1",
                    os.path.join(a.work, "sheet.jpg")])
    print(f"{lang} · {model} · {len(words)} words → {len(cues)} cues · existing captions: {band or 'none'}")
    print(f"next: translate every cue's \"text\" in {a.work}/cues.json, then `subtitle.py check {a.work}`")


def wrap(text, max_line=MAX_LINE):
    """Two balanced lines, breaking after punctuation when possible (bottom line may be longer)."""
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= max_line:
        return [text]
    spaces = [m.start() for m in re.finditer(" ", text)]
    mid = len(text) / 2
    def cost(i):
        c = abs(i - mid)
        if re.search(r"[،,.;:؛!?؟]$", text[:i]):
            c -= 6
        if i > mid:                      # pyramid shape: prefer a shorter top line
            c += 1
        return c
    i = min(spaces, key=cost)
    return [text[:i], text[i + 1:]]


def cps_limit(lang):
    return 17 if lang in RTL else 20


def cmd_check(a, quiet=False):
    job = json.load(open(os.path.join(a.work, "cues.json"), encoding="utf-8"))
    lang, problems = job["target_lang"], []
    for c in job["cues"]:
        t = c.get("text", "").strip()
        if not t:
            problems.append(f"[{c['i']}] missing translation"); continue
        lines = wrap(t)
        if len(lines) > 2 or max(len(l) for l in lines) > MAX_LINE + 6:
            problems.append(f"[{c['i']}] too long ({len(t)} chars) — condense: {t}")
        cps = len(t.replace(" ", "")) / max(0.1, c["end"] - c["start"])
        if cps > cps_limit(lang) + 4:
            problems.append(f"[{c['i']}] reading speed {cps:.0f} cps > {cps_limit(lang)} — condense: {t}")
    if not quiet:
        print("\n".join(problems) if problems else f"✓ {len(job['cues'])} cues pass (≤2 lines × {MAX_LINE}, ≤{cps_limit(lang)} cps)")
    return problems


def ts_ass(t):
    cs = int(round(t * 100)); return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ts_srt(t):
    ms = int(round(t * 1000)); return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cmd_render(a):
    job = json.load(open(os.path.join(a.work, "cues.json"), encoding="utf-8"))
    missing = [c["i"] for c in job["cues"] if not c.get("text", "").strip()]
    if missing:
        sys.exit(f"cues without translation: {missing[:30]}")
    for p in cmd_check(a, quiet=True):
        print("⚠", p, file=sys.stderr)
    w, h, lang = job["width"], job["height"], job["target_lang"]
    rtl = lang in RTL
    mark = "‏" if rtl else ""
    lines_of = lambda c: [mark + l for l in wrap(c["text"])]

    base = os.path.splitext(a.out)[0]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(base + ".srt", "w", encoding="utf-8") as f:
        for k, c in enumerate(job["cues"], 1):
            f.write(f"{k}\n{ts_srt(c['start'])} --> {ts_srt(c['end'])}\n" + "\n".join(lines_of(c)) + "\n\n")

    # style: white bold, black outline + soft shadow, no box — scaled to the frame
    size = round(0.057 * min(w, h) * a.size)
    outline, shadow = round(size * 0.08, 1), round(size * 0.035, 1)
    band = job.get("existing_captions")
    align, margin = 2, round(h * 0.06)
    two_lines = size * 2.6
    if a.position == "top":
        align, margin = 8, round(h * 0.06)
    elif band and a.position == "auto":
        below = h - (band[0] + band[1])
        if below > two_lines + h * 0.03:          # room under the existing captions
            margin = max(round(h * 0.03), round(below - two_lines) // 2)
        else:                                     # otherwise sit just above them
            margin = h - band[0] + round(h * 0.015)
    ass = base + ".ass"
    with open(ass, "w", encoding="utf-8") as f:
        f.write(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Cairo,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},{align},{round(w * 0.05)},{round(w * 0.05)},{margin},{-1 if rtl else 1}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
        for c in job["cues"]:
            f.write(f"Dialogue: 0,{ts_ass(c['start'])},{ts_ass(c['end'])},Sub,,0,0,0,,{(chr(92) + 'N').join(lines_of(c))}\n")

    src = job["video"]
    iso = {"ar": "ara", "en": "eng", "fr": "fra", "es": "spa", "de": "deu", "tr": "tur", "fa": "per", "ur": "urd"}.get(lang, lang)
    if a.mode in ("burn", "both"):
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"ass={ass}:fontsdir={FONTS}",
                               "-c:v", "libx264", "-crf", str(a.crf), "-preset", "slow", "-pix_fmt", "yuv420p",
                               "-c:a", "copy", "-movflags", "+faststart", a.out])
        print("burned:", a.out)
    if a.mode in ("soft", "both"):
        soft = a.out if a.mode == "soft" else base + ".soft.mp4"
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", base + ".srt", "-map", "0", "-map", "1",
                               "-c", "copy", "-c:s", "mov_text", f"-metadata:s:s:0", f"language={iso}",
                               "-movflags", "+faststart", soft])
        print("soft (toggleable track, video untouched):", soft)
    print("subtitles:", base + ".srt", base + ".ass")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("video"); p.add_argument("work")
    p.add_argument("--lang", default="auto"); p.add_argument("--to", default="ar")
    p.add_argument("--model", default="auto", help="auto | parakeet | whisper-medium | whisper-large-v3 | whisper-small")
    c = sp.add_parser("check"); c.add_argument("work")
    r = sp.add_parser("render"); r.add_argument("work"); r.add_argument("out")
    r.add_argument("--mode", default="burn", choices=["burn", "soft", "both"])
    r.add_argument("--size", type=float, default=1.0); r.add_argument("--crf", type=int, default=17)
    r.add_argument("--position", default="auto", choices=["auto", "bottom", "top"])
    a = ap.parse_args()
    {"prepare": cmd_prepare, "check": cmd_check, "render": cmd_render}[a.cmd](a)


if __name__ == "__main__":
    main()
