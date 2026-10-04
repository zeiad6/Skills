#!/usr/bin/env python3
"""Dub an existing video with an offline neural voice, subtitles re-timed to the new speech.

    python3 dub_video.py <in.mp4> <cues.json> <out.mp4> [--cover 740,92] [--voice ar-female] [--speed 1.0]
                         [--keep-bg 0] [--no-subs]

cues.json: [{"start", "end", "text", "dub"?}] in source time. `text` is burned as the subtitle; `dub`
is the line to speak (defaults to text). Arabic runs ~1.5-1.8x longer than English: write dub lines
~35% shorter than a literal translation, and use the same text for the subtitle so viewers read what
they hear. (Most users should call scripts/localize.py, which prepares cues.json for you.)

Timing: consecutive cues with no gap form a section (one breath group of the original speaker).
Each section is voiced as continuous speech (sentence-level synthesis, no per-fragment chopping) and
its video is slowed just enough for the speech to fit (factor >= 1), so voice, subtitles and
on-screen animation stay in sync. Factors are printed; aim for <= 1.15 by shortening dub lines.
"""
import argparse, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts import Voice, DEFAULT_VOICE, VOICES, master  # noqa: E402
from burn_subs import ass_time, srt_time, FONTS  # noqa: E402


def probe(src):
    w, h = map(int, subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height", "-of", "csv=p=0:s=x", src]).decode().split("x"))
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]))
    return w, h, dur


def write_ass(path, w, h, cover, events):
    size = round(h * 0.031)
    if cover:
        y, bh = cover
        mv = h - (y + bh // 2) - size // 2
    else:
        mv = round(h * 0.12)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\n\n[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                f"Style: S,Cairo,{size},&H00FFFFFF,&H00FFFFFF,&H001A1715,&H001A1715,-1,0,0,0,100,100,0,0,3,{max(4, size // 3)},0,2,{w // 14},{w // 14},{mv},-1\n\n"
                "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for s, e, t in events:
            f.write(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},S,,0,0,0,,{t.replace(chr(10), chr(92) + 'N')}\n")


def dub(src, cues, out, cover=None, voice=DEFAULT_VOICE, speed=1.0, keep_bg=0.0, subs=True, log=print):
    import numpy as np, soundfile as sf
    sub = lambda c: c.get("ar") or c.get("translation") or c["text"]
    w, h, dur = probe(src)
    secs = [[cues[0]]]
    for p, c in zip(cues, cues[1:]):
        (secs[-1].append(c) if c["start"] - p["end"] < 0.05 else secs.append([c]))

    v = Voice(voice, speed)
    audios, spans_all, factors = [], [], []
    starts = [0.0] + [s[0]["start"] for s in secs[1:]]
    ends = starts[1:] + [dur]
    for s in secs:
        x, sr, spans = v.speak_lines([c.get("dub") or sub(c) for c in s])
        audios.append(x); spans_all.append(spans)
        window = s[-1]["end"] - s[0]["start"]
        factors.append(max(1.0, (len(x) / sr + 0.15) / window))
    new0 = [0.0]
    for i in range(len(secs)):
        new0.append(new0[-1] + (ends[i] - starts[i]) * factors[i])

    events, prev_end = [], 0.0
    total = new0[-1]
    placed = []
    for i, s in enumerate(secs):
        t0 = max(new0[i] + (s[0]["start"] - starts[i]) * factors[i], prev_end)
        placed.append(t0)
        prev_end = t0 + len(audios[i]) / sr + 0.12
        for c, (a, b) in zip(s, spans_all[i]):
            events.append([t0 + a, t0 + b, sub(c)])
    total = max(total, prev_end + 0.3)
    for k in range(len(events) - 1):          # hold each subtitle until the next one (no flicker)
        if events[k + 1][0] - events[k][1] < 0.6:
            events[k][1] = events[k + 1][0]
    mix = np.zeros(int(total * sr) + 1, dtype="float32")
    for t0, x in zip(placed, audios):
        i = int(t0 * sr); mix[i:i + len(x)] += x

    base = os.path.splitext(out)[0]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sf.write(base + ".raw.wav", mix, sr); master(base + ".raw.wav", base + ".dub.wav"); os.remove(base + ".raw.wav")
    with open(base + ".srt", "w", encoding="utf-8") as f:
        for i, (s0, e0, t) in enumerate(events, 1):
            f.write(f"{i}\n{srt_time(s0)} --> {srt_time(e0)}\n{t}\n\n")

    n = len(secs)
    pre = f"drawbox=x=0:y={cover[0]}:w=iw:h={cover[1]}:color=black@1:t=fill," if cover else ""
    fc = f"[0:v]{pre}split={n}" + "".join(f"[s{i}]" for i in range(n)) + ";"
    fc += "".join(f"[s{i}]trim={starts[i]}:{ends[i]},setpts=(PTS-STARTPTS)*{factors[i]:.4f}[v{i}];" for i in range(n))
    post = ""
    if subs:
        write_ass(base + ".ass", w, h, cover, events)
        post = f",ass={base}.ass:fontsdir={FONTS}"
    fc += "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fps=30{post}[v]"
    amap = ["-map", "1:a"]
    if keep_bg > 0:
        fc += ";" + "".join(f"[0:a]atrim={starts[i]}:{ends[i]},asetpts=PTS-STARTPTS,atempo={1 / factors[i]:.4f}[b{i}];" for i in range(n))
        fc += "".join(f"[b{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,volume={keep_bg}[bg];[1:a][bg]amix=inputs=2:normalize=0[a]"
        amap = ["-map", "[a]"]
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", base + ".dub.wav", "-filter_complex", fc,
                           "-map", "[v]", *amap, "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac",
                           "-b:a", "160k", "-shortest", "-movflags", "+faststart", out])
    log(f"section stretch factors: {[round(f, 2) for f in factors]}")
    log(f"wrote {out} ({total:.1f}s from {dur:.1f}s source, voice {voice})")
    return factors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("cues"); ap.add_argument("out")
    ap.add_argument("--cover", help="Y,H band hiding the source's burned-in captions")
    ap.add_argument("--voice", default=DEFAULT_VOICE, help=", ".join(VOICES))
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--keep-bg", type=float, default=0.0)
    ap.add_argument("--no-subs", action="store_true")
    a = ap.parse_args()
    cover = tuple(map(int, a.cover.split(","))) if a.cover else None
    dub(a.src, json.load(open(a.cues, encoding="utf-8")), a.out, cover, a.voice, a.speed, a.keep_bg, not a.no_subs,
        log=lambda m: print(m, file=sys.stderr))


if __name__ == "__main__":
    main()
