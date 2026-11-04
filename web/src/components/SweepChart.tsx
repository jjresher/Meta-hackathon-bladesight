import type { SweepPoint } from "../types";

const W = 640;
const H = 300;
const M = { top: 16, right: 76, bottom: 40, left: 46 };

/**
 * Recall and precision of the damage class against the SAM score threshold (the dev sweep).
 * Drawn as inline SVG so it has no dependency; the same numbers are listed in the table under it.
 */
export default function SweepChart({ points }: { points: SweepPoint[] }) {
  if (points.length === 0) return null;
  const xMax = Math.max(1, ...points.map((p) => p.threshold));
  const x = (t: number) => M.left + (t / xMax) * (W - M.left - M.right);
  const y = (v: number) => H - M.bottom - v * (H - M.top - M.bottom);
  const line = (pick: (p: SweepPoint) => number) =>
    points.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.threshold).toFixed(1)} ${y(pick(p)).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];

  return (
    <svg
      className="sweep"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Recall and precision of the damage class by score threshold"
      data-testid="sweep-chart"
    >
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} className="sweep__grid" />
          <text x={M.left - 8} y={y(v) + 4} textAnchor="end" className="sweep__tick">
            {Math.round(v * 100)}%
          </text>
        </g>
      ))}
      {points.map((p) => (
        <text key={p.threshold} x={x(p.threshold)} y={H - M.bottom + 18} textAnchor="middle" className="sweep__tick">
          {p.threshold}
        </text>
      ))}
      <text x={(M.left + W - M.right) / 2} y={H - 4} textAnchor="middle" className="sweep__axis">
        SAM score threshold
      </text>

      <path d={line((p) => p.precision)} className="sweep__line sweep__line--precision" />
      <path d={line((p) => p.recall)} className="sweep__line sweep__line--recall" />
      {points.map((p) => (
        <g key={p.threshold}>
          <circle cx={x(p.threshold)} cy={y(p.precision)} r="3.5" className="sweep__dot sweep__dot--precision" />
          <circle cx={x(p.threshold)} cy={y(p.recall)} r="3.5" className="sweep__dot sweep__dot--recall" />
        </g>
      ))}
      <text x={x(last.threshold) + 10} y={y(last.precision) + 4} className="sweep__label sweep__label--precision">
        precision
      </text>
      <text x={x(last.threshold) + 10} y={y(last.recall) + 4} className="sweep__label sweep__label--recall">
        recall
      </text>
    </svg>
  );
}
