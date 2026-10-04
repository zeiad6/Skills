// "Forge" — the original presenter mascot: a small engineer robot with a hard hat and a tablet.
// mascotSVG(t, talking) returns an SVG string; everything is a pure function of time.
// Do NOT replace this with a well-known copyrighted character — design a new original one instead.
function mascotSVG(t, talking, opts) {
  opts = opts || {};
  const accent = opts.accent || '#4ade80';
  const bob = Math.sin(t * 2.2) * 4;                          // idle breathing
  const blink = (t % 3.7) < 0.12 ? 0.1 : 1;                   // periodic blink
  const mouth = talking ? 4 + Math.abs(Math.sin(t * 13)) * 12 : 3;
  const tilt = Math.sin(t * 0.9) * 2.5;
  const wave = opts.wave ? Math.sin(t * 8) * 18 : 0;
  return `
<svg viewBox="0 0 300 560" width="300" height="560" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="mBody" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#2b3138"/><stop offset="1" stop-color="#161a1f"/></linearGradient>
    <linearGradient id="mHead" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#e7ebef"/><stop offset="1" stop-color="#b9c1ca"/></linearGradient>
    <radialGradient id="mGlow"><stop offset="0" stop-color="${accent}" stop-opacity=".35"/><stop offset="1" stop-color="${accent}" stop-opacity="0"/></radialGradient>
  </defs>
  <ellipse cx="150" cy="540" rx="110" ry="14" fill="#000" opacity=".6"/>
  <g transform="translate(0 ${bob.toFixed(2)})">
    <!-- legs -->
    <rect x="102" y="400" width="36" height="120" rx="14" fill="#1f2a3a"/>
    <rect x="162" y="400" width="36" height="120" rx="14" fill="#1f2a3a"/>
    <rect x="92" y="505" width="56" height="26" rx="12" fill="#e5e7eb"/>
    <rect x="152" y="505" width="56" height="26" rx="12" fill="#e5e7eb"/>
    <!-- torso (hoodie) -->
    <rect x="72" y="250" width="156" height="170" rx="46" fill="url(#mBody)"/>
    <rect x="128" y="300" width="44" height="34" rx="8" fill="none" stroke="${accent}" stroke-width="4"/>
    <text x="150" y="324" text-anchor="middle" font-family="JBMono, monospace" font-size="18" fill="${accent}">&lt;/&gt;</text>
    <!-- left arm holding tablet -->
    <rect x="40" y="270" width="40" height="120" rx="20" fill="#232a31"/>
    <g transform="rotate(-8 60 390)">
      <rect x="16" y="350" width="92" height="120" rx="12" fill="#0d1013" stroke="#3a434e" stroke-width="4"/>
      <rect x="28" y="364" width="68" height="10" rx="5" fill="${accent}" opacity=".9"/>
      <rect x="28" y="384" width="50" height="8" rx="4" fill="#4a535e"/>
      <rect x="28" y="400" width="60" height="8" rx="4" fill="#4a535e"/>
      <circle cx="40" cy="440" r="10" fill="none" stroke="${accent}" stroke-width="4"/>
    </g>
    <!-- right arm (waves when opts.wave) -->
    <g transform="rotate(${(-wave).toFixed(2)} 240 280)">
      <rect x="220" y="270" width="40" height="120" rx="20" fill="#232a31"/>
      <circle cx="240" cy="392" r="20" fill="#d6dbe0"/>
    </g>
    <!-- neck -->
    <rect x="132" y="226" width="36" height="34" rx="8" fill="#9aa3ad"/>
    <!-- head -->
    <g transform="rotate(${tilt.toFixed(2)} 150 160)">
      <circle cx="150" cy="150" r="120" fill="url(#mGlow)"/>
      <rect x="62" y="84" width="176" height="150" rx="56" fill="url(#mHead)"/>
      <rect x="46" y="140" width="22" height="44" rx="10" fill="#9aa3ad"/>
      <rect x="232" y="140" width="22" height="44" rx="10" fill="#9aa3ad"/>
      <!-- visor -->
      <rect x="84" y="118" width="132" height="86" rx="34" fill="#0b0f13"/>
      <g fill="${accent}">
        <rect x="108" y="${(146 - 14 * blink).toFixed(1)}" width="24" height="${(28 * blink).toFixed(1)}" rx="10"/>
        <rect x="168" y="${(146 - 14 * blink).toFixed(1)}" width="24" height="${(28 * blink).toFixed(1)}" rx="10"/>
        <rect x="${(150 - 16).toFixed(1)}" y="${(184 - mouth / 2).toFixed(1)}" width="32" height="${mouth.toFixed(1)}" rx="${Math.min(6, mouth / 2).toFixed(1)}" opacity=".9"/>
      </g>
      <!-- hard hat -->
      <path d="M62 102 Q66 30 150 26 Q234 30 238 102 Z" fill="#f59e0b"/>
      <rect x="44" y="94" width="212" height="20" rx="10" fill="#d97706"/>
      <rect x="140" y="30" width="20" height="66" rx="8" fill="#fbbf24"/>
    </g>
  </g>
</svg>`;
}
