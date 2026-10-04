// Original presenter mascots. presenterSVG(name, t, talk, opts) returns an SVG string; pure function of time.
//   forge — engineer robot with a hard hat and a tablet (pairs with male voices)
//   nova  — engineer robot with a headset, glowing visor and a light-trail ponytail (pairs with female voices)
// `talk` is the mouth opening 0..1 (from the voice envelope) or a boolean.
// Do NOT replace these with well-known copyrighted characters — design new original ones instead.
function presenterSVG(name, t, talk, opts) {
  return (name === 'nova' ? novaSVG : mascotSVG)(t, talk, opts);
}

function mouthOpen(t, talk) {
  if (typeof talk === 'number') return talk;
  return talk ? 0.25 + Math.abs(Math.sin(t * 13)) * 0.6 : 0;
}

function mascotSVG(t, talking, opts) {
  opts = opts || {};
  const accent = opts.accent || '#4ade80';
  const bob = Math.sin(t * 2.2) * 4;                          // idle breathing
  const blink = (t % 3.7) < 0.12 ? 0.1 : 1;                   // periodic blink
  const mouth = 3 + mouthOpen(t, talking) * 15;
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

function novaSVG(t, talking, opts) {
  opts = opts || {};
  const accent = opts.accent || '#c084fc';
  const bob = Math.sin(t * 2.0) * 4;
  const blink = (t % 4.1) < 0.12 ? 0.12 : 1;
  const open = mouthOpen(t, talking);
  const tilt = Math.sin(t * 0.8) * 3;
  const sway = Math.sin(t * 1.6) * 6;                          // ponytail trail sways
  const wave = opts.wave ? Math.sin(t * 8) * 20 : 0;
  return `
<svg viewBox="0 0 300 560" width="300" height="560" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="nBody" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#3b2f4f"/><stop offset="1" stop-color="#1c1626"/></linearGradient>
    <linearGradient id="nHead" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f5f3ff"/><stop offset="1" stop-color="#d4cde6"/></linearGradient>
    <linearGradient id="nTrail" x1="0" x2="1"><stop offset="0" stop-color="${accent}"/><stop offset="1" stop-color="${accent}" stop-opacity="0"/></linearGradient>
    <radialGradient id="nGlow"><stop offset="0" stop-color="${accent}" stop-opacity=".35"/><stop offset="1" stop-color="${accent}" stop-opacity="0"/></radialGradient>
  </defs>
  <ellipse cx="150" cy="540" rx="100" ry="13" fill="#000" opacity=".6"/>
  <g transform="translate(0 ${bob.toFixed(2)})">
    <!-- legs + boots -->
    <rect x="108" y="410" width="32" height="110" rx="14" fill="#2a2140"/>
    <rect x="160" y="410" width="32" height="110" rx="14" fill="#2a2140"/>
    <rect x="98" y="502" width="50" height="28" rx="12" fill="${accent}"/>
    <rect x="152" y="502" width="50" height="28" rx="12" fill="${accent}"/>
    <!-- jacket with collar and badge -->
    <path d="M80 300 Q80 248 150 248 Q220 248 220 300 L224 420 Q150 440 76 420 Z" fill="url(#nBody)"/>
    <path d="M118 252 L150 290 L182 252" fill="none" stroke="#f5f3ff" stroke-width="6" stroke-linejoin="round"/>
    <circle cx="186" cy="330" r="13" fill="none" stroke="${accent}" stroke-width="4"/>
    <path d="M181 330 l4 4 l7 -8" fill="none" stroke="${accent}" stroke-width="4" stroke-linecap="round"/>
    <!-- left arm with holo-card -->
    <rect x="48" y="272" width="38" height="118" rx="19" fill="#31274a"/>
    <g transform="rotate(-6 66 392)">
      <rect x="22" y="352" width="96" height="70" rx="12" fill="${accent}" opacity=".18" stroke="${accent}" stroke-width="3"/>
      <rect x="34" y="366" width="56" height="8" rx="4" fill="${accent}"/>
      <rect x="34" y="382" width="40" height="7" rx="3.5" fill="#a89cc8"/>
      <rect x="34" y="396" width="64" height="7" rx="3.5" fill="#a89cc8"/>
    </g>
    <!-- right arm (waves) -->
    <g transform="rotate(${(-wave).toFixed(2)} 232 284)">
      <rect x="214" y="272" width="38" height="118" rx="19" fill="#31274a"/>
      <circle cx="233" cy="392" r="19" fill="#ede9fe"/>
    </g>
    <rect x="134" y="226" width="32" height="30" rx="8" fill="#b7aecd"/>
    <g transform="rotate(${tilt.toFixed(2)} 150 160)">
      <circle cx="150" cy="150" r="125" fill="url(#nGlow)"/>
      <!-- light-trail ponytail -->
      <path d="M214 92 Q270 ${(110 + sway).toFixed(1)} 262 ${(200 + sway).toFixed(1)}" fill="none" stroke="url(#nTrail)" stroke-width="22" stroke-linecap="round"/>
      <circle cx="214" cy="92" r="16" fill="${accent}"/>
      <!-- head shell -->
      <path d="M64 150 Q64 70 150 70 Q236 70 236 150 L236 182 Q236 232 150 232 Q64 232 64 182 Z" fill="url(#nHead)"/>
      <!-- fringe panel -->
      <path d="M70 128 Q90 72 150 70 Q196 72 222 104 Q170 92 128 116 Q100 132 70 128 Z" fill="#3b2f4f"/>
      <!-- visor -->
      <rect x="86" y="130" width="128" height="78" rx="34" fill="#120e1a"/>
      <g fill="${accent}">
        <ellipse cx="122" cy="162" rx="13" ry="${(14 * blink).toFixed(1)}"/>
        <ellipse cx="178" cy="162" rx="13" ry="${(14 * blink).toFixed(1)}"/>
        <path d="M106 ${(146 + 4 * (1 - blink)).toFixed(1)} l8 -6 M194 ${(146 + 4 * (1 - blink)).toFixed(1)} l-8 -6" stroke="${accent}" stroke-width="4" stroke-linecap="round"/>
        <ellipse cx="150" cy="${(190 + open * 2).toFixed(1)}" rx="${(12 - open * 2).toFixed(1)}" ry="${(2.5 + open * 7).toFixed(1)}" opacity=".95"/>
      </g>
      <circle cx="104" cy="186" r="6" fill="#f472b6" opacity=".45"/>
      <circle cx="196" cy="186" r="6" fill="#f472b6" opacity=".45"/>
      <!-- headset -->
      <path d="M62 150 Q62 52 150 52 Q238 52 238 150" fill="none" stroke="#2a2140" stroke-width="10"/>
      <rect x="44" y="132" width="26" height="54" rx="12" fill="#2a2140"/>
      <rect x="230" y="132" width="26" height="54" rx="12" fill="#2a2140"/>
      <path d="M58 182 Q66 222 112 214" fill="none" stroke="#2a2140" stroke-width="6" stroke-linecap="round"/>
      <circle cx="114" cy="213" r="7" fill="${accent}"/>
    </g>
  </g>
</svg>`;
}
