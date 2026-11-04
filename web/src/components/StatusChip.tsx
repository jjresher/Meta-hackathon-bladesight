import type { Verdict } from "../types";
import { VerdictGlyph } from "./icons";

const LABELS: Record<Verdict, string> = {
  ok: "OK",
  needs_review: "Needs review",
  reinspect: "Reinspect",
};

interface StatusChipProps {
  status: Verdict;
  /** Compact variant used inside dense table rows. */
  small?: boolean;
}

/**
 * Accessible status chip. Status is conveyed by THREE independent cues so it is
 * never color alone: a text label, a distinct shape glyph, and (secondarily)
 * color. Reused by the fleet, work orders and defect cards.
 */
export default function StatusChip({ status, small = false }: StatusChipProps) {
  return (
    <span
      className={`chip chip--${status}${small ? " chip--sm" : ""}`}
      data-testid="status-chip"
      data-status={status}
    >
      <VerdictGlyph verdict={status} size={small ? 11 : 12} />
      {LABELS[status]}
    </span>
  );
}
