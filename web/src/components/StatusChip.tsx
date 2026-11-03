import type { Verdict } from "../types";

const LABELS: Record<Verdict, string> = {
  ok: "OK",
  needs_review: "Needs review",
  reinspect: "Reinspect",
};

/** Accessible status chip reused by the fleet, work orders and defect cards. */
export default function StatusChip({ status }: { status: Verdict }) {
  return (
    <span className={`chip chip--${status}`} data-testid="status-chip">
      {LABELS[status]}
    </span>
  );
}
