---
name: video-subtitles
description: Add accurate, film-style translated subtitles to ANY video while leaving the original video and audio untouched — like movie subtitles. Detects the spoken language, transcribes with per-word timestamps (Parakeet-TDT for English + 24 European languages, Whisper for others), segments by professional subtitle rules, Claude translates with full context, then burns RTL-correct subtitles (Arabic by default) and/or adds a toggleable subtitle track plus .srt. Use when the user asks to subtitle or translate a video "as text only", "ترجمة نصية", "ترجمة مثل الأفلام", "أضف ترجمة عربية للفيديو", "subtitles", "captions", ".srt". Do NOT dub, re-voice, cover or restyle anything unless explicitly asked.
---

# Video Subtitles (ترجمة نصية بأسلوب الأفلام)

The rule of this skill: **add subtitles, change nothing else.** Same picture, same audio (stream
copied byte-for-byte), same length, existing on-screen captions left visible and never covered.

Everything runs offline in the container (sherpa-onnx + ffmpeg); models download once from GitHub
releases. Bundled font: Cairo (Arabic + Latin, OFL).

## Workflow

```bash
S=<this skill>/scripts/subtitle.py
python3 $S prepare input.mp4 work/              # language detect → ASR with word times → timed cues
#   work/cues.json (cues with "src", empty "text"), work/transcript.txt, work/sheet.jpg
#   → YOU translate every cue (see below), writing "text" in work/cues.json
python3 $S check work/                          # length + reading-speed rules; fix every line it lists
python3 $S render work/ out/input_ar.mp4 --mode both
#   out/input_ar.mp4       subtitles burned in (video re-encoded at CRF 17, audio copied)
#   out/input_ar.soft.mp4  original streams + switchable Arabic subtitle track (no re-encode)
#   out/input_ar.srt / .ass
```
Options: `prepare --to en|fr|…` (target language, default `ar`), `--lang en` (skip detection),
`--model parakeet|whisper-medium|whisper-large-v3` (default auto). `render --mode burn|soft|both`,
`--size 1.15` (bigger text), `--position auto|bottom|top`.

## Translating (the part that makes it accurate — do it carefully)

1. Read `work/transcript.txt` **in full first** so every cue is translated with the context of the
   whole video (pronouns, running examples, terminology stay consistent).
2. Fix ASR mistakes using context and `work/sheet.jpg` / on-screen text before translating
   (e.g. "the SSH" → "you SSH", "liner" → "linter", "can't succeed" vs "can succeed": choose what
   makes sense in context; the on-screen captions of the original are a good reference).
3. Translate **meaning, not words**: natural, fluent target language as a professional subtitler
   would write it. Keep technical terms, product names and code in their original form
   (Docker, GitHub Actions, CI/CD, Canary…). Keep numbers and units exact.
4. One cue = one `text`. Never move content between cues — timing comes from the speech.
   If a cue ends mid-sentence, end the translation so the next cue continues naturally (use "،").
5. Length: each cue must fit 2 lines × 42 characters and ≤ 17 characters/second for Arabic
   (≤ 20 for Latin scripts). If `check` flags a cue, condense it (drop fillers, keep meaning).
6. Arabic punctuation: ، ؛ ؟ — and Arabic quotation style. RTL is handled automatically
   (each line gets a right-to-left mark, so lines starting with English terms still align right).

## How accuracy is achieved (don't undo)

- **Per-word timestamps** (Parakeet-TDT v3): cues start/end exactly on the words, not spread across
  a sentence. Whisper fallback works on short VAD chunks (≤ 8 s) to keep timing tight.
- **Segmentation rules:** split at sentence ends, at clauses when long, at pauses > 0.6 s;
  ≤ 84 chars per cue; 1.0–6.5 s; 50 ms lead-in, 250 ms hold; ≥ 2-frame gap between cues.
- **Line breaking:** two balanced lines, preferring breaks after punctuation, top line shorter.
- **Placement:** if the video already has burned-in captions, `prepare` detects their band and
  `render` puts the subtitles in free space below them (or just above if there's no room).
  Check one rendered frame; override with `--position`.
- **Style:** white bold Cairo, black outline + soft shadow, no box — scaled to the frame size.

## Verify before delivering

- Extract 3–4 frames at cue midpoints (`ffmpeg -ss T -i out.mp4 -frames:v 1 f.png`) and look:
  text readable, not covering anything, Arabic letters joined, punctuation on the left end.
- Confirm the audio is untouched:
  `cmp <(ffmpeg -v error -i in.mp4 -map 0:a -c copy -f adts -) <(ffmpeg -v error -i out.mp4 -map 0:a -c copy -f adts -)`.
- Deliver the burned MP4 (plays everywhere) and the `.srt`; mention the soft-track version for
  players/platforms that support switchable subtitles.

Need dubbing, voiceover or generated explainer videos instead? That's the `tech-explainer-video`
skill — only use it when the user explicitly asks for a voice.

## Where deliverables go (user preference)

- Anything not meant to be public — third-party videos, translated/dubbed copies of other people's
  content, personal outputs — goes to the **private** repo `zeiad6/zidex`, branch **`videos`**
  (an orphan branch holding only media; one folder per video, update its README table).
  Push it without cloning the code: `git init -b videos` in a temp dir, add files,
  `git fetch origin videos && git reset --soft origin/videos` (if the branch exists), commit, push.
- Never put such files in public repos (`zeiad6/Skills`, `zeiad6/PromptForge`). Only original,
  shareable demos belong in `Skills/showcase/`.
