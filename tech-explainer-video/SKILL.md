---
name: tech-explainer-video
description: Generate short vertical (9:16) animated tech-explainer videos — dark "engineering terminal" style with a CI/CD-style progress pipeline, terminal/code/checklist/flow/stat scenes, an original robot presenter, and word-by-word captions — in Arabic (RTL) or any language, rendered to MP4 with Playwright + ffmpeg. Also translates existing videos (offline transcription → translation → RTL-safe burned subtitles). Use when the user asks for a Reel/Short/TikTok explaining a programming or DevOps concept, wants "a video like this one", or wants a video translated/subtitled into Arabic. Triggers: "اعمل فيديو يشرح", "فيديو مثل هذا", "ترجم الفيديو", explainer video, reel, shorts, subtitles, CI/CD video.
---

# Tech Explainer Video (فيديوهات شرح تقنية قصيرة)

Two workflows:

- **A. Generate** a new explainer video from a topic → `storyboard.json` → MP4.
- **B. Translate** an existing video → transcript → translation → subtitles burned in (covering the old captions).

Everything runs offline in the container: Chromium (Playwright) renders frames, ffmpeg encodes.
Bundled fonts: Cairo (Arabic + Latin) and JetBrains Mono, under OFL (`assets/fonts/OFL.txt`).

## Ground rules

- **Presenter is always original.** Use the bundled "Forge" robot (`engine/mascot.js`) or design a new
  original character. Never draw, trace or imitate a well-known copyrighted character, even if the
  reference video uses one — match the *layout and pacing*, not the character.
- **Write an original script.** Use a reference video for structure, pacing and visual grammar; don't
  copy its narration line by line into a new video.
- Technical terms stay in English inside Arabic sentences (CI/CD, Docker, GitHub Actions) — that's how
  Arab developers actually talk; add a short Arabic gloss the first time if helpful.

## A. Generate a video

1. **Script.** 30–90 s, hook in the first 3 s (a question or a pain point), one idea per scene,
   end with a one-line recap. Arabic narration runs ~2.3 words/s; English ~2.6 words/s.
2. **Storyboard.** Write `storyboard.json` (full schema: `references/storyboard.md`; working
   examples: `examples/kubernetes-ar.json` (auto-timed, recommended), `examples/docker-ar.json`
   (hand-timed)). **Prefer auto-timing:** give each scene a `say` list of narration lines and
   omit `start`/`end` — scenes are laid end to end and caption cues are timed at a natural
   speaking rate. Add `"sync": "say"` so list items (nodes/items/cards/people) appear exactly
   when the caption that introduces them starts. Pick scene types that *show* the idea:

   | type | use for |
   |---|---|
   | `title` | hook / chapter card |
   | `terminal` | "doing it by hand", commands, errors (typed live) |
   | `checklist` | questions/checks resolving to ✓ / ✕ |
   | `code` | YAML, Dockerfile, config — lines reveal, key lines highlight |
   | `flow` | step-by-step process, active node advances |
   | `compare` | two concepts side by side (CI vs CD, Image vs Container) |
   | `stat` | percentages, rollouts (dot grid + bar, steps like 5→25→50→100) |
   | `cluster` | servers/nodes running instances: scaling, node failure, rescheduling (K8s, load balancing) |
   | `avatars` | people / teams pushing to one branch |
   | `bullets` | recap |
   | `html` | anything custom (raw HTML string, positioned in the content box) |

   The optional top `pipeline` bar is the video's spine: define its steps once, then each scene
   sets `pipeline: {done, current, fail}` so viewers always see where they are.
3. **Validate** — prints the computed timeline and warns about long captions, overlong scenes,
   gaps/overlaps and a slow hook. Fix every warning before rendering:
   ```bash
   node scripts/render.mjs story.json --check
   ```
4. **Preview stills before rendering** (fast, catches layout/RTL problems):
   ```bash
   node scripts/render.mjs story.json out/stills --stills 2,9,15,22 --width 540
   ```
   Pick times from the `--check` output (mid-scene, and right after list items/events fire).
   Look at the PNGs with the Read tool. Fix overlaps / overflowing text / empty space, then render.
5. **Render** (parallel: one Chromium page + encoder per worker, default = CPUs − 1):
   ```bash
   node scripts/render.mjs story.json out/video.mp4                   # 1080x1920, 30 fps
   node scripts/render.mjs story.json out/clip.mp4 --from 10 --to 20  # quick partial check
   ```
   ≈ real time at 1080p with 3 workers. Send the result with SendUserFile.

### Voiceover

There is no TTS in the default container (Hugging Face / Microsoft speech endpoints are blocked).
- If the user supplies narration audio: set `"audio": "voice.mp3"`, run
  `python3 scripts/transcribe.py voice.mp3 segs.json --model small --lang ar`, and set caption
  `start/end` from the segments (split long segments proportionally by text length). Scene
  boundaries should follow the captions.
- If a TTS tool/API is available in the session, generate the audio first, then do the same.
- Otherwise deliver the silent video (captions carry the message) and say so; `"music": {"file": "...", "volume": 0.3}` adds a background track if the user provides one.

## B. Translate an existing video

1. Transcribe (downloads Whisper from GitHub releases on first run, ~640 MB for `small.en`):
   ```bash
   python3 scripts/transcribe.py input.mp4 segs.json --model small.en     # English source
   python3 scripts/transcribe.py input.mp4 segs.json --model small --lang es  # other languages
   ```
2. Fix obvious ASR mistakes using what's on screen (extract frames with
   `ffmpeg -i input.mp4 -vf "fps=1/4,scale=200:-1,tile=8x4" -frames:v 1 sheet.jpg` and read it).
3. Split each segment into caption cues of ≤ ~45 Arabic characters (≤ 2 lines), allocate time
   proportionally to source-text length, and translate each cue. Save as
   `[{"start","end","text","ar"}]`.
4. Find where the source's burned-in captions sit (read a full-resolution frame), then:
   ```bash
   python3 scripts/burn_subs.py input.mp4 cues.json out/input_ar.mp4 --cover 740,92
   ```
   `--cover Y,H` paints an opaque band over the old captions (omit it if the video has none).
   An `.srt` is written next to the MP4 for platforms that take soft subtitles.
5. Spot-check 3–4 frames: Arabic must be joined (not isolated letters), punctuation on the left
   end, Latin terms in the right order.

## Troubleshooting

- **Arabic letters disconnected / wrong order in ffmpeg subtitles** → you're not using
  `burn_subs.py` (it sets ASS `Encoding: -1` for auto RTL and the bundled Cairo font).
- **Playwright not found** → it's installed globally; `render.mjs` falls back to `npm root -g`.
  Never run `playwright install` in the cloud container.
- **Text overflows a card** → shorten copy first; otherwise set a custom `box` on the scene.
- **Presenter covers content** → `presenter: false`, or `"presenter": "left"` / `"right"`.
