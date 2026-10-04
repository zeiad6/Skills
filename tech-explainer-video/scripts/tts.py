#!/usr/bin/env python3
"""Offline neural text-to-speech (Piper voices via sherpa-onnx, models from GitHub releases).

Voices (see VOICES): ar-female (default, "dii"), ar-male ("miro"), ar-male-classic ("kareem"),
en-female, en-male. Arabic text is auto-diacritized (piper's tashkeel model) — the high-quality
Arabic voices were trained on diacritized text and sound robotic without it.

Speech is synthesized per *sentence*, not per caption fragment: fragments that end in a comma
are joined with the next one so intonation flows, and caption timings are then derived from the
continuous audio. Silence is trimmed, pauses are uniform (comma / sentence), and the final mix is
compressed and loudness-normalized.

Library:
    v = Voice("ar-female"); audio, sr, spans = v.speak_lines(["سطر أول،", "سطر ثانٍ."])
CLI — voice a storyboard (one clip per scene; caption durations written back):
    python3 tts.py story.json [--voice ar-female] [--speed 1.0]
    → story.voiced.json + voice/sceneNN.wav   (then: node render.mjs story.voiced.json out.mp4)
"""
import argparse, json, os, re, subprocess, sys, tarfile, urllib.request

CACHE = os.path.expanduser("~/.cache/tech-explainer-video")
REL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"

# name -> (sherpa-onnx model id, gender, license note)
VOICES = {
    "ar-female":       ("vits-piper-ar_JO-SA_dii-high", "female", "CC BY-NC-SA 4.0 (non-commercial)"),
    "ar-male":         ("vits-piper-ar_JO-SA_miro_V2-high", "male", "CC BY-NC-SA 4.0 (non-commercial)"),
    "ar-male-classic": ("vits-piper-ar_JO-kareem-medium", "male", "see model card"),
    "en-female":       ("vits-piper-en_US-amy-medium", "female", "see model card"),
    "en-female-hq":    ("vits-piper-en_US-lessac-high", "female", "see model card"),
    "en-male":         ("vits-piper-en_US-ryan-high", "male", "see model card"),
}
DEFAULT_VOICE = "ar-female"
PAUSE = {",": 0.16, ".": 0.32}     # seconds of silence after a clause / sentence

# Spoken forms for Latin tech terms inside Arabic (speech only — captions keep the original).
SPOKEN_AR = {
    "CI/CD": "سي آي سي دي", "CICD": "سي آي سي دي", "CI": "سي آي", "CD": "سي دي",
    "Kubernetes": "كوبرنيتِس", "K8s": "كيه إيتس", "Docker Hub": "دوكر هَب", "Dockerfile": "دوكر فايل",
    "Docker": "دوكر", "GitHub Actions": "جِت هَب أكشنز", "GitHub": "جِت هَب", "Git": "جِت", "YAML": "يامل",
    "API": "إيه بي آي", "Pods": "بودز", "Pod": "بود", "Deployment": "ديبلويمنت", "Service": "سيرفس",
    "Node": "نود", "Cluster": "كلاستر", "Control Plane": "كنترول بلين", "Image": "إيميج",
    "Container": "كونتينر", "SSH": "إس إس إتش", "Staging": "ستيجنج", "Rolling": "رولينج",
    "Blue-Green": "بلو جرين", "Canary": "كناري", "linter": "لينتر", "push": "بوش", "Python": "بايثون",
    "Linux": "لينكس", "AWS": "إيه دبليو إس", "React": "رياكت", "JavaScript": "جافاسكربت", "SQL": "سيكوال",
}
AR_DIGITS = {0: "صفر", 1: "واحد", 2: "اثنان", 3: "ثلاثة", 4: "أربعة", 5: "خمسة", 6: "ستة", 7: "سبعة", 8: "ثمانية",
             9: "تسعة", 10: "عشرة", 20: "عشرين", 25: "خمسة وعشرين", 50: "خمسين", 100: "مئة", 1000: "ألف"}


def _ensure_deps():
    try:
        import sherpa_onnx, soundfile, numpy  # noqa
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "sherpa-onnx", "numpy", "soundfile"])


def speakable_ar(text, extra=None):
    m = {**SPOKEN_AR, **(extra or {})}
    for k in sorted(m, key=len, reverse=True):
        text = re.sub(rf"(?<![A-Za-z]){re.escape(k)}(?![A-Za-z])", m[k], text)
    text = re.sub(r"(\d+)\s*%", lambda g: f"{AR_DIGITS.get(int(g[1]), g[1])} بالمئة", text)
    text = re.sub(r"\b(\d+)\b", lambda g: AR_DIGITS.get(int(g[1]), g[1]), text)
    text = text.replace("‏", "").replace("…", "،").replace("—", "،")
    return re.sub(r"[()\"«»:]", " ", text).strip()


def sentences(lines):
    """Group caption lines into sentences: a line ending in . ? ! ؟ closes a group."""
    groups, cur = [], []
    for i, ln in enumerate(lines):
        cur.append(i)
        if re.search(r"[.!?؟]\s*$", ln.strip()) or i == len(lines) - 1:
            groups.append(cur); cur = []
    return groups


