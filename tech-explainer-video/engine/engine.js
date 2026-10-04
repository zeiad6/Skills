// Deterministic storyboard renderer. Every frame is a pure function of time `t`,
// so headless capture (scripts/render.mjs) and live preview produce identical output.
// API: window.__load(storyboard), window.__seek(seconds), window.__duration()
(function () {
  const W = 1080, H = 1920;
  let SB = null, DIR = 'rtl';

  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const ease = x => 1 - Math.pow(1 - clamp(x), 3);
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // appear(lt, at): fade + rise starting at local time `at`
  const appear = (lt, at = 0, d = 0.45, dy = 30) => {
    const p = ease((lt - at) / d);
    return `opacity:${p.toFixed(3)};transform:translateY(${((1 - p) * dy).toFixed(1)}px)`;
  };
  // Stagger helper: item i appears at explicit `at` or evenly spread over the first 60% of the scene.
  const atOf = (item, i, n, dur, start = 0.25) =>
    (item && typeof item === 'object' && item.at != null) ? item.at : start + i * Math.min(1.2, (dur * 0.6) / Math.max(1, n));

  // ---------------------------------------------------------------- pipeline bar
  function pipelineBar(state, lt) {
    const groups = SB.pipeline.groups;
    const steps = groups.flatMap(g => g.steps);
    const n = steps.length, x0 = 70, x1 = W - 80 - 70;
    const xs = steps.map((_, i) => x0 + (x1 - x0) * (n === 1 ? 0.5 : i / (n - 1)));
    const done = state.done != null ? state.done : -1;
    const fail = state.fail != null ? state.fail : -1;
    // pipeline is laid out LTR always (it is a timeline), like a progress bar
    let h = `<div class="abs pipe" style="direction:ltr">`;
    let k = 0;
    groups.forEach(g => {
      const a = xs[k] - 30, b = xs[k + g.steps.length - 1] + 30;
      h += `<div class="grp" style="left:${a}px;width:${b - a}px"><b>${esc(g.label)}</b></div>`;
      k += g.steps.length;
    });
    for (let i = 0; i < n - 1; i++) {
      const on = i < done || (i === done - 1);
      const col = fail >= 0 && i >= fail - 1 && i < fail ? 'var(--red)' : (i < done ? 'var(--green)' : 'var(--line-2)');
      h += `<div class="seg" style="left:${xs[i]}px;width:${xs[i + 1] - xs[i]}px;background:${on || i < done ? col : 'var(--line-2)'}"></div>`;
    }
    steps.forEach((s, i) => {
      let cls = '';
      if (i === fail) cls = 'fail'; else if (i <= done) cls = 'done'; else if (i === done + 1 && state.current) cls = 'cur';
      const pulse = cls === 'cur' ? `transform:scale(${(1 + 0.12 * Math.sin(lt * 6)).toFixed(3)})` : '';
      h += `<div class="dot ${cls}" style="left:${xs[i]}px;${pulse}"></div>`;
      h += `<div class="lbl ${i <= done && i !== fail ? 'on' : ''} ${i === fail ? 'bad' : ''}" style="left:${xs[i]}px">${esc(s)}</div>`;
    });
    return h + `</div>`;
  }

  // ---------------------------------------------------------------- scene types
  const SCENES = {
    title(s, lt, dur) {
      return `<div style="height:100%;display:flex;flex-direction:column;justify-content:center;gap:26px;text-align:center">
        ${s.eyebrow ? `<div class="h-eyebrow" style="${appear(lt, 0.1)}">${esc(s.eyebrow)}</div>` : ''}
        <div class="h-big" style="font-size:${s.size || 92}px;${appear(lt, 0.25, 0.6, 50)}">${esc(s.title)}</div>
        ${s.subtitle ? `<div class="h-mid muted" style="font-weight:700;font-size:40px;${appear(lt, 0.6)}">${esc(s.subtitle)}</div>` : ''}
      </div>`;
    },

    terminal(s, lt, dur) {
      const lines = s.lines || [];
      const speed = s.cps || 38; // chars per second
      let budget = Math.max(0, lt - 0.4) * speed, out = '';
      for (const ln of lines) {
        if (budget <= 0) break;
        const isCmd = ln.startsWith('$');
        // commands are typed char by char, output lines appear at once
        const show = isCmd ? ln.slice(0, Math.floor(budget)) : ln;
        budget -= isCmd ? ln.length : 10;
        const col = isCmd ? '#e5e7eb' : (/(error|fail|✗)/i.test(ln) ? 'var(--red)' : (/(ok|pass|✓|success|done)/i.test(ln) ? 'var(--green)' : '#94a3b8'));
        out += `<span style="color:${col}">${esc(show)}</span>\n`;
      }
      const cursor = (Math.floor(lt * 2) % 2 === 0) ? '<span class="cursor"></span>' : '';
      const header = s.server ? `<div class="card" style="display:flex;align-items:center;gap:22px;padding:24px 28px;margin-bottom:22px;${appear(lt, 0)}">
          <div class="ico" style="width:66px;height:66px;border-radius:16px;border:2px solid var(--line-2);display:grid;place-items:center;font:800 30px JBMono;color:var(--muted)">≡</div>
          <div style="flex:1"><div style="font:800 36px Cairo;direction:ltr;text-align:start">${esc(s.server.name)}</div><div class="mono muted" style="font-size:21px">${esc(s.server.sub || '')}</div></div>
          ${s.server.live ? `<div style="font:800 22px Cairo;color:var(--green)">● LIVE</div>` : ''}</div>` : '';
      return `${header}<div class="card term" style="${appear(lt, 0.1)}">
        <div class="bar"><i style="background:#f05252"></i><i style="background:#fbbf24"></i><i style="background:#4ade80"></i><span>${esc(s.title || 'bash')}</span></div>
        <pre>${out}${cursor}</pre></div>`;
    },

    checklist(s, lt, dur) {
      const items = s.items || [];
      let h = s.heading ? `<div class="h-eyebrow" style="margin-bottom:22px;${appear(lt, 0)}">${esc(s.heading)}</div>` : '';
      items.forEach((it, i) => {
        const at = atOf(it, i, items.length, dur);
        const resolveAt = it.resolveAt != null ? it.resolveAt : at + 0.9;
        const res = lt >= resolveAt ? (it.status || 'ok') : 'wait';
        const st = res === 'ok' ? '<div class="st ok">✓</div>' : res === 'fail' ? '<div class="st bad">✕</div>' : '<div class="st"></div>';
        h += `<div class="card row" style="${appear(lt, at)}">
          <div class="ico">${esc(it.icon || '›')}</div>
          <div><div class="ttl">${esc(it.title)}</div>${it.sub ? `<div class="sub">${esc(it.sub)}</div>` : ''}</div>${st}</div>`;
      });
      return h;
    },

    avatars(s, lt, dur) {
      const ppl = s.people || [];
      let h = `<div style="display:flex;justify-content:center;gap:34px;flex-wrap:wrap;margin-top:40px">`;
      ppl.forEach((p, i) => {
        h += `<div style="${appear(lt, atOf(p, i, ppl.length, dur * 0.6, 0.1))}"><div class="av" style="border-color:${p.color || '#3a434e'}">${esc(p.letter || p.name[0])}</div><div class="av-n">${esc(p.name)}</div>${p.note ? `<div class="av-n" style="color:var(--green);font-size:20px">${esc(p.note)}</div>` : ''}</div>`;
      });
      h += `</div>`;
      // branch line with commits flowing into main
      const prog = ease((lt - 0.8) / Math.max(1, dur - 1.5));
      h += `<div class="abs" style="left:40px;right:40px;top:640px;height:4px;background:var(--line-2);direction:ltr">
        <div style="height:100%;width:${(prog * 100).toFixed(1)}%;background:var(--green)"></div></div>
        <div class="abs mono muted" style="right:40px;top:665px;font-size:24px">${esc(s.branch || 'main')}</div>`;
      return h;
    },

    stat(s, lt, dur) {
      // values: [5, 25, 50, 100] stepping across the scene, or a single value counting up
      const vals = s.values || [s.value || 0];
      const seg = dur / vals.length, idx = Math.min(vals.length - 1, Math.floor(lt / seg));
      const prev = idx ? vals[idx - 1] : 0, cur = vals[idx];
      const v = prev + (cur - prev) * ease((lt - idx * seg) / 0.7);
      const n = s.grid || 10, onCount = Math.round(n * n * v / 100);
      let dots = '';
      for (let i = 0; i < n * n; i++) dots += `<i class="${i < onCount ? 'on' : ''}"></i>`;
      return `<div style="text-align:center;${appear(lt, 0)}">
        <div style="font:800 150px/1 Cairo;color:var(--blue);direction:ltr">${Math.round(v)}${esc(s.unit == null ? '%' : s.unit)}</div>
        <div class="h-eyebrow" style="margin:14px 0 34px">${esc(s.label || '')}</div>
        <div class="dots" style="grid-template-columns:repeat(${n},38px);justify-content:center;direction:ltr">${dots}</div>
        <div style="display:flex;justify-content:space-between;margin:34px 40px 12px;font:800 24px Cairo"><span class="blue">${esc(s.leftLabel || '')}</span><span class="muted">${esc(s.rightLabel || '')}</span></div>
        <div class="bar-track" style="margin:0 40px;direction:ltr"><div class="bar-fill" style="width:${v.toFixed(2)}%"></div></div>
      </div>`;
    },

    compare(s, lt, dur) {
      const cards = s.cards || [];
      return cards.map((c, i) => `<div class="card cmp" style="padding:36px 40px;margin-bottom:30px;border-color:${c.color || 'var(--line)'};${appear(lt, atOf(c, i, cards.length, dur, 0.15))}">
        <div class="big" style="text-align:start;color:${c.color || 'var(--text)'}">${esc(c.title)}</div>
        <div class="q">${esc(c.text)}</div>${c.sub ? `<div class="muted" style="font:700 26px Cairo;margin-top:10px">${esc(c.sub)}</div>` : ''}</div>`).join('');
    },

    code(s, lt, dur) {
      const lines = (s.code || '').split('\n');
      const reveal = s.reveal === false ? lines.length : Math.floor(Math.max(0, lt - 0.3) * (s.lps || 4));
      const hl = new Set(s.highlight || []);
      const body = lines.map((l, i) => i < reveal ? `<span class="ln ${hl.has(i + 1) && lt > (s.highlightAt || 0) ? 'hl' : ''}">${esc(l) || ' '}</span>` : '').join('');
      return `<div class="card term code" style="${appear(lt, 0)}"><div class="bar"><i style="background:#f05252"></i><i style="background:#fbbf24"></i><i style="background:#4ade80"></i><span>${esc(s.file || 'config.yml')}</span></div><pre>${body}</pre></div>`;
    },

    flow(s, lt, dur) {
      const nodes = s.nodes || [];
      const per = (dur - 0.6) / Math.max(1, nodes.length);
      const ats = nodes.map((nd, i) => nd.at != null ? nd.at : 0.3 + i * per);
      let active = -1;
      ats.forEach((a, i) => { if (lt >= a) active = i; });
      if (active === nodes.length - 1 && lt > dur - 0.4 && s.finish !== false) active = nodes.length;
      let h = `<div style="position:relative;padding-inline-start:10px">`;
      h += `<div class="abs" style="inset-inline-start:41px;top:40px;bottom:40px;width:4px;background:var(--line-2)"><div style="width:100%;height:${(clamp(active / Math.max(1, nodes.length - 1)) * 100).toFixed(1)}%;background:var(--green)"></div></div>`;
      nodes.forEach((nd, i) => {
        const cls = i < active ? 'done' : i === active ? 'cur' : '';
        h += `<div class="node ${cls}" style="margin-bottom:${s.gap || 34}px;position:relative;${appear(lt, Math.min(ats[i] - 0.2, i * 0.25))}">
          <div class="c">${i < active ? '✓' : esc(nd.icon || i + 1)}</div><div><div class="t">${esc(nd.title)}</div>${nd.sub ? `<div class="s">${esc(nd.sub)}</div>` : ''}</div></div>`;
      });
      return h + `</div>`;
    },

    bullets(s, lt, dur) {
      const items = s.items || [];
      let h = s.heading ? `<div class="h-mid" style="margin-bottom:34px;${appear(lt, 0)}">${esc(s.heading)}</div>` : '';
      items.forEach((it, i) => {
        const txt = typeof it === 'string' ? it : it.text;
        h += `<div style="display:flex;gap:20px;align-items:baseline;margin-bottom:26px;font:700 40px/1.35 Cairo;${appear(lt, atOf(it, i, items.length, dur))}">
          <span style="color:var(--accent);flex:none">●</span><span>${esc(txt)}</span></div>`;
      });
      return h;
    },

    // Kubernetes-style cluster: worker nodes holding pods; events scale replicas or kill nodes and
    // pods get rescheduled onto healthy nodes (pending → running). Deterministic in lt.
    cluster(s, lt, dur) {
      const nodes = s.nodes || [{ name: 'node-1' }, { name: 'node-2' }, { name: 'node-3' }];
      const evs = (s.events || []).slice().sort((a, b) => a.at - b.at);
      let replicas = s.replicas ?? 3;
      const dead = new Set();
      // pods[i] = { node, since }: since = when it (re)started on that node
      const place = (alive, i) => alive[i % alive.length];
      let alive = nodes.map((_, i) => i);
      let pods = Array.from({ length: replicas }, (_, i) => ({ node: place(alive, i), since: s.instant ? -9 : 0.3 + i * 0.15 }));
      for (const e of evs) {
        if (e.at > lt) break;
        if (e.action === 'scale') {
          for (let i = pods.length; i < e.replicas; i++) pods.push({ node: -1, since: e.at + (i - replicas) * 0.12 });
          pods.length = e.replicas; replicas = e.replicas;
        } else if (e.action === 'kill') {
          dead.add(e.node);
        } else if (e.action === 'revive') {
          dead.delete(e.node);
        }
        alive = nodes.map((_, i) => i).filter(i => !dead.has(i));
        // reschedule: pods on dead nodes (or unplaced) move to the least-loaded alive node
        const load = {}; alive.forEach(i => load[i] = 0);
        pods.forEach(p => { if (p.node >= 0 && !dead.has(p.node)) load[p.node]++; });
        pods.forEach(p => {
          if (p.node < 0 || dead.has(p.node)) {
            const tgt = alive.slice().sort((a, b) => load[a] - load[b] || a - b)[0];
            if (tgt == null) return;
            load[tgt]++;
            p.since = Math.max(p.since, e.at + (e.action === 'kill' ? 0.9 : 0));
            p.node = tgt;
          }
        });
      }
      const label = s.app || 'app';
      let h = '';
      if (s.controlPlane !== false) {
        h += `<div class="card" style="padding:20px 26px;margin-bottom:26px;display:flex;align-items:center;gap:20px;border-color:#2b3a52;${appear(lt, 0)}">
          <div style="font:800 30px Cairo;color:var(--blue);direction:ltr">⎈ Control Plane</div>
          <div class="mono muted" style="font-size:21px;margin-inline-start:auto">${esc(s.controlPlaneSub || 'api-server · scheduler · etcd')}</div></div>`;
      }
      if (s.desired !== false) {
        h += `<div style="display:flex;justify-content:center;gap:18px;margin-bottom:22px;font:800 30px Cairo;${appear(lt, 0.1)}">
          <span class="muted">${esc(s.desiredLabel || 'replicas')}</span><span class="mono" style="font-size:34px;color:var(--green)">${pods.filter(p => p.node >= 0 && lt - p.since > 0.8).length}/${replicas}</span></div>`;
      }
      const cols = nodes.length > 3 ? 2 : nodes.length;
      h += `<div style="display:grid;grid-template-columns:repeat(${cols},1fr);gap:20px;direction:ltr">`;
      nodes.forEach((nd, i) => {
        const isDead = dead.has(i);
        const mine = pods.map((p, k) => ({ ...p, k })).filter(p => p.node === i && lt >= p.since - 0.01);
        let podsH = '';
        mine.forEach(p => {
          const age = lt - p.since, pending = age < 0.8;
          const sc = ease(age / 0.35);
          podsH += `<div style="width:${s.podSize || 84}px;height:${s.podSize || 84}px;border-radius:18px;display:grid;place-items:center;font:800 30px JBMono;transform:scale(${sc.toFixed(3)});
            background:${pending ? 'rgba(251,191,36,.15)' : 'rgba(74,222,128,.14)'};border:3px solid ${pending ? 'var(--amber)' : 'var(--green)'};color:${pending ? 'var(--amber)' : 'var(--green)'}">${pending ? '…' : '▣'}</div>`;
        });
        const shake = isDead ? `transform:translateX(${(Math.sin(lt * 50) * Math.max(0, 1 - (lt - (evs.find(e => e.action === 'kill' && e.node === i)?.at || 0)) * 2) * 8).toFixed(1)}px)` : '';
        h += `<div class="card" style="padding:22px;min-height:${s.nodeHeight || 400}px;border-color:${isDead ? 'var(--red)' : 'var(--line)'};opacity:${isDead ? 0.55 : 1};${shake};${appear(lt, 0.15 + i * 0.12)}">
          <div style="display:flex;align-items:center;gap:10px;font:800 24px JBMono;color:${isDead ? 'var(--red)' : 'var(--muted)'}">${isDead ? '✕' : '▤'} ${esc(nd.name)}</div>
          <div style="display:flex;flex-wrap:wrap;gap:16px;margin-top:22px">${podsH}</div></div>`;
      });
      h += `</div>`;
      if (s.service) {
        const flow = (lt * 0.8) % 1;
        h += `<div class="card" style="margin-top:26px;padding:18px 26px;display:flex;align-items:center;gap:18px;direction:ltr;${appear(lt, 0.3)}">
          <div style="font:800 26px Cairo;color:var(--green)">Service</div>
          <div style="flex:1;height:4px;background:var(--line-2);position:relative"><i style="position:absolute;top:-6px;left:${(flow * 100).toFixed(1)}%;width:16px;height:16px;border-radius:50%;background:var(--green)"></i></div>
          <div class="mono muted" style="font-size:22px">${esc(s.service)}</div></div>`;
      }
      if (s.legend !== false) h += `<div class="mono muted" style="margin-top:18px;font-size:20px;text-align:center">▣ pod (${esc(label)})</div>`;
      return h;
    },

    // Fallback for anything custom: raw HTML (trusted storyboard content only)
    html(s, lt, dur) { return s.html || ''; }
  };

  // ---------------------------------------------------------------- captions
  function captionHTML(t) {
    const c = (SB.captions || []).find(c => t >= c.start && t < c.end);
    if (!c) return '';
    const words = c.text.split(/\s+/).filter(Boolean);
    const kws = new Set((c.keywords || []).map(k => k.toLowerCase()));
    const lt = t - c.start, d = c.end - c.start;
    // word-by-word reveal paced over 85% of the cue, so the line reads like karaoke
    const lit = Math.ceil(clamp(lt / (d * 0.85)) * words.length);
    const p = ease(lt / 0.2);
    const html = words.map((w, i) => {
      const k = kws.has(w.replace(/[.,،؟?!:؛"]/g, '').toLowerCase());
      return `<span class="w ${i < lit ? 'on' : ''} ${k ? 'kw' : ''}">${esc(w)}</span>`;
    }).join(' ');
    return `<div class="abs cap" style="opacity:${p.toFixed(3)}"><span class="pill" dir="${DIR}">${html}</span></div>`;
  }

  // ---------------------------------------------------------------- frame
  function sceneAt(t) {
    const sc = SB.scenes;
    for (let i = 0; i < sc.length; i++) if (t >= sc[i].start && t < sc[i].end) return i;
    return t >= (sc.at(-1)?.end || 0) ? sc.length - 1 : 0;
  }

  function render(t) {
    const stage = document.getElementById('stage');
    const i = sceneAt(t), s = SB.scenes[i], prev = SB.scenes[i - 1], next = SB.scenes[i + 1];
    const lt = t - s.start, dur = s.end - s.start;
    const fadeIn = ease(lt / 0.35), fadeOut = 1 - ease((lt - (dur - 0.25)) / 0.25);

    const side = s.presenter === true ? (DIR === 'rtl' ? 'right' : 'left') : s.presenter;
    const hasP = !!side;
    // content box: next to the presenter, or full width
    const box = s.box || (hasP
      ? { x: side === 'left' ? 330 : 40, y: s.top || 400, w: 710, h: 980 }
      : { x: 60, y: s.top || 400, w: 960, h: 980 });

    let h = window.backgroundHTML
      ? backgroundHTML(s.background || SB.meta?.background || 'plain', t, SB.meta?.bgAccent || SB.meta?.accent, SB.meta?.bgOptions)
      : '';
    if (SB.pipeline && s.pipeline !== false && s.pipeline) h += pipelineBar(s.pipeline, lt);
    if (s.eyebrow && s.type !== 'title') h += `<div class="abs h-eyebrow" style="left:60px;right:60px;top:${box.y - 70}px;text-align:center;${appear(lt, 0)}">${esc(s.eyebrow)}</div>`;

    const fn = SCENES[s.type] || SCENES.html;
    h += `<div class="abs" dir="${DIR}" style="left:${box.x}px;top:${box.y}px;width:${box.w}px;height:${box.h}px;opacity:${(fadeIn * (next ? fadeOut : 1)).toFixed(3)}">${fn(s, lt, dur)}</div>`;

    if (hasP) {
      const prevSame = prev && !!prev.presenter, nextSame = next && !!next.presenter;
      const pin = prevSame ? 1 : ease(lt / 0.5), pout = nextSame || !next ? 1 : 1 - ease((lt - (dur - 0.3)) / 0.3);
      const k = pin * pout, dx = (1 - k) * (side === 'left' ? -120 : 120);
      // lip-sync: voice envelope (set by render.mjs) when present, else animate while a caption is up
      const env = window.__ENVELOPE;
      const talking = env ? (env[Math.floor(t * env.fps)] || 0) : (SB.captions || []).some(c => t >= c.start && t < c.end - 0.1);
      const x = side === 'left' ? 20 : W - 320;
      h += `<div class="abs" style="left:${x}px;top:${(s.presenterTop || 820)}px;opacity:${k.toFixed(3)};transform:translateX(${dx.toFixed(1)}px)">${presenterSVG(SB.meta?.presenter || 'forge', t, talking, { accent: SB.meta?.presenterAccent, wave: s.wave && lt < 1.6 })}</div>`;
    }
    h += captionHTML(t);
    if (SB.meta?.handle) h += `<div class="abs handle">${esc(SB.meta.handle)}</div>`;
    stage.innerHTML = h;
  }

  function fit() {
    const m = SB?.meta || {}, w = m.width || W, h = m.height || H;
    const vp = document.getElementById('viewport');
    vp.style.width = w + 'px'; vp.style.height = h + 'px';
    document.getElementById('stage').style.transform = `scale(${w / W})`;
  }

  window.__load = raw => {
    const sb = window.Timeline ? Timeline.normalize(raw) : raw;
    SB = sb; DIR = sb.meta?.dir || (/^(ar|fa|ur|he)/.test(sb.meta?.lang || '') ? 'rtl' : 'ltr');
    document.documentElement.lang = sb.meta?.lang || 'ar';
    if (sb.meta?.accent) document.documentElement.style.setProperty('--accent', sb.meta.accent);
    fit(); render(0);
    return document.fonts.ready.then(() => true);
  };
  window.__seek = t => render(t);
  window.__setEnvelope = (arr, fps) => { window.__ENVELOPE = arr; if (arr) arr.fps = fps; };
  window.__duration = () => SB.duration || Math.max(SB.scenes.at(-1).end, ...(SB.captions || []).map(c => c.end));
  window.__SCENE_TYPES = Object.keys(SCENES);
  window.__warnings = () => window.Timeline ? Timeline.validate(SB, Object.keys(SCENES)) : [];
})();
