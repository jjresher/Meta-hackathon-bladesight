import type { ThresholdPoint } from "../types";

/**
 * Precision/recall-vs-threshold curve drawn as inline SVG (AGENTS.md rule 2:
 * no committed chart image). Two polylines over a shared x axis of detection
 * thresholds, with gridlines, axis ticks and point markers.
 */
const W = 640;
const H = 320;
const PAD = { top: 16, right: 16, bottom: 40, left: 44 };

export default function ThresholdCurve({ points }: { points: ThresholdPoint[] }) {
  if (points.length === 0) {
    return <p className="state">No threshold data available.</p>;
  }

  const sorted = [...points].sort((a, b) => a.threshold - b.threshold);
  const xs = sorted.map((p) => p.threshold);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const sx = (t: number) =>
    PAD.left + (maxX === minX ? plotW / 2 : ((t - minX) / (maxX - minX)) * plotW);
  const sy = (v: number) => PAD.top + (1 - v) * plotH;

  const line = (key: "precision" | "recall") =>
    sorted.map((p) => `${sx(p.threshold).toFixed(1)},${sy(p[key]).toFixed(1)}`).join(" ");

  const yTicks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div>
      <svg
        className="curve__svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Precision and recall as a function of the detection score threshold"
        data-testid="threshold-curve"
      >
        {/* Y gridlines + labels */}
        {yTicks.map((v) => (
          <g key={`y-${v}`}>
            <line
              x1={PAD.left}
              y1={sy(v)}
              x2={W - PAD.right}
              y2={sy(v)}
              stroke="var(--border)"
              strokeWidth="1"
            />
            <text
              x={PAD.left - 8}
              y={sy(v) + 4}
              fill="var(--text-faint)"
              fontSize="11"
              textAnchor="end"
              fontFamily="ui-monospace, monospace"
            >
              {v.toFixed(2)}
            </text>
          </g>
        ))}

        {/* X ticks + labels */}
        {sorted.map((p) => (
          <g key={`x-${p.threshold}`}>
            <line
              x1={sx(p.threshold)}
              y1={H - PAD.bottom}
              x2={sx(p.threshold)}
              y2={H - PAD.bottom + 5}
              stroke="var(--border-strong)"
              strokeWidth="1"
            />
            <text
              x={sx(p.threshold)}
              y={H - PAD.bottom + 18}
              fill="var(--text-faint)"
              fontSize="11"
              textAnchor="middle"
              fontFamily="ui-monospace, monospace"
            >
              {p.threshold.toFixed(1)}
            </text>
          </g>
        ))}

        {/* Axis titles */}
        <text
          x={PAD.left + plotW / 2}
          y={H - 4}
          fill="var(--text-dim)"
          fontSize="12"
          textAnchor="middle"
        >
          Detection score threshold
        </text>

        {/* Precision line (accent) */}
        <polyline
          points={line("precision")}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {/* Recall line (review amber) */}
        <polyline
          points={line("recall")}
          fill="none"
          stroke="var(--review)"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          strokeDasharray="7 4"
        />

        {/* Point markers */}
        {sorted.map((p) => (
          <g key={`pt-${p.threshold}`}>
            <circle cx={sx(p.threshold)} cy={sy(p.precision)} r="3.5" fill="var(--accent)" />
            <circle cx={sx(p.threshold)} cy={sy(p.recall)} r="3.5" fill="var(--review)" />
          </g>
        ))}
      </svg>

      <div className="curve__legend">
        <span>
          <span className="swatch-line" style={{ background: "var(--accent)" }} />
          Precision
        </span>
        <span>
          <span
            className="swatch-line"
            style={{
              background:
                "repeating-linear-gradient(90deg, var(--review) 0 7px, transparent 7px 11px)",
            }}
          />
          Recall
        </span>
      </div>
    </div>
  );
}