class Voice:
    def __init__(self, name=DEFAULT_VOICE, speed=1.0, threads=4):
        _ensure_deps()
        import sherpa_onnx
        model_id = VOICES.get(name, (name,))[0]
        self.name, self.gender = name, VOICES.get(name, (None, "male"))[1]
        d = os.path.join(CACHE, model_id)
        if not os.path.isdir(d):
            os.makedirs(CACHE, exist_ok=True)
            tb = d + ".tar.bz2"
            print("downloading voice", model_id, file=sys.stderr)
            urllib.request.urlretrieve(REL + model_id + ".tar.bz2", tb)
            with tarfile.open(tb) as t:
                t.extractall(CACHE)
            os.remove(tb)
        onnx = next(f for f in os.listdir(d) if f.endswith(".onnx"))
        cfgj = json.load(open(os.path.join(d, onnx + ".json"), encoding="utf-8"))
        self.arabic = cfgj.get("language", {}).get("code", "").startswith("ar") or "-ar_" in model_id
        self.diacritize = None
        if self.arabic and cfgj.get("inference", {}).get("add_diacritics"):
            try:
                from piper.tashkeel import TashkeelDiacritizer
            except ImportError:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "piper-tts"])
                from piper.tashkeel import TashkeelDiacritizer
            self.diacritize = TashkeelDiacritizer()
        cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=os.path.join(d, onnx), tokens=os.path.join(d, "tokens.txt"),
                data_dir=os.path.join(d, "espeak-ng-data"), noise_scale=0.6, noise_scale_w=0.7),
            num_threads=threads))
        self.tts, self.speed = sherpa_onnx.OfflineTts(cfg), speed
        self.sr = self.tts.sample_rate

    def prepare(self, text, extra=None):
        if not self.arabic:
            return text
        t = speakable_ar(text, extra)
        return self.diacritize.diacritize(t) if self.diacritize else t

    def _synth(self, text, extra=None):
        import numpy as np
        a = self.tts.generate(self.prepare(text, extra), sid=0, speed=self.speed)
        return trim(np.array(a.samples, dtype="float32"), self.sr)

    def say(self, text, extra=None):
        return self._synth(text, extra), self.sr

    def speak_lines(self, lines, extra=None, gap_scale=1.0):
        """Continuous narration for caption lines. Returns (audio, sr, [(start, end) per line])."""
        import numpy as np
        out, spans, t = [], [None] * len(lines), 0.0
        groups = sentences(lines)
        for gi, g in enumerate(groups):
            x = self._synth(" ".join(lines[i].strip() for i in g), extra)
            dur = len(x) / self.sr
            # split the sentence's audio among its lines by (spoken) length
            w = [max(1, len(self.prepare(lines[i], extra))) for i in g]
            acc = 0.0
            for i, wi in zip(g, w):
                spans[i] = (t + dur * acc / sum(w), t + dur * (acc + wi) / sum(w)); acc += wi
            out.append(x); t += dur
            if gi < len(groups) - 1:
                p = PAUSE["."] * gap_scale
                out.append(np.zeros(int(p * self.sr), dtype="float32")); t += p
        return (np.concatenate(out) if out else np.zeros(1, "float32")), self.sr, spans


def trim(x, sr, thr=0.01, pad=0.03):
    import numpy as np
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx):
        return x
    a, b = max(0, idx[0] - int(pad * sr)), min(len(x), idx[-1] + int(pad * sr))
    y = x[a:b].copy()
    f = min(len(y) // 2, int(0.012 * sr))       # 12 ms fades: no clicks at joins
    if f > 0:
        y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
    return y


# Gentle voice chain for the final mix: rumble cut, de-harsh, compression, broadcast loudness.
MASTER = "highpass=f=70,equalizer=f=4500:t=q:w=1.5:g=-2,acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2,loudnorm=I=-16:TP=-1.5:LRA=7"


def master(in_wav, out_wav):
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", in_wav, "-af", MASTER, "-ar", "48000", out_wav])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--voice", default=DEFAULT_VOICE, help=", ".join(VOICES))
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--out-dir", default="voice")
    a = ap.parse_args()
    import soundfile as sf
    sb = json.load(open(a.storyboard, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(a.storyboard))
    os.makedirs(os.path.join(base, a.out_dir), exist_ok=True)
    v = Voice(a.voice, a.speed)
    meta = sb.setdefault("meta", {})
    extra = meta.get("spoken", {})
    meta["gap"] = 0                      # pauses now live inside the audio
    meta.setdefault("presenter", "nova" if v.gender == "female" else "forge")
    meta.setdefault("voice", a.voice)
    for si, s in enumerate(sb["scenes"]):
        say = [{"text": l} if isinstance(l, str) else l for l in s.get("say", [])]
        if not say:
            continue
        x, sr, spans = v.speak_lines([c.get("speak") or c["text"] for c in say], extra)
        raw = os.path.join(base, a.out_dir, f"scene{si:02d}.raw.wav")
        rel = f"{a.out_dir}/scene{si:02d}.wav"
        sf.write(raw, x, sr); master(raw, os.path.join(base, rel)); os.remove(raw)
        # caption i lasts until caption i+1 starts, so the cues tile the clip exactly
        for i, c in enumerate(say):
            nxt = spans[i + 1][0] if i + 1 < len(say) else len(x) / sr
            c["duration"] = round(nxt - spans[i][0], 3)
        say[0]["audio"] = rel
        s["say"] = say
    out = os.path.splitext(a.storyboard)[0] + ".voiced.json"
    json.dump(sb, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"voiced {len(sb['scenes'])} scenes with {a.voice} ({VOICES.get(a.voice, ('', '', ''))[2]}) -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
