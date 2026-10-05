---
name: tech-explainer-video
description: Generate short vertical (9:16) animated tech-explainer videos — dark "engineering terminal" style with a CI/CD-style progress pipeline, terminal/code/checklist/flow/stat scenes, original presenters (Nova with a female voice, Forge with a male voice), offline neural Arabic voiceover with lip-sync, and word-by-word captions — rendered to MP4 with Playwright + ffmpeg. Also localizes ANY existing video from any language: auto language detection, transcription, translation, natural Arabic dubbing (female/male voice) and RTL-safe subtitles. Use when the user asks for a Reel/Short/TikTok explaining a programming or DevOps concept, wants "a video like this one", or wants a video translated/subtitled into Arabic. Triggers: "اعمل فيديو يشرح", "فيديو مثل هذا", "ترجم الفيديو", "دبلج", "دبلجة", "تعليق صوتي", explainer video, reel, shorts, subtitles, CI/CD video.
---

# Tech Explainer Video (فيديوهات شرح تقنية قصيرة)

Workflows:

- **A. Generate** a new explainer video from a topic → `storyboard.json` → MP4.
- **B. Translate** an existing video → transcript → translation → subtitles burned in (covering the old captions),
  optionally **dubbed** with an Arabic voice.

Everything runs offline in the container: Chromium (Playwright) renders frames, ffmpeg encodes, sherpa-onnx does speech-to-text and text-to-speech.
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

   **Background** (`meta.background`, or per scene `background`): animated, low-contrast layers
   that make the video distinctive without hurting readability. A name or an array layered
   bottom→top: `aurora` (drifting colour glows), `network` (nodes + links with data pulses —
   cloud/infra), `grid` (perspective floor rushing forward — speed/pipelines), `code` (falling code
   glyphs — programming), `stars` (particles), `plain`. Good pairs: `["aurora","network"]` for
   infra, `["aurora","code"]` for programming, `["aurora","grid"]` for CI/CD. Colours follow
   `meta.accent` (override `meta.bgAccent`; aurora colours via `meta.bgOptions.colors`, strength
   via `meta.bgOptions.glow`). Cards are translucent so the background shows through.

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

### Voiceover (offline neural voices, lip-synced)

```bash
python3 scripts/tts.py story.json --voice ar-female      # → story.voiced.json + voice/sceneNN.wav
node scripts/render.mjs story.voiced.json out/video.mp4
```
| voice | model | notes |
|---|---|---|
| `ar-female` (default) | Piper `ar_JO-SA_dii-high` | natural female, high quality — **CC BY-NC-SA 4.0: non-commercial only** |
| `ar-male` | Piper `ar_JO-SA_miro_V2-high` | male, high quality — CC BY-NC-SA 4.0 |
| `ar-male-classic` | Piper `ar_JO-kareem-medium` | male, more permissive licence, flatter |
| `en-female` / `en-female-hq` / `en-male` | Piper `en_US-amy` / `en_US-lessac` / `en_US-ryan` | English |

**Fish Audio (cloud, any voice the user picks on fish.audio):** `--voice fish:<modelId>[:female|male]`
(the id is the `modelId=` in the fish.audio URL). Needs `FISH_API_KEY` set as an environment variable
in the environment settings (never in chat, files or commits) and `api.fish.audio` allowed in the
environment's network access. Optional `FISH_MODEL` (default `s1`). Works for both `tts.py` and
`localize.py finish --voice fish:<id>`. Only use voices the user owns or has rights/consent for.

