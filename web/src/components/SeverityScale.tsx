import type { Severity } from "../types";

/**
 * Severity rendered as a 1-5 pip scale (filled pips = severity) plus a text
 * value. Like the status chip, it does not rely on color alone: the count of
 * filled pips and the "N / 5" label both carry the value.
 */
export default function SeverityScale({ value }: { value: Severity }) {
  return (
    <span className="sev">
      <span className="sev__pips" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((pip) => {
          const on = pip <= value;
          return (
            <span
              key={pip}
              className={`sev__pip${on ? ` sev__pip--on sev__pip--s${value}` : ""}`}
            />
          );
        })}
      </span>
      <span className="sev__label">{value} / 5</span>
      <span className="visually-hidden">severity {value} of 5</span>
    </span>
  );
}
