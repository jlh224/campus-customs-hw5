import type { CSSProperties } from "react";
import type { AgentName } from "../types";

/**
 * Handsome Dan, our own mascot drawing (not Yale's logo): determined brow,
 * brindle eye patch, droopy jowls, underbite fangs, and a spiked collar.
 *
 *   <Dan badge />            varsity badge (the brand logo)
 *   <Dan outfit="boss" />    free-standing, in an agent's headgear (seats, log, reports)
 *   <Dan outfit=... mono />  one ink color, for rubber stamps
 *
 * Headgear: Boss top hat · Inventory delivery cap · Accounting green eyeshade
 * · Facilities hard hat · Customer Service headset.
 */
const INK = "#1e1714";
const VINTAGE = { badge: "#00356b", ring: "#ffffff", collar: "#286dc0", fur: "#f7f0e2", patch: "#c39363", ear: "#4a3326" };

export function Dan({ outfit, mono = false, badge = false, size = 64, title }: {
  outfit?: AgentName;
  mono?: boolean;
  badge?: boolean;
  size?: number;
  title?: string;
}) {
  // In stamp (mono) mode every shape is paper-colored with ink outlines.
  const stamp: CSSProperties = { fill: "var(--stamp-paper, #fff)" };
  const f = (color: string): { fill?: string; style?: CSSProperties } => (mono ? { style: stamp } : { fill: color });
  const ink = mono ? "currentColor" : INK;
  const sw = mono ? 3.4 : 3; // stamps read better with slightly heavier lines

  return (
    <svg width={size} height={size} viewBox="0 0 120 120" role="img" aria-label={title ?? "Handsome Dan"}>
      {title && <title>{title}</title>}
      {badge && !mono && (
        <>
          <circle cx="60" cy="60" r="57" fill={VINTAGE.badge} />
          <circle cx="60" cy="60" r="52" fill="none" stroke={VINTAGE.ring} strokeWidth="2.5" />
        </>
      )}
      {/* rose ears */}
      <path d="M27 38 C15 30 16 15 33 21 C38 27 35 34 27 38 Z" {...f(VINTAGE.ear)} stroke={ink} strokeWidth={sw} strokeLinejoin="round" />
      <path d="M93 38 C105 30 104 15 87 21 C82 27 85 34 93 38 Z" {...f(VINTAGE.ear)} stroke={ink} strokeWidth={sw} strokeLinejoin="round" />
      {/* head */}
      <path d="M60 22 C86 22 100 36 101 56 C102 70 97 80 90 86 L30 86 C23 80 18 70 19 56 C20 36 34 22 60 22 Z"
        {...f(VINTAGE.fur)} stroke={ink} strokeWidth={sw + 0.2} />
      {/* brindle patch */}
      {!mono && <path d="M68 33 C82 30 93 40 91 54 C85 58 75 56 70 50 C67 45 66 38 68 33 Z" fill={VINTAGE.patch} />}
      {mono && <path d="M68 33 C82 30 93 40 91 54 C85 58 75 56 70 50 C67 45 66 38 68 33 Z" fill="none" stroke={ink} strokeWidth="1.6" strokeDasharray="3 2.5" />}
      {/* brow wrinkles */}
      <path d="M51 32 Q60 28 69 32" fill="none" stroke={ink} strokeWidth="2" strokeLinecap="round" opacity={mono ? 1 : 0.5} />
      <path d="M54 37 Q60 34.5 66 37" fill="none" stroke={ink} strokeWidth="2" strokeLinecap="round" opacity={mono ? 1 : 0.5} />
      {/* eyes + determined brows */}
      <ellipse cx="45" cy="51" rx="7" ry="6.5" {...f("#fff")} stroke={ink} strokeWidth="2" />
      <ellipse cx="75" cy="51" rx="7" ry="6.5" {...f("#fff")} stroke={ink} strokeWidth="2" />
      <circle cx="46" cy="50.5" r="3.8" fill={ink} />
      <circle cx="74" cy="50.5" r="3.8" fill={ink} />
      {!mono && <circle cx="47.4" cy="48.9" r="1.4" fill="#fff" />}
      {!mono && <circle cx="75.4" cy="48.9" r="1.4" fill="#fff" />}
      <path d="M37 41 Q45 36.5 53 40.5" fill="none" stroke={ink} strokeWidth="3.6" strokeLinecap="round" />
      <path d="M67 42.5 Q75 40 83 43" fill="none" stroke={ink} strokeWidth="3.6" strokeLinecap="round" />
      {/* jowls */}
      <path d="M60 68 C46 62 25 66 24 81 C23 94 42 100 60 95 Z" {...f("#fffaf2")} stroke={ink} strokeWidth={sw} strokeLinejoin="round" />
      <path d="M60 68 C74 62 95 66 96 81 C97 94 78 100 60 95 Z" {...f("#fffaf2")} stroke={ink} strokeWidth={sw} strokeLinejoin="round" />
      {/* underbite + fangs */}
      <path d="M41 89 Q60 110 79 89 Q73 104 60 105 Q47 104 41 89 Z" fill={mono ? "currentColor" : "#7a2232"} stroke={ink} strokeWidth="2.6" strokeLinejoin="round" />
      {!mono && <path d="M52 100 Q60 96 68 100 Q64 105 60 105 Q56 105 52 100 Z" fill="#e8798a" />}
      <path d="M47 97 Q45.5 91.5 43.6 86.2 Q45.2 85.4 46.4 86.4 Q50.5 90.5 53.4 97.6 Z" {...f("#fff")} stroke={ink} strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M73 97 Q74.5 91.5 76.4 86.2 Q74.8 85.4 73.6 86.4 Q69.5 90.5 66.6 97.6 Z" {...f("#fff")} stroke={ink} strokeWidth="1.8" strokeLinejoin="round" />
      {/* nose */}
      <path d="M48 63 C48 55 72 55 72 63 C72 69 66 72 60 72 C54 72 48 69 48 63 Z" fill={ink} />
      {!mono && <ellipse cx="54.5" cy="60.5" rx="3.2" ry="1.8" fill="#fff" opacity=".55" />}
      {/* spiked collar */}
      <path d="M32 100 Q60 114 88 100 L90 108 Q60 123 30 108 Z" {...f(VINTAGE.collar)} stroke={ink} strokeWidth="2.6" strokeLinejoin="round" />
      <circle cx="45" cy="108" r="2.2" {...f("#e8e2d6")} stroke={ink} />
      <circle cx="60" cy="112" r="2.2" {...f("#e8e2d6")} stroke={ink} />
      <circle cx="75" cy="108" r="2.2" {...f("#e8e2d6")} stroke={ink} />

      {outfit === "boss" && (
        <g>
          <rect x="40" y="2" width="40" height="22" rx="2" {...f("#1c1714")} stroke={ink} strokeWidth="2.5" />
          <rect x="40" y="16" width="40" height="5" fill={mono ? "currentColor" : "#286dc0"} />
          <rect x="28" y="22" width="64" height="6" rx="3" {...f("#1c1714")} stroke={ink} strokeWidth="2.5" />
        </g>
      )}
      {outfit === "inventory" && (
        <g>
          <path d="M30 33 Q31 9 60 9 Q89 9 90 33 Z" {...f("#7b5534")} stroke={ink} strokeWidth="2.6" />
          <path d="M84 31 Q104 28 112 36 Q98 40 82 37 Z" {...f("#5e3f24")} stroke={ink} strokeWidth="2.6" strokeLinejoin="round" />
          <rect x="52" y="15" width="16" height="10" rx="2" {...f("#d9a521")} stroke={ink} strokeWidth="2" />
        </g>
      )}
      {outfit === "accounting" && (
        <g>
          <path d="M24 36 Q60 14 96 36 L101 45 Q60 26 19 45 Z" {...f("#2f8f55")} fillOpacity={mono ? undefined : 0.9}
            stroke={ink} strokeWidth="2.6" strokeLinejoin="round" />
          <path d="M26 36 Q60 18 94 36" fill="none" stroke={mono ? ink : "#1d5e37"} strokeWidth="3" />
        </g>
      )}
      {outfit === "facilities" && (
        <g>
          <path d="M28 33 Q28 6 60 6 Q92 6 92 33 Z" {...f("#f2b705")} stroke={ink} strokeWidth="2.6" />
          <path d="M60 6 L60 32" stroke={mono ? ink : "#c99400"} strokeWidth="4" />
          <rect x="20" y="30" width="80" height="7" rx="3.5" {...f("#e0a800")} stroke={ink} strokeWidth="2.6" />
        </g>
      )}
      {outfit === "customer_service" && (
        <g>
          <path d="M20 58 Q18 14 60 12 Q102 14 100 58" fill="none" stroke={ink} strokeWidth="5" strokeLinecap="round" />
          <rect x="11" y="50" width="13" height="20" rx="5" {...f("#44607a")} stroke={ink} strokeWidth="2.6" />
          <rect x="96" y="50" width="13" height="20" rx="5" {...f("#44607a")} stroke={ink} strokeWidth="2.6" />
          <path d="M17 68 Q20 90 40 88" fill="none" stroke={ink} strokeWidth="3" strokeLinecap="round" />
          <circle cx="41" cy="88" r="4" {...f("#44607a")} stroke={ink} strokeWidth="2" />
        </g>
      )}
    </svg>
  );
}
