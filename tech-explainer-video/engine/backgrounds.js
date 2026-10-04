// Animated backgrounds. backgroundHTML(spec, t, accent) → HTML string, a pure function of time.
// spec: a theme name or an array of names layered bottom→top:
//   aurora   slow drifting colour glows (cheap radial gradients, no blur filters)
//   network  drifting nodes + links with data pulses travelling along them (cloud / infra topics)
//   grid     perspective grid floor scrolling toward the viewer (speed / pipeline topics)
//   code     faint columns of falling code glyphs (programming topics)
//   stars    subtle twinkling particles
//   plain    the original dot grid only
// Every theme stays dark and low-contrast so text, captions and the presenter remain readable.
(function (root) {
  const W = 1080, H = 1920;

  function rng(seed) {                     // deterministic PRNG (mulberry32)
    return () => {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  const hex = (c, a) => {
    const n = parseInt(c.slice(1), 16);
    return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`;
  };

  const THEMES = {
    plain() {
      return `<div class="abs" style="inset:0;background:radial-gradient(circle at 1px 1px, rgba(255,255,255,.035) 1.5px, transparent 0) 0 0 / 36px 36px"></div>`;
    },

    aurora(t, accent, o) {
      const cols = o.colors || [accent, '#60a5fa', '#c084fc'];
      const blobs = cols.map((c, i) => {
        const x = 50 + 34 * Math.sin(t * (0.07 + i * 0.023) + i * 2.1);
        const y = 30 + 26 * Math.cos(t * (0.05 + i * 0.017) + i * 1.3) + i * 18;
        const r = 52 + 10 * Math.sin(t * 0.11 + i);
        return `radial-gradient(ellipse ${r}% ${r * 0.62}% at ${x.toFixed(2)}% ${y.toFixed(2)}%, ${hex(c, o.glow || 0.30)}, transparent 72%)`;
      });
      return `<div class="abs" style="inset:0;background:${blobs.join(',')}"></div>` + THEMES.plain();
    },

    network(t, accent, o) {
      const cache = THEMES.network._c || (THEMES.network._c = (() => {
        const r = rng(7), n = o.nodes || 34, nodes = [];
        for (let i = 0; i < n; i++) nodes.push({ x: r() * W, y: r() * H, a: r() * 6.28, s: 0.15 + r() * 0.25, k: 18 + r() * 26 });
        const edges = [];
        nodes.forEach((p, i) => nodes.forEach((q, j) => {
          if (j > i && Math.hypot(p.x - q.x, p.y - q.y) < 330) edges.push([i, j, r()]);
        }));
        return { nodes, edges };
      })());
      const P = cache.nodes.map(p => ({ x: p.x + Math.sin(t * p.s + p.a) * p.k, y: p.y + Math.cos(t * p.s * 0.8 + p.a) * p.k }));
      let svg = '';
      for (const [i, j, ph] of cache.edges) {
        const d = Math.hypot(P[i].x - P[j].x, P[i].y - P[j].y), a = Math.max(0, 1 - d / 360) * 0.45;
        svg += `<line x1="${P[i].x.toFixed(1)}" y1="${P[i].y.toFixed(1)}" x2="${P[j].x.toFixed(1)}" y2="${P[j].y.toFixed(1)}" stroke="${hex(accent, a.toFixed(3))}" stroke-width="2"/>`;
        if (ph < 0.35) {                    // data pulse travelling along this link
          const f = (t * (0.25 + ph) + ph * 10) % 1;
          svg += `<circle cx="${(P[i].x + (P[j].x - P[i].x) * f).toFixed(1)}" cy="${(P[i].y + (P[j].y - P[i].y) * f).toFixed(1)}" r="6" fill="${hex(accent, 0.85)}"/>`;
        }
      }
      P.forEach((p, i) => {
        const pulse = 0.5 + 0.5 * Math.sin(t * 1.7 + i);
        svg += `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${(5 + pulse * 3).toFixed(2)}" fill="${hex(accent, (0.45 + pulse * 0.3).toFixed(3))}"/>`;
      });
      return `<svg class="abs" style="inset:0" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${svg}</svg>`;
    },

    grid(t, accent, o) {
      const horizon = o.horizon || 1180, speed = o.speed || 0.6;
      let svg = '';
      for (let i = 0; i < 18; i++) {        // horizontal lines rushing toward the viewer
        const z = ((i - t * speed) % 18 + 18) % 18 + 1;
        const y = horizon + 3200 / z - 150;
        if (y > H || y < horizon) continue;
        const a = Math.min(0.6, (y - horizon) / (H - horizon) * 0.8);
        svg += `<line x1="0" y1="${y.toFixed(1)}" x2="${W}" y2="${y.toFixed(1)}" stroke="${hex(accent, a.toFixed(3))}" stroke-width="2"/>`;
      }
      for (let i = -12; i <= 12; i++) {     // vertical lines converging on the vanishing point
        const xb = W / 2 + i * 160;
        svg += `<line x1="${W / 2}" y1="${horizon}" x2="${xb}" y2="${H}" stroke="${hex(accent, 0.32)}" stroke-width="2"/>`;
      }
      return `<div class="abs" style="left:0;right:0;top:${horizon - 300}px;height:600px;background:radial-gradient(ellipse 60% 50% at 50% 50%, ${hex(accent, 0.25)}, transparent 70%)"></div>
        <svg class="abs" style="inset:0" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${svg}</svg>
        <div class="abs" style="left:0;right:0;top:${horizon}px;bottom:0;background:linear-gradient(transparent, rgba(5,6,7,.55))"></div>`;
    },

    code(t, accent, o) {
      const cache = THEMES.code._c || (THEMES.code._c = (() => {
        const r = rng(11), glyphs = '{}[]()<>=+-*/;:01λ$#&|!?'.split(''), cols = [];
        for (let c = 0; c < 22; c++) {
          const s = []; for (let k = 0; k < 30; k++) s.push(glyphs[Math.floor(r() * glyphs.length)]);
          cols.push({ x: c * 50 + r() * 20, v: 40 + r() * 70, o: r() * H, s });
        }
        return cols;
      })());
      let h = '';
      for (const c of cache) {
        const y0 = ((c.o + t * c.v) % (H + 900)) - 900;
        c.s.forEach((g, k) => {
          const y = y0 + k * 34;
          if (y < -40 || y > H) return;
          const a = k === c.s.length - 1 ? 0.8 : 0.08 + 0.25 * (k / c.s.length);
          h += `<span style="position:absolute;left:${c.x.toFixed(0)}px;top:${y.toFixed(0)}px;color:${hex(accent, a.toFixed(3))}">${g === '<' ? '&lt;' : g === '>' ? '&gt;' : g === '&' ? '&amp;' : g}</span>`;
        });
      }
      return `<div class="abs mono" style="inset:0;font-size:26px;line-height:1">${h}</div>`;
    },

    stars(t, accent) {
      const cache = THEMES.stars._c || (THEMES.stars._c = (() => {
        const r = rng(3), s = [];
        for (let i = 0; i < 90; i++) s.push({ x: r() * W, y: r() * H, z: 0.3 + r() * 0.7, p: r() * 6.28 });
        return s;
      })());
      return `<svg class="abs" style="inset:0" width="${W}" height="${H}">${cache.map(s => {
        const y = (s.y - t * 14 * s.z + H) % H, a = 0.15 + 0.35 * s.z * (0.5 + 0.5 * Math.sin(t * 2 * s.z + s.p));
        return `<circle cx="${s.x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(1.2 + s.z * 1.8).toFixed(2)}" fill="rgba(255,255,255,${a.toFixed(3)})"/>`;
      }).join('')}</svg>`;
    }
  };

  function backgroundHTML(spec, t, accent, opts) {
    const layers = Array.isArray(spec) ? spec : [spec || 'plain'];
    const body = layers.map(n => (THEMES[n] || THEMES.plain)(t, accent || '#4ade80', opts || {})).join('');
    // vignette keeps edges dark and the centre readable
    return `<div class="abs" style="inset:0;overflow:hidden">${body}<div class="abs" style="inset:0;background:radial-gradient(ellipse 85% 70% at 50% 45%, transparent 60%, rgba(0,0,0,.5))"></div></div>`;
  }

  root.backgroundHTML = backgroundHTML;
  root.BACKGROUNDS = Object.keys(THEMES);
})(window);
