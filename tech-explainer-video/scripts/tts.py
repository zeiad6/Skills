#!/usr/bin/env python3
"""Offline text-to-speech (Piper voices via sherpa-onnx; models from GitHub releases).

Library:  from tts import Voice;  v = Voice(); samples, sr = v.say("مرحبا")
CLI — voice a storyboard (one clip per `say` line; durations written back so timing follows speech):
    python3 tts.py story.json [--voice vits-piper-ar_JO-kareem-medium] [--speed 1.15]
    → story.voiced.json + voice/NNN.wav   (then: node render.mjs story.voiced.json out.mp4)

Latin tech terms inside Arabic are transliterated *for speech only* (captions keep the original),
because Arabic voices otherwise mangle words like "Docker" or "GitHub".
"""
import argparse, json, os, re, subprocess, sys, tarfile, urllib.request

CACHE = os.path.expanduser("~/.cache/tech-explainer-video")
REL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
DEFAULT_VOICE = "vits-piper-ar_JO-kareem-medium"

# Spoken forms for common terms (longest keys first when applied). Extend per video.
SPOKEN_AR = {
    "CI/CD": "سي آي سي دي", "CICD": "سي آي سي دي", "CI": "سي آي", "CD": "سي دي",
    "Kubernetes": "كوبرنيتِس", "K8s": "كيه إيتس", "Docker": "دوكر", "Dockerfile": "دوكر فايل",
    "GitHub Actions": "جِت هَب أكشنز", "GitHub": "جِت هَب", "Git": "جِت", "YAML": "يامل", "API": "إيه بي آي",
    "Pod": "بود", "Pods": "بودز", "Deployment": "ديبلويمنت", "Service": "سيرفس", "Node": "نود",
    "Cluster": "كلاستر", "Control Plane": "كنترول بلين", "Image": "إيميج", "Container": "كونتينر",
    "SSH": "إس إس إتش", "Staging": "ستيجنج", "Rolling": "رولينج", "Blue-Green": "بلو جرين",
    "Canary": "كناري", "linter": "لينتر", "push": "بوش", "Python": "بايثون", "Docker Hub": "دوكر هَب",
}


def speakable(text, extra=None):
    m = {**SPOKEN_AR, **(extra or {})}
    for k in sorted(m, key=len, reverse=True):
        text = re.sub(rf"(?<![A-Za-z]){re.escape(k)}(?![A-Za-z])", m[k], text)
    text = re.sub(r"(\d+)\s*%", r"\1 بالمئة", text)
    return text.replace("‏", "").replace("…", "،").replace("(", "").replace(")", "")


class Voice:
    def __init__(self, name=DEFAULT_VOICE, speed=1.0, threads=4):
        try:
            import sherpa_onnx  # noqa
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "sherpa-onnx", "numpy", "soundfile"])
        import sherpa_onnx
        os.makedirs(CACHE, exist_ok=True)
        d = os.path.join(CACHE, name)
        if not os.path.isdir(d):
            tb = d + ".tar.bz2"
            print("downloading voice", name, file=sys.stderr)
            urllib.request.urlretrieve(REL + name + ".tar.bz2", tb)
            with tarfile.open(tb) as t:
                t.extractall(CACHE)
            os.remove(tb)
        model = next(f for f in os.listdir(d) if f.endswith(".onnx"))
        cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=os.path.join(d, model), tokens=os.path.join(d, "tokens.txt"),
                                                       data_dir=os.path.join(d, "espeak-ng-data")),
            num_threads=threads))
        self.tts, self.speed, self.arabic = sherpa_onnx.OfflineTts(cfg), speed, "-ar_" in name

    def say(self, text, extra=None):
        import numpy as np
        a = self.tts.generate(speakable(text, extra) if self.arabic else text, sid=0, speed=self.speed)
        return np.array(a.samples, dtype="float32"), a.sample_rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--speed", type=float, default=1.15)
    ap.add_argument("--out-dir", default="voice")
    a = ap.parse_args()
    import soundfile as sf
    sb = json.load(open(a.storyboard, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(a.storyboard))
    os.makedirs(os.path.join(base, a.out_dir), exist_ok=True)
    v = Voice(a.voice, a.speed)
    extra = sb.get("meta", {}).get("spoken", {})  # per-video pronunciation overrides
    n = 0
    for s in sb["scenes"]:
        for i, line in enumerate(s.get("say", [])):
            c = {"text": line} if isinstance(line, str) else line
            x, sr = v.say(c.get("speak") or c["text"], extra)
            rel = f"{a.out_dir}/{n:03d}.wav"
            sf.write(os.path.join(base, rel), x, sr)
            c["audio"], c["duration"] = rel, round(len(x) / sr + 0.05, 2)
            s["say"][i] = c
            n += 1
    out = os.path.splitext(a.storyboard)[0] + ".voiced.json"
    json.dump(sb, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"voiced {n} lines -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
