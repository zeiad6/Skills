// Storyboard normalization + validation, shared by the browser engine and scripts/render.mjs.
//
// Scenes may omit start/end and carry narration instead:
//   { "type": "flow", "say": ["line one", {"text": "line two", "keywords": ["K8s"]}], "sync": "say", ... }
// normalize() lays scenes end-to-end, derives caption cues from `say` at a natural speaking rate,
// and (with sync: "say") times each list item to the caption that introduces it.
(function (root) {
  const RTL = /^(ar|fa|ur|he)/;
  const LISTS = ['items', 'nodes', 'cards', 'people'];

  function words(s) { return String(s).trim().split(/\s+/).filter(Boolean).length; }

  function normalize(input) {
    const sb = JSON.parse(JSON.stringify(input));
    sb.meta = sb.meta || {};
    const lang = sb.meta.lang || 'ar';
    const wps = sb.meta.wps || (RTL.test(lang) ? 2.3 : 2.6);  // narration speed, words per second
    const gap = sb.meta.gap ?? 0.12;                            // silence between cues
    sb.captions = (sb.captions || []).slice();
    let cursor = 0;
    for (const s of sb.scenes) {
      if (s.start == null) s.start = cursor;
      const cues = [];
      let t = s.start + (s.lead ?? 0.3);
      for (const line of s.say || []) {
        const c = typeof line === 'string' ? { text: line } : { ...line };
        const d = c.duration || Math.max(1.4, words(c.text) / wps + 0.35);
        c.start = +t.toFixed(2); c.end = +(t + d).toFixed(2);
        cues.push(c); t += d + gap;
      }
      if (s.end == null) s.end = +(Math.max(t + (s.tail ?? 0.25), s.start + (s.duration || 0), s.start + 1.5)).toFixed(2);
      sb.captions.push(...cues);
      // local cue times let scenes reveal their list items on the narration beat
      s._cues = cues.map(c => ({ start: c.start - s.start, end: c.end - s.start }));
      if (s.sync === 'say') {
        const off = s.syncOffset || 0;
        for (const key of LISTS) {
          (s[key] || []).forEach((it, i) => {
            const c = s._cues[i + off];
            if (!c) return;
            if (typeof it === 'string') s[key][i] = { text: it, at: c.start };
            else if (it.at == null) it.at = c.start;
          });
        }
      }
      cursor = s.end;
    }
    sb.captions.sort((a, b) => a.start - b.start);
    return sb;
  }

  // Returns human-readable warnings; empty array means the storyboard looks sane.
  function validate(sb, sceneTypes) {
    const w = [];
    const maxChars = sb.meta?.maxCaptionChars || 48;
    sb.scenes.forEach((s, i) => {
      const tag = `scene ${i + 1} (${s.type})`;
      if (sceneTypes && !sceneTypes.includes(s.type)) w.push(`${tag}: unknown type`);
      if (!(s.end > s.start)) w.push(`${tag}: end must be after start`);
      const n = sb.scenes[i + 1];
      if (n && Math.abs(n.start - s.end) > 0.01) w.push(`${tag}: ${n.start > s.end ? 'gap' : 'overlap'} of ${Math.abs(n.start - s.end).toFixed(2)}s before next scene`);
      if (s.end - s.start > (s.sync ? 16 : 12)) w.push(`${tag}: ${(s.end - s.start).toFixed(1)}s long — split it, viewers drop off on static scenes`);
    });
    (sb.captions || []).forEach((c, i) => {
      if (c.text.length > maxChars) w.push(`caption ${i + 1}: ${c.text.length} chars (> ${maxChars}) — may wrap to 3 lines: "${c.text}"`);
      const nx = sb.captions[i + 1];
      if (nx && nx.start < c.end - 0.01) w.push(`caption ${i + 1}: overlaps the next caption`);
    });
    if (sb.scenes[0] && sb.scenes[0].end > 5) w.push('scene 1 is longer than 5s — the hook should land in the first 3 seconds');
    return w;
  }

  const api = { normalize, validate };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Timeline = api;
})(typeof window !== 'undefined' ? window : globalThis);
