import type { Interval } from "../types";

/** A value on a 0-100% track with its 95% interval drawn behind it. */
export default function RangeBar({ value, interval }: { value: number; interval: Interval | null }) {
  return (
    <span className="range" aria-hidden="true">
      {interval && (
        <span
          className="range__ci"
          style={{ left: `${interval.low * 100}%`, width: `${Math.max(0.5, (interval.high - interval.low) * 100)}%` }}
        />
      )}
      <span className="range__dot" style={{ left: `${value * 100}%` }} />
    </span>
  );
}
