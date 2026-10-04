#!/usr/bin/env python3
"""Offline speech-to-text with timestamps (Whisper via sherpa-onnx + Silero VAD).

    python3 transcribe.py <video_or_audio> <out.json> [--model small.en|base.en|small|medium] [--lang en]

Models download from GitHub releases (k2-fsa/sherpa-onnx), which works even where
huggingface.co is blocked. Output: [{"start": s, "end": s, "text": "..."}, ...]
Use a multilingual model (small / medium) with --lang for non-English sources.
"""
import argparse, json, os, subprocess, sys, tarfile, urllib.request, wave

CACHE = os.path.expanduser("~/.cache/tech-explainer-video")
REL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"


def fetch(url, dest):
    if not os.path.exists(dest):
        print("downloading", url, file=sys.stderr)
        urllib.request.urlretrieve(url, dest + ".part")
        os.rename(dest + ".part", dest)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--max-seg", type=float, default=12.0, help="max seconds per segment")
    a = ap.parse_args()

    try:
        import numpy as np, sherpa_onnx
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "sherpa-onnx", "numpy"])
        import numpy as np, sherpa_onnx

    os.makedirs(CACHE, exist_ok=True)
    mdir = os.path.join(CACHE, f"sherpa-onnx-whisper-{a.model}")
    if not os.path.isdir(mdir):
        tb = fetch(REL + f"sherpa-onnx-whisper-{a.model}.tar.bz2", mdir + ".tar.bz2")
        with tarfile.open(tb) as t:
            t.extractall(CACHE)
    vad_path = fetch(REL + "silero_vad.onnx", os.path.join(CACHE, "silero_vad.onnx"))

    wav = os.path.join(CACHE, "_in.wav")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-ac", "1", "-ar", "16000", wav])
    w = wave.open(wav); sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768

    p = lambda s: os.path.join(mdir, f"{a.model}-{s}")
    enc = p("encoder.int8.onnx") if os.path.exists(p("encoder.int8.onnx")) else p("encoder.onnx")
    dec = p("decoder.int8.onnx") if os.path.exists(p("decoder.int8.onnx")) else p("decoder.onnx")
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=enc, decoder=dec, tokens=p("tokens.txt"),
        language="" if a.model.endswith(".en") else a.lang, task="transcribe", num_threads=4)

    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = vad_path
    cfg.silero_vad.min_silence_duration = 0.15
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = a.max_seg
    cfg.sample_rate = sr
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=600)

    segs = []

    def drain():
        while not vad.empty():
            s = vad.front
            st = s.start / sr
            samples = np.array(s.samples, dtype=np.float32)
            stream = rec.create_stream(); stream.accept_waveform(sr, samples); rec.decode_stream(stream)
            text = stream.result.text.strip()
            if text:
                segs.append({"start": round(st, 2), "end": round(st + len(samples) / sr, 2), "text": text})
                print(f"{st:7.2f}  {text}", file=sys.stderr)
            vad.pop()

    win = cfg.silero_vad.window_size
    for i in range(0, len(x), win):
        vad.accept_waveform(x[i:i + win]); drain()
    vad.flush(); drain()

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(segs, f, ensure_ascii=False, indent=1)
    print(f"wrote {len(segs)} segments -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
