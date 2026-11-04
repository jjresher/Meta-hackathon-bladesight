/**
 * Numbers that no API endpoint carries yet, copied from their evidence file. Every value here is
 * checked against the file by `src/evidence.test.ts`, so it cannot drift (AGENTS.md rule 5).
 */
export const EVIDENCE_BASE_URL =
  "https://github.com/jjresher/Meta-hackathon-bladesight/blob/main/";

export const SEVERITY_AGREEMENT = {
  file: "docs/evidence/severity_agreement.md",
  crops: 40,
  /** Quadratic weighted kappa, model vs one non-specialist applying docs/rubric.md. */
  kappa: 0.12,
  kappaLow: -0.05,
  kappaHigh: 0.29,
  exactAgreementPct: 25,
  withinOnePct: 48,
  modelGradedOne: 29,
  humanGradedOne: 10,
  meanModelMinusHuman: -1.3,
} as const;

/** Damage class: tiles with no dataset box that still got a damage prediction, per split. */
export const FALSE_ALARM_RATE = {
  dev: { file: "docs/evidence/eval_dev.md", rate: 0.21, cleanTiles: 100 },
  heldout: { file: "docs/evidence/eval_heldout.md", rate: 0.24, cleanTiles: 300 },
} as const;

/**
 * Detection v2, the detector the demo runs: measured on a preregistered fresh dev set after the
 * held-out run, never on the held-out split. The detection numbers on this page measure v1.
 */
export const DETECTOR_V2 = {
  file: "docs/evidence/eval_fresh_v2.md",
  tiles: 300,
  f1V1: 0.224,
  f1V2: 0.25,
  falseAlarm: 0.21,
} as const;

export const evidenceUrl = (path: string): string => `${EVIDENCE_BASE_URL}${path}`;

/**
 * Muse Spark (Model API) vs Muse Spark Open (Baseten) on the same stored detections of the farm:
 * agreement between two models, not accuracy (neither run is a reference).
 */
export const OPEN_WEIGHTS_FARM = {
  file: "docs/evidence/open_weights_farm.md",
  defects: 98,
  sameSeverity: 78,
  sameSeverityPct: 80,
  withinOne: 89,
  withinOnePct: 91,
  sameVerdict: 64,
  sameVerdictPct: 65,
  /** Verdict counts per run. */
  verdicts: {
    meta: { ok: 35, needs_review: 50, reinspect: 13 },
    baseten: { ok: 25, needs_review: 59, reinspect: 14 },
  },
  /** Rows: Meta verdict ok / needs_review / reinspect; columns: Open verdict, same order. */
  verdictMatrix: [
    [18, 13, 4],
    [4, 41, 5],
    [3, 5, 5],
  ],
  turbines: 12,
  spearman: 0.62,
  topSixInBoth: 4,
  orders: { meta: 11, baseten: 9, metaRun: "run-final", openRun: "run-open-weights" },
  repairDefects: { both: 2, union: 7, meta: 6, baseten: 3 },
  reinspectDefects: { both: 14, union: 27, meta: 19, baseten: 22 },
} as const;

/**
 * The rules the agent's tools enforce in code (`src/bladesight/fleet/rules.py`, stable ids). No
 * endpoint lists them; `src/evidence.test.ts` checks this copy against the source.
 */
export const GUARD_RULES = {
  file: "src/bladesight/fleet/rules.py",
  rules: [
    { id: "verified_only", text: "A repair or monitor work order may only cite defects whose verification verdict is ok." },
    { id: "reinspect_unverified_only", text: "Re-inspection is only for defects that are not verified; verified ones get a work order." },
    { id: "assessed_before_reinspection", text: "A defect must have been assessed before a re-inspection can be requested." },
    { id: "defects_in_inspection", text: "Every cited defect must exist in the named inspection." },
    { id: "cite_a_defect", text: "Every order cites at least one defect id." },
    { id: "order_kind", text: "A work order is a repair or a monitor order; anything else is a re-inspection." },
    { id: "order_priority", text: "Priority is P1, P2 or P3." },
    { id: "report_cites_existing_orders", text: "The report may only cite work orders that exist." },
    { id: "report_cites_assessed_defects", text: "The report may only cite defects that were assessed and verified." },
    { id: "two_inspections_to_compare", text: "A comparison needs two inspections of the turbine." },
    { id: "known_image", text: "Image ids must exist in the store." },
    { id: "known_tool", text: "Only the seven fleet tools exist." },
    { id: "known_ids", text: "Inspection and defect ids must exist, and required arguments must be given." },
    { id: "valid_arguments", text: "Arguments must have the documented types." },
  ],
} as const;
