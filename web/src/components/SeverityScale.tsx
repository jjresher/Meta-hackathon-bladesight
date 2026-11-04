/**
 * Severity on the 1-5 rubric as five pips plus "N / 5". A missing severity (the assessment
 * failed or the defect was never graded) shows an explicit dash, never a made-up number.
 */
export default function SeverityScale({ value }: { value: number | null | undefined }) {
  if (value == null) {
    return (
      <span className="sev sev--none">
        <span className="sev__label">not graded</span>
      </span>
    );
  }
  return (
    <span className="sev">
      <span className="sev__pips" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((pip) => (
          <span key={pip} className={`sev__pip${pip <= value ? ` sev__pip--on sev__pip--s${value}` : ""}`} />
        ))}
      </span>
      <span className="sev__label">{value} / 5</span>
      <span className="visually-hidden">severity {value} of 5</span>
    </span>
  );
}
