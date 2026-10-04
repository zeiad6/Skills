#!/usr/bin/env python3
"""Burn translated subtitles into an existing video (RTL-safe), optionally hiding the original captions.

    python3 burn_subs.py <in.mp4> <cues.json> <out.mp4> [--cover Y,H] [--margin-v PX] [--size PX]

cues.json: [{"start": s, "end": s, "text": "..."}]  (also accepts "ar"/"translation" keys)
--cover Y,H   paint an opaque band over the source's burned-in captions (pixel rows, source scale)
Also writes <out>.srt next to the video. Uses the bundled Cairo font, so Arabic shapes correctly,
and ASS Encoding -1 so libass auto-detects RTL base direction.
"""
import argparse, json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "assets", "fonts")


def ass_time(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("cues"); ap.add_argument("out")
    ap.add_argument("--cover", help="Y,H band to blank out (e.g. 740,92)")
    ap.add_argument("--margin-v", type=int, help="distance of subtitle baseline from bottom (px)")
    ap.add_argument("--size", type=int, help="font size in px (default: 3.1%% of height)")
    a = ap.parse_args()

    w, h = map(int, subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0:s=x", a.src]).decode().strip().split("x"))
    cues = json.load(open(a.cues, encoding="utf-8"))
    text = lambda c: (c.get("ar") or c.get("translation") or c["text"]).replace("\n", "\\N")

    size = a.size or round(h * 0.031)
    if a.margin_v is not None:
        mv = a.margin_v
    elif a.cover:
        y, bh = map(int, a.cover.split(","))
        mv = h - (y + bh // 2) - size // 2
    else:
        mv = round(h * 0.12)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    base = os.path.splitext(a.out)[0]
    ass = base + ".ass"
    with open(ass, "w", encoding="utf-8") as f:
        f.write(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: S,Cairo,{size},&H00FFFFFF,&H00FFFFFF,&H001A1715,&H001A1715,-1,0,0,0,100,100,0,0,3,{max(4, size // 3)},0,2,{w // 14},{w // 14},{mv},-1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
        for c in cues:
            f.write(f"Dialogue: 0,{ass_time(c['start'])},{ass_time(c['end'])},S,,0,0,0,,{text(c)}\n")
    with open(base + ".srt", "w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            f.write(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{text(c).replace(chr(92) + 'N', chr(10))}\n\n")

    vf = []
    if a.cover:
        y, bh = map(int, a.cover.split(","))
        vf.append(f"drawbox=x=0:y={y}:w=iw:h={bh}:color=black@1:t=fill")
    vf.append(f"ass={ass}:fontsdir={FONTS}")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-vf", ",".join(vf),
                           "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "copy",
                           "-movflags", "+faststart", a.out])
    print("wrote", a.out, "and", base + ".srt")


if __name__ == "__main__":
    main()
