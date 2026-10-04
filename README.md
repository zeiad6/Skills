# Skills

Claude skills by @zeiad6. Each folder is a self-contained skill (`SKILL.md` + scripts/assets).

| skill | what it does |
|---|---|
| [`tech-explainer-video`](tech-explainer-video/SKILL.md) | Generates vertical (9:16) animated tech-explainer videos in Arabic (RTL) or any language from a storyboard JSON — terminal/code/flow/cluster scenes, original robot presenter, word-by-word captions — translates existing videos with RTL-safe burned subtitles, and localizes any video with natural Arabic dubbing (female or male voice). |

## Install

Copy a skill folder into one of:

- `~/.claude/skills/` — available in every project
- `<project>/.claude/skills/` — available in that project only

```bash
git clone https://github.com/zeiad6/Skills
cp -r Skills/tech-explainer-video ~/.claude/skills/
```

`tech-explainer-video` needs Node 18+ with Playwright (Chromium), ffmpeg (with libass), and Python 3.

## Showcase

- [`showcase/kubernetes-ar.mp4`](showcase/kubernetes-ar.mp4) — "ما هو Kubernetes؟", 76 s, generated end-to-end from
  [`examples/kubernetes-ar.json`](tech-explainer-video/examples/kubernetes-ar.json) with offline Arabic voiceover (female voice, Nova presenter).
