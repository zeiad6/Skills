# Storyboard schema

Canvas is designed at 1080×1920; `meta.width` scales the output (height = width × 16/9).
All times are seconds from the start of the video. Scene-local item times (`at`, `resolveAt`,
`highlightAt`) are seconds from the start of that scene.

```jsonc
{
  "meta": {
    "lang": "ar",            // ar | en | ... (rtl auto for ar/fa/ur/he)
    "dir": "rtl",            // optional override
    "fps": 30, "width": 1080,
    "handle": "@you",        // small footer watermark (optional)
    "accent": "#4ade80"      // keyword + mascot accent color
  },
  "audio": "voice.mp3",      // optional narration, relative to this file
  "music": { "file": "bg.mp3", "volume": 0.12 },   // optional, looped
  "duration": 60,            // optional; default = last scene/caption end
  "pipeline": {              // optional persistent progress bar at the top
    "groups": [ { "label": "CI", "steps": ["PUSH","LINT","TEST"] },
                { "label": "CD", "steps": ["IMAGE","STAGING","PROD"] } ]
  },
  "scenes": [ /* contiguous, non-overlapping: scene[i].end == scene[i+1].start */ ],
  "captions": [ { "start": 0.3, "end": 3.2, "text": "...", "keywords": ["CI/CD"] } ]
}
```

## Auto-timing (recommended)

Omit `start`/`end` on scenes and give them narration; `engine/timeline.js` computes everything:

| field | meaning |
|---|---|
| `say` | `["line", {"text": "line", "keywords": ["K8s"], "duration": 2.5}]` — one caption cue per line |
| `sync` | `"say"`: item *i* of `items`/`nodes`/`cards`/`people` appears when cue *i + syncOffset* starts |
| `syncOffset` | skip intro cues before the first list item (e.g. 1 for "four concepts:") |
| `lead` / `tail` | silence before the first / after the last cue (default 0.3 / 0.25 s) |
| `duration` | minimum scene length when it has little or no narration |
| `meta.wps` | words per second (default 2.3 Arabic, 2.6 others); `meta.gap` silence between cues (0.12) |

Explicit `start`/`end` and top-level `captions` still work and can be mixed in.

## Common scene fields

| field | meaning |
|---|---|
| `start`, `end`, `type` | required |
| `presenter` | `true` (side by text direction), `"left"`, `"right"`, or omitted |
| `wave` | mascot waves during the first 1.6 s |
| `pipeline` | `{ "done": 3, "current": true, "fail": -1 }` — index of last done step; `current` pulses the next; `fail` paints a step red. Omit to hide the bar in this scene |
| `eyebrow` | small uppercase label above the content |
| `top` | y of the content box (default 400) |
| `box` | `{x,y,w,h}` full override of the content box |

## Scene types

- **title** — `eyebrow`, `title`, `subtitle`, `size` (title px, default 92)
- **terminal** — `title` (window title), `server: {name, sub, live}`, `lines: []`
  (lines starting with `$` are typed; others print at once; error/ok words auto-colored), `cps`
- **checklist** — `heading`, `items: [{icon, title, sub, status: "ok"|"fail", at, resolveAt}]`
- **code** — `file`, `code` (string with `\n`), `highlight: [lineNumbers]`, `highlightAt`, `lps` (lines/s), `reveal: false`
- **flow** — `nodes: [{title, sub, icon}]`, `gap`; the active node advances evenly across the scene
- **compare** — `cards: [{title, text, sub, color, at}]`
- **stat** — `values: [5, 25, 50, 100]` (stepped) or `value`, `unit` (default `%`), `label`, `grid` (N×N dots), `leftLabel`, `rightLabel`
- **cluster** — `nodes: [{name}]`, `replicas`, `app` (pod label), `instant` (pods present at scene start),
  `events: [{at, action: "scale", replicas} | {at, action: "kill", node} | {at, action: "revive", node}]`,
  `controlPlane: false`, `controlPlaneSub`, `service` (adds a load-balancer bar), `desiredLabel`,
  `podSize`, `nodeHeight`. Rescheduled/new pods show amber "pending" for 0.8 s, then green
- **avatars** — `people: [{name, letter, color, note}]`, `branch`
- **bullets** — `heading`, `items: ["text" | {text, at}]`
- **html** — `html`: raw markup placed in the content box (trusted input only)

## Captions

One cue on screen at a time, ≤ ~45 Arabic chars (2 lines max at 56 px). Words light up
progressively over 85 % of the cue; words listed in `keywords` (matched without punctuation)
use the accent color. The mascot's mouth animates while a cue is active.

## Pacing cheatsheet

- Hook ≤ 3 s; scene length 4–8 s; a visual change at least every ~3 s.
- Narration ≈ 2.3 words/s (Arabic), 2.6 words/s (English).
- End with a recap scene (`compare` or `bullets`) that answers the hook question.
