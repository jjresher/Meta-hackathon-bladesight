import type { Trend, TurbineStatus, Verdict } from "../types";
import { ToneGlyph, TrendIcon, type Tone } from "./icons";

function Chip({ tone, label, small, title }: { tone: Tone; label: string; small?: boolean; title?: string }) {
  return (
    <span className={`chip chip--${tone}${small ? " chip--sm" : ""}`} data-tone={tone} title={title}>
      <ToneGlyph tone={tone} size={small ? 11 : 12} />
      {label}
    </span>
  );
}

const VERDICT: Record<Verdict, { tone: Tone; label: string; title: string }> = {
  ok: { tone: "ok", label: "Verified", title: "Both looks agree and the rule checks passed" },
  needs_review: { tone: "review", label: "Needs review", title: "A person should look at this defect" },
  reinspect: { tone: "alert", label: "Reinspect", title: "Take new photos before deciding" },
};

/** Verdict of the verification step. Shape, text and colour all carry the value. */
export function VerdictChip({ verdict, small }: { verdict: Verdict; small?: boolean }) {
  const { tone, label, title } = VERDICT[verdict];
  return <Chip tone={tone} label={label} title={title} small={small} />;
}

const TURBINE: Record<TurbineStatus, { tone: Tone; label: string }> = {
  critical: { tone: "alert", label: "Critical" },
  attention: { tone: "review", label: "Attention" },
  needs_review: { tone: "review", label: "Needs review" },
  ok: { tone: "ok", label: "No verified issue" },
};

export function TurbineStatusChip({ status, small }: { status: TurbineStatus; small?: boolean }) {
  const { tone, label } = TURBINE[status];
  return <Chip tone={tone} label={label} small={small} />;
}

const TREND_LABEL: Record<Trend, string> = {
  worse: "Worse",
  same: "Unchanged",
  better: "Better",
  new: "New",
};

/** Change of the latest inspection against the previous one (synthetic 2017/2018 grouping). */
export function TrendBadge({ trend }: { trend: Trend }) {
  return (
    <span className={`trend trend--${trend}`}>
      <TrendIcon trend={trend} />
      {TREND_LABEL[trend]}
    </span>
  );
}
