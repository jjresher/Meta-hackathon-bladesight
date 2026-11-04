import type { Provider, StageModel } from "../types";

/** Where a model ran. The one label map for providers in the UI. */
export const PROVIDER_LABEL: Record<Provider, string> = {
  meta: "Meta Model API",
  baseten: "Baseten, open weights",
  stub: "stub (no real model)",
};

/**
 * Display name of a model: "Muse Spark (Model API)" / "Muse Spark Open (Baseten)" for Muse Spark,
 * "SAM 3.1 (Model API)" for SAM; anything else falls back to the raw model id.
 */
export function modelLabel(model: string | null | undefined, provider: Provider | null | undefined): string {
  const id = (model ?? "").toLowerCase();
  if (!id) return "unknown model";
  if (provider === "stub") return `${model} (stub)`;
  if (id.includes("muse-spark-open")) return "Muse Spark Open (Baseten)";
  if (id.startsWith("muse-spark") && provider === "meta") return "Muse Spark (Model API)";
  if (id.startsWith("sam-3.1") && provider === "meta") return "SAM 3.1 (Model API)";
  return model as string;
}

export const STAGE_LABEL: Record<StageModel["stage"], string> = {
  detection_proposals: "detection proposals",
  segmentation: "segmentation",
  severity: "severity",
  verification: "second look",
  agent: "agent and report",
};

/** Short stage names for the run bar. */
export const STAGE_SHORT: Record<StageModel["stage"], string> = {
  detection_proposals: "detection",
  segmentation: "masks",
  severity: "severity",
  verification: "second look",
  agent: "agent",
};

/** Stages grouped by the model that ran them, in pipeline order: [label, stage names][]. */
export function stagesByModel(stages: StageModel[], names = STAGE_LABEL): [string, string[]][] {
  const groups = new Map<string, string[]>();
  for (const s of stages) {
    const label = modelLabel(s.model, s.provider);
    groups.set(label, [...(groups.get(label) ?? []), names[s.stage]]);
  }
  return [...groups.entries()];
}
