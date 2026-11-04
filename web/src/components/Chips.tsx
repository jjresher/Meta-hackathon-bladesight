import type { Provider, Trend, TurbineStatus, Verdict } from "../types";
import { PROVIDER_LABEL, modelLabel } from "../lib/models";
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
  ok: { tone: "ok", label: "Verified", title: "Both looks agreed, confidence was high enough and the rule checks passed" },
  needs_review: { tone: "review", label: "Needs review", title: "A person should look at this defect" },
  reinspect: { tone: "alert", label: "Reinspect", title: "Take new photos before deciding" },
};

/** Verdict of the verification step. Shape, text and colour all carry the value. */
export function VerdictChip({ verdict, small }: { verdict: Verdict; small?: boolean }) {
  const { tone, label, title } = VERDICT[verdict];
  return <Chip tone={tone} label={label} title={title} small={small} />;
}

/**
 * A defect with no verification result (a stage failed, so the second look never ran). The "?"
 * matches the glyph on its overlay; it means "not checked", never "probably fine".
 */
export function UnverifiedChip({ small }: { small?: boolean }) {
  return (
    <span
      className={`chip chip--none${small ? " chip--sm" : ""}`}
      title="Not checked: the verification step did not run for this defect"
    >
      <span className="chip__q" aria-hidden="true">
        ?
      </span>
      Unverified
    </span>
  );
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

/**
 * Which model produced something (an assessment, a second look, a work order, a trace step), from
 * its own `model` / `provider` fields; the exact model id is in the title. Nothing when unknown.
 */
export function ModelBadge({
  model,
  provider,
  prefix,
}: {
  model: string | null | undefined;
  provider: Provider | null | undefined;
  prefix?: string;
}) {
  if (!model) return null;
  return (
    <span
      className={`model-badge model-badge--${provider ?? "unknown"}`}
      title={`${prefix ? `${prefix} ` : ""}${model}${provider ? ` via ${PROVIDER_LABEL[provider]}` : ""}`}
      data-testid="model-badge"
    >
      {prefix && <span className="model-badge__prefix">{prefix} </span>}
      {modelLabel(model, provider)}
    </span>
  );
}
