#!/usr/bin/env python3
"""Dub an existing video into Arabic (or any Piper voice) with subtitles synced to the new voice.

    python3 dub_video.py <in.mp4> <cues.json> <out.mp4> [--cover 740,92] [--speed 1.35] [--voice NAME] [--keep-bg 0]

cues.json: [{"start", "end", "text", "dub"?}] in source time. `text` is burned as the subtitle; `dub`
(optional) is a *condensed* line to speak instead — Arabic runs ~1.5-1.8x longer than English, so write
dub lines ~35% shorter than the full translation, and use the same text for the subtitle if you want
viewers to read exactly what they hear.

How timing works: consecutive cues with no gap form a section (one breath group of the original
speaker). Each section of video is slowed just enough for its dubbed speech to fit (factor >= 1), so
voice, subtitles and on-screen animation stay in sync. The script prints the per-section factors;
if many are > 1.15, shorten the dub lines rather than accepting a sluggish video.

--keep-bg V mixes the original audio under the dub at volume V (only sensible when the source has
no speech in it, e.g. you separated music beforehand). Default 0 = voice only.
"""
import argparse, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts import Voice, DEFAULT_VOICE  # noqa: E402
from burn_subs import ass_time, FONTS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("cues"); ap.add_argument("out")
    ap.add_argument("--cover", help="Y,H band hiding the source's burned-in captions")
    ap.add_argument("--speed", type=float, default=1.35)
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--gap", type=float, default=0.10)
    ap.add_argument("--keep-bg", type=float, default=0.0)
    a = ap.parse_args()
    import numpy as np, soundfile as sf

    cues = json.load(open(a.cues, encoding="utf-8"))
    sub = lambda c: c.get("ar") or c.get("translation") or c["text"]
    w, h = map(int, subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height", "-of", "csv=p=0:s=x", a.src]).decode().split("x"))
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.src]))

    # sections = runs of contiguous cues
    secs = [[cues[0]]]
    for p, c in zip(cues, cues[1:]):
        (secs[-1].append(c) if c["start"] - p["end"] < 0.05 else secs.append([c]))

    v = Voice(a.voice, a.speed)
    sr, clips = None, []
    for c in cues:
        x, sr = v.say(c.get("dub") or sub(c)); clips.append(x)
    k = 0
    starts = [0.0] + [s[0]["start"] for s in secs[1:]]
    ends = starts[1:] + [dur]
    factors = []
    for s in secs:
        need = sum(len(clips[k + i]) / sr + a.gap for i in range(len(s)))
        factors.append(max(1.0, need / (s[-1]["end"] - s[0]["start"]))); k += len(s)
    new0 = [0.0]
    for i in range(len(secs)):
        new0.append(new0[-1] + (ends[i] - starts[i]) * factors[i])

    placed, prev, k = [], 0.0, 0
    for i, s in enumerate(secs):
        for c in s:
            t = max(new0[i + 0] + (c["start"] - starts[i]) * factors[i], prev)
            placed.append((t, t + len(clips[k]) / sr)); prev = placed[-1][1] + a.gap; k += 1
    total = max(new0[-1], prev + 0.3)
    mix = np.zeros(int(total * sr) + 1, dtype="float32")
    for (t, _), x in zip(placed, clips):
        i = int(t * sr); mix[i:i + len(x)] += x
    mix = mix / max(1e-6, float(np.abs(mix).max())) * 0.89
    base = os.path.splitext(a.out)[0]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sf.write(base + ".dub.wav", mix, sr)

    size = round(h * 0.031)
    mv = h - (int(a.cover.split(",")[0]) + int(a.cover.split(",")[1]) // 2) - size // 2 if a.cover else round(h * 0.12)
    with open(base + ".ass", "w", encoding="utf-8") as f:
        f.write(f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\n\n[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                f"Style: S,Cairo,{size},&H00FFFFFF,&H00FFFFFF,&H001A1715,&H001A1715,-1,0,0,0,100,100,0,0,3,{max(4, size // 3)},0,2,{w // 14},{w // 14},{mv},-1\n\n"
                "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for i, ((s0, e0), c) in enumerate(zip(placed, cues)):
            nxt = placed[i + 1][0] if i + 1 < len(placed) else e0 + 0.6
            f.write(f"Dialogue: 0,{ass_time(s0)},{ass_time(min(nxt, e0 + 0.5))},S,,0,0,0,,{sub(c)}\n")

    n = len(secs)
    pre = f"drawbox=x=0:y={a.cover.split(',')[0]}:w=iw:h={a.cover.split(',')[1]}:color=black@1:t=fill," if a.cover else ""
    fc = f"[0:v]{pre}split={n}" + "".join(f"[s{i}]" for i in range(n)) + ";"
    fc += "".join(f"[s{i}]trim={starts[i]}:{ends[i]},setpts=(PTS-STARTPTS)*{factors[i]:.4f}[v{i}];" for i in range(n))
    fc += "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fps=30,ass={base}.ass:fontsdir={FONTS}[v]"
    amap = ["-map", "1:a"]
    if a.keep_bg > 0:
        fc += ";" + "".join(f"[0:a]atrim={starts[i]}:{ends[i]},asetpts=PTS-STARTPTS,atempo={1 / factors[i]:.4f}[b{i}];" for i in range(n))
        fc += "".join(f"[b{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,volume={a.keep_bg}[bg];[1:a][bg]amix=inputs=2:normalize=0[a]"
        amap = ["-map", "[a]"]
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-i", base + ".dub.wav", "-filter_complex", fc,
                           "-map", "[v]", *amap, "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac",
                           "-b:a", "160k", "-shortest", "-movflags", "+faststart", a.out])
    print("section stretch factors:", [round(f, 2) for f in factors], file=sys.stderr)
    print(f"wrote {a.out} ({total:.1f}s from {dur:.1f}s source)", file=sys.stderr)


if __name__ == "__main__":
    main()
