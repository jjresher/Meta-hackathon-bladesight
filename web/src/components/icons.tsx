/**
 * Small inline-SVG icon set (issue #13). Keeping icons inline avoids bundling
 * any raster assets (AGENTS.md rule 2) and lets status glyphs double as a
 * non-color status cue.
 */

interface IconProps {
  size?: number;
  className?: string;
}

export type Tone = "ok" | "review" | "alert";

/** A distinct glyph per tone so status is conveyed by shape, not color. */
export function ToneGlyph({ tone, size = 12 }: { tone: Tone; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 12 12",
    "aria-hidden": true,
    focusable: false,
    className: "chip__glyph",
  } as const;

  if (tone === "ok") {
    // Check mark.
    return (
      <svg {...common}>
        <path
          d="M2.5 6.5 L5 9 L9.5 3"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (tone === "review") {
    // Diamond with a query stroke.
    return (
      <svg {...common}>
        <path
          d="M6 1 L11 6 L6 11 L1 6 Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
        <circle cx="6" cy="6" r="1.1" fill="currentColor" />
      </svg>
    );
  }
  // alert: warning triangle.
  return (
    <svg {...common}>
      <path
        d="M6 1.2 L11 10.5 L1 10.5 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M6 4.5 V7.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="6" cy="9" r="0.8" fill="currentColor" />
    </svg>
  );
}

export function InfoIcon({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="8" cy="4.6" r="0.95" fill="currentColor" />
      <path d="M8 7 V11.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function ArrowLeftIcon({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <path
        d="M9.5 3.5 L5 8 L9.5 12.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M5 8 H13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

/** The BladeSight brand mark: a stylized three-blade rotor. */
export function BrandMark({ size = 34 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 34 34"
      aria-hidden="true"
      focusable="false"
      className="app-brand__mark"
    >
      <rect width="34" height="34" rx="7" fill="var(--accent)" />
      <g transform="translate(17 17)" fill="var(--accent-ink)">
        <circle r="2.4" />
        <g>
          <path d="M0 -2 C 1.2 -7 1 -10.5 0 -12.5 C -1 -10.5 -1.2 -7 0 -2 Z" />
          <path d="M0 -2 C 1.2 -7 1 -10.5 0 -12.5 C -1 -10.5 -1.2 -7 0 -2 Z" transform="rotate(120)" />
          <path d="M0 -2 C 1.2 -7 1 -10.5 0 -12.5 C -1 -10.5 -1.2 -7 0 -2 Z" transform="rotate(240)" />
        </g>
      </g>
    </svg>
  );
}

export function ImageOffIcon({ size = 28, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3 16 L8.5 11 L13 15 L16 12.5 L21 17" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M4 3 L20 21" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}


export function TrendIcon({ trend, size = 12 }: { trend: "worse" | "same" | "better" | "new"; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 12 12", "aria-hidden": true, focusable: false } as const;
  const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" } as const;
  if (trend === "worse") return <svg {...common}><path d="M2 9 L6 3 L10 9" {...stroke} /></svg>;
  if (trend === "better") return <svg {...common}><path d="M2 3 L6 9 L10 3" {...stroke} /></svg>;
  if (trend === "new") return <svg {...common}><path d="M6 2 V10 M2 6 H10" {...stroke} /></svg>;
  return <svg {...common}><path d="M2 6 H10" {...stroke} /></svg>;
}