Tell the user about the non-commercial licence when they plan to monetise; offer `ar-male-classic`.
How it stays smooth (don't undo this): caption fragments are joined into **sentences** before
synthesis (a line ending in a comma continues into the next), Arabic is **auto-diacritized**
(tashkeel) because these voices were trained on diacritized text, silence is trimmed with 12 ms
fades, pauses are uniform (0.32 s between sentences), and the track is compressed and normalised to
-16 LUFS. Each scene is one continuous clip; caption timings are derived from it.

- `meta.presenter` is set automatically: **`nova`** (original female engineer robot: headset,
  glowing visor, light-trail ponytail) for female voices, **`forge`** (hard-hat robot) for male.
  Override with `"presenter": "forge"|"nova"`, colour via `meta.presenterAccent`.
- **Listen-back QA (on by default):** every sentence is transcribed back with Whisper; if words are
  dropped, repeated or slurred it is re-synthesized (up to 3 tries) and the best take is kept.
  Sentences still scoring < 0.75 are printed — rephrase them (shorter, simpler words). `--no-qa`
  skips it. Voice noise is lowered (0.45/0.6) for steadier delivery; avoid `--speed` above ~1.1,
  shorten text instead.
- **Tech terms stay recognisable:** the sentence is never split to insert English audio (that would
  sound choppy). Instead each term uses the Arabic spelling that an English recognizer hears as the
  original word (`SPOKEN_AR`). For a new term, find the best spelling with
  `python3 scripts/tts.py x.json --tune-terms '{"Terraform": ["تيرافورم", "تيرَفورْم"]}'` and add it.
  Subtitles always keep the English term.
- The presenter's mouth follows the real voice loudness (render.mjs passes an envelope).
- English tech terms are transliterated for speech only (`SPOKEN_AR` in `tts.py`; per-video
  `meta.spoken: {"Helm": "هِلم"}`, or `"speak"` on a line). Add every new Latin term the script uses.
- Narration speed: `--speed 1.1` for snappier shorts. User-supplied narration instead: set
  `"audio": "voice.mp3"` and time captions from `scripts/transcribe.py`.

## B. Localize / dub ANY video (any source language)

```bash
python3 scripts/localize.py prepare input.mp4 work/            # detect language, transcribe, find caption band
#   → work/job.json (cues with "src", empty "text"/"dub"), work/sheet.jpg, work/band.jpg
#   YOU (Claude) now translate: fill "text" and "dub" for every cue in work/job.json
python3 scripts/localize.py finish work/ out/input_ar.mp4 --speed 1.15   # dub + subtitles
python3 scripts/localize.py finish work/ out/input_ar_subs.mp4 --mode subs # subtitles only, original audio
```
Translating well is the part that makes this smart — do it yourself, carefully:
1. Read `work/sheet.jpg` (and frames at specific times if needed) to understand the visuals and
   fix ASR mistakes using on-screen text (e.g. "linner" → linter).
2. `text` = the subtitle, `dub` = what is spoken. For Arabic dubbing write `dub` **condensed**
   (~35–40% shorter than a literal translation, same meaning) and set `text` = `dub` so viewers read
   what they hear. Keep tech terms in English.
3. Cues inside one speech segment are one breath group: keep the sentence flowing across them
   (end mid-sentence cues with "،"), so the voice is synthesized as one continuous sentence.
4. Open `work/band.jpg`: the red box must cover the original burned-in captions. Adjust `"cover"`
   `[y, height]` in job.json if needed, or set it to `null` when there are none.
5. `finish` prints per-section stretch factors. If any is > 1.2, shorten those `dub` lines and run
   `finish` again — aim for the dubbed video to be within ~5% of the original length.

Notes: the source audio is replaced (speech and music can't be separated in a mixed track; keeping
it leaves the original voice audible). `--voice ar-male` for a male dub. The presenter in someone
else's video can't be swapped — only generated videos use Nova/Forge. `transcribe.py` and
`burn_subs.py` remain available as standalone steps.

## Troubleshooting

- **Arabic letters disconnected / wrong order in ffmpeg subtitles** → you're not using
  `burn_subs.py` (it sets ASS `Encoding: -1` for auto RTL and the bundled Cairo font).
- **Playwright not found** → it's installed globally; `render.mjs` falls back to `npm root -g`.
  Never run `playwright install` in the cloud container.
- **Text overflows a card** → shorten copy first; otherwise set a custom `box` on the scene.
- **Presenter covers content** → `presenter: false`, or `"presenter": "left"` / `"right"`.

## Where deliverables go (user preference)

- Anything not meant to be public — third-party videos, translated/dubbed copies of other people's
  content, personal outputs — goes to the **private** repo `zeiad6/zidex`, branch **`videos`**
  (an orphan branch holding only media; one folder per video, update its README table).
  Push it without cloning the code: `git init -b videos` in a temp dir, add files,
  `git fetch origin videos && git reset --soft origin/videos` (if the branch exists), commit, push.
- Never put such files in public repos (`zeiad6/Skills`, `zeiad6/PromptForge`). Only original,
  shareable demos belong in `Skills/showcase/`.
