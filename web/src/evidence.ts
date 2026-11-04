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

export const evidenceUrl = (path: string): string => `${EVIDENCE_BASE_URL}${path}`;
