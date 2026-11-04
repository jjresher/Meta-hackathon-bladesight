import type { Defect, Inspection } from "../types";

interface BladeImageProps {
  inspection: Inspection;
  defects: Defect[];
  showMasks: boolean;
  showBoxes: boolean;
  /** Defect id to emphasise (hovered/active card). */
  activeId: string | null;
  onHover: (id: string | null) => void;
}

/**
 * Inline-SVG drone-image placeholder (AGENTS.md rule 2: no committed raster).
 *
 * The `imageRef` on an inspection is only a path string; we never fetch or
 * bundle the raster. Instead we draw a calm, schematic blade on a dark ground
 * as a stand-in, and overlay the real defect geometry on top:
 *   - MASKS  from `defect.maskPolygon` (flat [x0,y0,...] ring, 0..1 coords)
 *   - BOXES  from `defect.measurement.bbox` (relative 0..1)
 * Masks and boxes are toggled independently by the caller.
 *
 * The SVG uses a 0..1000 x 0..(1000/aspect) coordinate space so relative
 * defect coords map directly after scaling by the view box size.
 */
const VW = 1000;

export default function BladeImage({
  inspection,
  defects,
  showMasks,
  showBoxes,
  activeId,
  onHover,
}: BladeImageProps) {
  const aspect = inspection.imageWidth / inspection.imageHeight || 586 / 371;
  const VH = Math.round(VW / aspect);

  return (
    <svg
      className="viewer__svg"
      viewBox={`0 0 ${VW} ${VH}`}
      role="img"
      aria-label={`Schematic drone view of turbine ${inspection.turbineId}, ${inspection.year}, with ${defects.length} defect overlays`}
      data-testid="blade-image"
    >
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0c141c" />
          <stop offset="1" stopColor="#0a0f14" />
        </linearGradient>
        <linearGradient id="blade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#2b3a49" />
          <stop offset="0.5" stopColor="#3a4c5e" />
          <stop offset="1" stopColor="#263340" />
        </linearGradient>
      </defs>

      {/* Ground / sky */}
      <rect x="0" y="0" width={VW} height={VH} fill="url(#sky)" />

      {/* Schematic blade: a long tapered shape running root (left) to tip
          (right), matching the region/axialPosition convention. */}
      <g>
        <path
          d={bladePath(VW, VH)}
          fill="url(#blade)"
          stroke="#4a5e72"
          strokeWidth="1.5"
        />
        {/* Leading-edge highlight */}
        <path
          d={`M ${VW * 0.08} ${VH * 0.46} Q ${VW * 0.5} ${VH * 0.4} ${VW * 0.95} ${VH * 0.49}`}
          fill="none"
          stroke="#5a7188"
          strokeWidth="1"
          opacity="0.6"
        />
        {/* Root / mid / tip guide ticks */}
        {[
          { x: 0.1, label: "root" },
          { x: 0.5, label: "mid" },
          { x: 0.9, label: "tip" },
        ].map((g) => (
          <g key={g.label}>
            <line
              x1={VW * g.x}
              y1={VH * 0.1}
              x2={VW * g.x}
              y2={VH * 0.9}
              stroke="#1c2630"
              strokeWidth="1"
              strokeDasharray="3 5"
            />
            <text
              x={VW * g.x}
              y={VH * 0.07}
              fill="#6f8294"
              fontSize="16"
              textAnchor="middle"
              fontFamily="ui-monospace, monospace"
            >
              {g.label}
            </text>
          </g>
        ))}
      </g>

      {/* Masks layer */}
      {showMasks &&
        defects.map((d) => {
          const active = d.id === activeId;
          return (
            <polygon
              key={`mask-${d.id}`}
              points={maskPoints(d.maskPolygon, VW, VH)}
              fill="var(--accent)"
              fillOpacity={active ? 0.42 : 0.26}
              stroke="var(--accent)"
              strokeWidth={active ? 2.5 : 1.5}
              data-testid="defect-mask"
            />
          );
        })}

      {/* Boxes layer */}
      {showBoxes &&
        defects.map((d) => {
          const b = d.measurement.bbox;
          const active = d.id === activeId;
          return (
            <g
              key={`box-${d.id}`}
              onMouseEnter={() => onHover(d.id)}
              onMouseLeave={() => onHover(null)}
              style={{ cursor: "pointer" }}
            >
              <rect
                x={b.x * VW}
                y={b.y * VH}
                width={b.width * VW}
                height={b.height * VH}
                fill="none"
                stroke="var(--review)"
                strokeWidth={active ? 3 : 2}
                strokeDasharray="6 4"
                data-testid="defect-box"
              />
              <rect
                x={b.x * VW}
                y={b.y * VH - 20}
                width={Math.max(d.id.length * 7.2, 40)}
                height={18}
                fill="var(--review)"
                opacity={active ? 1 : 0.85}
                rx="2"
              />
              <text
                x={b.x * VW + 5}
                y={b.y * VH - 6}
                fill="#2f2510"
                fontSize="13"
                fontFamily="ui-monospace, monospace"
                fontWeight="700"
              >
                {d.id.replace(/^D-/, "")}
              </text>
            </g>
          );
        })}
    </svg>
  );
}

/** A tapered blade outline from root (left, wide) to tip (right, narrow). */
function bladePath(w: number, h: number): string {
  const cy = h * 0.52;
  return [
    `M ${w * 0.06} ${cy - h * 0.1}`,
    `Q ${w * 0.03} ${cy} ${w * 0.08} ${cy + h * 0.1}`,
    `L ${w * 0.5} ${cy + h * 0.05}`,
    `Q ${w * 0.8} ${cy + h * 0.03} ${w * 0.97} ${cy + h * 0.008}`,
    `Q ${w * 0.99} ${cy} ${w * 0.97} ${cy - h * 0.008}`,
    `Q ${w * 0.8} ${cy - h * 0.04} ${w * 0.5} ${cy - h * 0.06}`,
    "Z",
  ].join(" ");
}

/** Map a flat relative polygon ring to an SVG points string. */
function maskPoints(poly: number[], w: number, h: number): string {
  const pts: string[] = [];
  for (let i = 0; i + 1 < poly.length; i += 2) {
    pts.push(`${(poly[i] * w).toFixed(1)},${(poly[i + 1] * h).toFixed(1)}`);
  }
  return pts.join(" ");
}
