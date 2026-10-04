#!/usr/bin/env node
// Render a storyboard JSON to MP4: headless Chromium captures every frame of engine/player.html,
// frames are piped into ffmpeg, and the optional voiceover / music is muxed in.
//
//   node render.mjs <storyboard.json> <out.mp4> [--fps 30] [--width 1080] [--from 0] [--to 12] [--workers 3]
//   node render.mjs <storyboard.json> <out_dir> --stills 1,6.5,20     # PNG previews only
//   node render.mjs <storyboard.json> --check                         # validate + print the timeline
import { createRequire } from 'node:module';
import { execSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const Timeline = require(path.join(here, '..', 'engine', 'timeline.js'));

function loadPlaywright() {
  try { return require('playwright'); } catch {}
  const root = execSync('npm root -g').toString().trim();
  return require(path.join(root, 'playwright'));
}

const args = process.argv.slice(2);
const FLAGS_WITH_VALUE = new Set(['fps', 'width', 'from', 'to', 'stills', 'workers']);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const has = k => args.includes('--' + k);
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && FLAGS_WITH_VALUE.has(args[i - 1].slice(2))));
const [sbPath, out] = pos;
if (!sbPath || (!out && !has('check'))) {
  console.error('usage: render.mjs <storyboard.json> <out.mp4|dir> [--fps N] [--width PX] [--from S] [--to S] [--workers N] [--stills t1,t2] | --check');
  process.exit(1);
}

const raw = JSON.parse(fs.readFileSync(sbPath, 'utf8'));
const sbDir = path.dirname(path.resolve(sbPath));
const fps = +opt('fps', raw.meta?.fps || 30);
const width = +opt('width', raw.meta?.width || 1080);
const height = Math.round(width * 16 / 9 / 2) * 2;
raw.meta = { ...(raw.meta || {}), width, height };
const sb = Timeline.normalize(raw);
const duration = sb.duration || Math.max(sb.scenes.at(-1).end, ...sb.captions.map(c => c.end));

const KNOWN = ['title', 'terminal', 'checklist', 'avatars', 'stat', 'compare', 'code', 'flow', 'bullets', 'cluster', 'html'];
const warnings = Timeline.validate(sb, KNOWN);
if (has('check')) {
  for (const s of sb.scenes) console.log(`${s.start.toFixed(2).padStart(6)} → ${s.end.toFixed(2).padStart(6)}  ${s.type}`);
  console.log(`total ${duration.toFixed(1)}s, ${sb.captions.length} captions`);
  console.log(warnings.length ? warnings.map(w => '⚠ ' + w).join('\n') : '✓ no warnings');
  process.exit(0);
}
warnings.forEach(w => console.warn('⚠ ' + w));

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'explainer-'));
function ffmpeg(argv) {
  const p = spawn('ffmpeg', ['-y', '-v', 'error', ...argv], { stdio: ['pipe', 'inherit', 'inherit'] });
  p.done = new Promise((res, rej) => p.on('close', c => c === 0 ? res() : rej(new Error('ffmpeg exited ' + c))));
  return p;
}

let audio = sb.audio ? path.resolve(sbDir, sb.audio) : null;
// per-line voice clips (from scripts/tts.py) are placed at their caption start times
const clips = sb.captions.filter(c => c.audio);
const duration0 = duration;
if (!audio && clips.length) {
  audio = path.join(tmp, 'voice.wav');
  const inputs = clips.flatMap(c => ['-i', path.resolve(sbDir, c.audio)]);
  const graph = clips.map((c, i) => `[${i}:a]aresample=48000,adelay=${Math.round(c.start * 1000)}:all=1[a${i}]`).join(';')
    + ';' + clips.map((_, i) => `[a${i}]`).join('') + `amix=inputs=${clips.length}:normalize=0,apad=whole_dur=${duration}[out]`;
  await ffmpeg([...inputs, '-filter_complex', graph, '-map', '[out]', '-ac', '1', audio]).done;
}
// lip-sync envelope: voice loudness per video frame, 0..1
let envelope = null;
if (audio) {
  const pcm = execSync(`ffmpeg -v error -i "${audio}" -ac 1 -ar 8000 -f s16le -`, { maxBuffer: 1 << 28 });
  const smp = new Int16Array(pcm.buffer, pcm.byteOffset, pcm.length >> 1), per = Math.round(8000 / fps);
  envelope = [];
  for (let i = 0; i < smp.length; i += per) {
    let e = 0; for (let j = i; j < Math.min(smp.length, i + per); j++) e += smp[j] * smp[j];
    envelope.push(Math.sqrt(e / per) / 32768);
  }
  const peak = [...envelope].sort((a, b) => a - b)[Math.floor(envelope.length * 0.97)] || 1;
  envelope = envelope.map(v => Math.min(1, Math.max(0, (v / peak - 0.08) * 1.15)));
}

