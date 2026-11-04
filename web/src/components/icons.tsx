/**
 * Small inline-SVG icon set (issue #13). Keeping icons inline avoids bundling
 * any raster assets (AGENTS.md rule 2) and lets status glyphs double as a
 * non-color status cue.
 */
import type { Verdict } from "../types";

interface IconProps {
  size?: number;
  className?: string;
}

/** A distinct glyph per verdict so status is conveyed by shape, not color. */
export function VerdictGlyph({ verdict, size = 12 }: { verdict: Verdict; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 12 12",
    "aria-hidden": true,
    focusable: false,
    className: "chip__glyph",
  } as const;

  if (verdict === "ok") {
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
  if (verdict === "needs_review") {
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
  // reinspect: warning triangle.
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