const player = pathToFileURL(path.join(here, '..', 'engine', 'player.html')).href;
const { chromium } = loadPlaywright();
const launch = {};
if (fs.existsSync('/opt/pw-browsers')) {
  // cloud containers ship a pinned Chromium; fall back to Playwright's default elsewhere
  try { launch.executablePath = execSync('ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome 2>/dev/null | head -1').toString().trim() || undefined; } catch {}
}
const browser = await chromium.launch(launch);

async function openPage() {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('page error:', e.message));
  await page.goto(player);
  // the page normalizes again; feed it the raw storyboard so preview and render share one code path
  await page.evaluate(s => window.__load(s), raw);
  if (envelope) await page.evaluate(([e, f]) => window.__setEnvelope(e, f), [envelope, fps]);
  return page;
}

const stills = opt('stills');
if (stills) {
  fs.mkdirSync(out, { recursive: true });
  const page = await openPage();
  for (const t of stills.split(',').map(Number)) {
    await page.evaluate(t => window.__seek(t), t);
    const f = path.join(out, `still_${t.toFixed(2)}.png`);
    await page.screenshot({ path: f });
    console.log(f);
  }
  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  process.exit(0);
}

const from = +opt('from', 0), to = Math.min(+opt('to', duration), duration);
const total = Math.round((to - from) * fps);
const workers = Math.max(1, Math.min(+opt('workers', Math.max(1, os.cpus().length - 1)), Math.ceil(total / fps)));
const VENC = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(fps)];

// Split the frame range into contiguous chunks, one Chromium page + encoder per worker.
let rendered = 0;
const t0 = Date.now();
const chunk = Math.ceil(total / workers);
const parts = [];
await Promise.all(Array.from({ length: workers }, async (_, w) => {
  const a = w * chunk, b = Math.min(total, a + chunk);
  if (a >= b) return;
  const file = path.join(tmp, `part${String(w).padStart(2, '0')}.mp4`);
  parts[w] = file;
  const page = await openPage();
  const enc = ffmpeg(['-f', 'image2pipe', '-framerate', String(fps), '-i', '-', ...VENC, file]);
  for (let f = a; f < b; f++) {
    await page.evaluate(t => window.__seek(t), from + f / fps);
    const buf = await page.screenshot({ type: 'jpeg', quality: 95 });
    if (!enc.stdin.write(buf)) await new Promise(r => enc.stdin.once('drain', r));
    if (++rendered % (fps * 5) === 0) process.stdout.write(`\rframe ${rendered}/${total}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  enc.stdin.end();
  await enc.done;
  await page.close();
}));
await browser.close();

const list = path.join(tmp, 'list.txt');
fs.writeFileSync(list, parts.filter(Boolean).map(f => `file '${f}'`).join('\n'));
const ff = ['-f', 'concat', '-safe', '0', '-i', list];
const music = sb.music?.file ? path.resolve(sbDir, sb.music.file) : null;
if (audio) ff.push('-ss', String(from), '-i', audio);
if (music) ff.push('-stream_loop', '-1', '-ss', String(from), '-i', music);
if (audio && music) {
  ff.push('-filter_complex', `[2:a]volume=${sb.music.volume ?? 0.12}[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]`, '-map', '0:v', '-map', '[a]');
} else if (music) {
  ff.push('-filter_complex', `[1:a]volume=${sb.music.volume ?? 0.3}[a]`, '-map', '0:v', '-map', '[a]');
} else if (audio) {
  ff.push('-map', '0:v', '-map', '1:a');
}
ff.push('-t', String(to - from), '-c:v', 'copy');
if (audio || music) ff.push('-c:a', 'aac', '-b:a', '192k');
ff.push('-movflags', '+faststart', out);
fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
await ffmpeg(ff).done;
fs.rmSync(tmp, { recursive: true, force: true });
console.log(`\nwrote ${out} (${(to - from).toFixed(1)}s @ ${fps}fps, ${width}x${height}, ${workers} workers, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
