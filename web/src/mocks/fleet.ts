/**
 * Internally consistent placeholder data for the BladeSight UI (issue #13).
 *
 * This is a stand-in until the backend agent commits generated fixtures to
 * `web/src/fixtures/*.json`. It is NOT real evidence: it is hand-written mock
 * data shaped to the `FleetDataset` contract so the five screens can be built
 * and demoed. Honest provenance labels are used throughout.
 *
 * Consistency guarantees maintained here by hand:
 *  - Turbines are ranked 1..12 by descending priority.
 *  - A turbine's `status` equals the worst verdict among its defects.
 *  - Work orders cite only defect ids that exist in the inspections.
 *  - The agent trace references real turbine and inspection ids.
 */

import type {
  AgentStep,
  Defect,
  EvalReport,
  FleetDataset,
  Inspection,
  Report,
  Severity,
  Turbine,
  Verdict,
  WorkOrder,
} from "../types";

/** Honest label: these are synthetic groupings of real DTU drone photos. */
export const FARM_LABEL = "Synthetic farm built from real DTU drone photos";

const PROVENANCE = FARM_LABEL;

/** Small helper to keep defect construction terse and consistent. */
function makeDefect(args: {
  id: string;
  concept: string;
  score: number;
  severity: Severity;
  confidence: number;
  verdict: Verdict;
  reasons: string[];
  agreement: number;
  region: "root" | "mid" | "tip";
  axialPosition: number;
  areaRatio: number;
  elongation: number;
  bbox: { x: number; y: number; width: number; height: number };
  rationale: string;
}): Defect {
  const { bbox } = args;
  return {
    id: args.id,
    concept: args.concept,
    score: args.score,
    // A simple quadrilateral ring derived from the bbox; good enough as a
    // placeholder mask until real polygons arrive in the fixtures.
    maskPolygon: [
      bbox.x,
      bbox.y,
      bbox.x + bbox.width,
      bbox.y,
      bbox.x + bbox.width,
      bbox.y + bbox.height,
      bbox.x,
      bbox.y + bbox.height,
    ],
    measurement: {
      areaRatio: args.areaRatio,
      bbox,
      elongation: args.elongation,
      region: args.region,
      axialPosition: args.axialPosition,
    },
    assessment: {
      type: args.concept,
      severity: args.severity,
      rationale: args.rationale,
      confidence: args.confidence,
      model: "muse-spark-1.3",
    },
    verification: {
      verdict: args.verdict,
      reasons: args.reasons,
      agreement: args.agreement,
    },
  };
}

// --- Inspections -----------------------------------------------------------
// Each turbine gets a 2017 and a 2018 inspection. Defect density and severity
// are tuned so the derived fleet ranking below is monotonic and sensible.

const inspections: Inspection[] = [
  // T01 — reinspect (worst): a severe tip crack with weak agreement.
  {
    id: "T01-2018",
    turbineId: "T01",
    year: 2018,
    imageRef: "/images/T01-2018.jpg",
    imageWidth: 586,
    imageHeight: 371,
    provenance: PROVENANCE,
    defects: [
      makeDefect({
        id: "D-T01-2018-01",
        concept: "crack",
        score: 0.82,
        severity: 5,
        confidence: 0.48,
        verdict: "reinspect",
        reasons: [
          "First and second look disagree on severity (5 vs 3).",
          "Confidence below the reinspection threshold (0.48 < 0.55).",
        ],
        agreement: 0.42,
        region: "tip",
        axialPosition: 0.91,
        areaRatio: 0.031,
        elongation: 6.4,
        bbox: { x: 0.62, y: 0.28, width: 0.2, height: 0.08 },
        rationale:
          "Long thin high-contrast line near the tip consistent with a transverse crack; length relative to chord is large.",
      }),
      makeDefect({
        id: "D-T01-2018-02",
        concept: "leading edge erosion",
        score: 0.74,
        severity: 3,
        confidence: 0.71,
        verdict: "needs_review",
        reasons: ["Erosion depth cannot be judged from a single view."],
        agreement: 0.68,
        region: "mid",
        axialPosition: 0.55,
        areaRatio: 0.054,
        elongation: 2.1,
        bbox: { x: 0.3, y: 0.42, width: 0.16, height: 0.1 },
        rationale:
          "Rough, lightened band along the leading edge typical of mid-span erosion; moderate extent.",
      }),
    ],
  },
  {
    id: "T01-2017",
    turbineId: "T01",
    year: 2017,
    imageRef: "/images/T01-2017.jpg",
    imageWidth: 586,
    imageHeight: 371,
    provenance: PROVENANCE,
    defects: [
      makeDefect({
        id: "D-T01-2017-01",
        concept: "leading edge erosion",
        score: 0.66,
        severity: 2,
        confidence: 0.8,
        verdict: "ok",
        reasons: [],
        agreement: 0.86,
        region: "mid",
        axialPosition: 0.54,
        areaRatio: 0.028,
        elongation: 1.9,
        bbox: { x: 0.31, y: 0.44, width: 0.12, height: 0.08 },
        rationale: "Early-stage erosion, smaller extent than the 2018 inspection; low severity.",
      }),
    ],
  },

  // T02 — reinspect: lightning damage at the tip, low confidence.
  {
    id: "T02-2018",
    turbineId: "T02",
    year: 2018,
    imageRef: "/images/T02-2018.jpg",
    imageWidth: 586,
    imageHeight: 371,
    provenance: PROVENANCE,
    defects: [
      makeDefect({
        id: "D-T02-2018-01",
        concept: "lightning damage",
        score: 0.79,
        severity: 4,
        confidence: 0.5,
        verdict: "reinspect",
        reasons: [
          "Burn pattern ambiguous against background soiling.",
          "Confidence below the reinspection threshold.",
        ],
        agreement: 0.47,
        region: "tip",
        axialPosition: 0.88,
        areaRatio: 0.042,
        elongation: 1.4,
        bbox: { x: 0.68, y: 0.35, width: 0.14, height: 0.14 },
        rationale:
          "Dark radial scorching near the tip consistent with a lightning strike receptor area.",
      }),
    ],
  },
  {
    id: "T02-2017",
    turbineId: "T02",
    year: 2017,
    imageRef: "/images/T02-2017.jpg",
    imageWidth: 586,
    imageHeight: 371,
    provenance: PROVENANCE,
    defects: [],
  },

  // T03 — needs_review: moderate surface damage.
  {
    id: "T03-2018",
    turbineId: "T03",
    year: 2018,
    imageRef: "/images/T03-2018.jpg",
    imageWidth: 586,
    imageHeight: 371,
    provenance: PROVENANCE,
    defects: [
      makeDefect({
        id: "D-T03-2018-01",
        concept: "surface damage",
        score: 0.71,
        severity: 3,
        confidence: 0.66,
        verdict: "needs_review",
        reasons: ["Severity sits on the 2/3 rubric boundary; a human should confirm."],
        agreement: 0.72,
        region: "mid",
        axialPosition: 0.49,
        areaRatio: 0.038,
        elongation: 1.7,
        bbox: { x: 0.4, y: 0.4, width: 0.13, height: 0.11 },
        rationale: "Patchy surface disruption mid-span; coating loss likely but depth unclear.",
      }),
      makeDefect({
        id: "D-T03-2018-02",
        concept: "dirt",
        score: 0.6,
        severity: 1,
        confidence: 0.83,
        verdict: "ok",
        reasons: [],
        agreement: 0.9,
        region: "root",
        axialPosition: 0.18,
        areaRatio: 0.02,
        elongation: 1.2,
        bbox: { x: 0.12, y: 0.52, width: 0.1, height: 0.08 },
        rationale: "Soiling near the root; cosmetic only, not a structural defect.",
      }),
    ],
  },
  {
    id: "T03-2017",
    turbineId: "T03",
    year: 2017,
    imageRef: "/images/T03-2017.jpg",
    imageWidth: 586,
    imageHeight: 371,
    provenance: PROVENANCE,
    defects: [
      makeDefect({
        id: "D-T03-2017-01",
        concept: "surface damage",
        score: 0.63,
        severity: 2,
        confidence: 0.79,
        verdict: "ok",
        reasons: [],
        agreement: 0.84,
        region: "mid",
        axialPosition: 0.48,
        areaRatio: 0.022,
        elongation: 1.6,
        bbox: { x: 0.41, y: 0.41, width: 0.1, height: 0.09 },
        rationale: "Minor surface disruption; smaller than the 2018 follow-up.",
      }),
    ],
  },

  // T04 — needs_review: crack with acceptable agreement.
  {
    id: "T04-2018",
    turbineId: "T04",
    year: 2018,
    imageRef: "/images/T04-2018.jpg",
    imageWidth: 586,
    imageHeight: 371,
    provenance: PROVENANCE,
    defects: [
      makeDefect({
        id: "D-T04-2018-01",
        concept: "crack",
        score: 0.76,
        severity: 3,
        confidence: 0.69,
        verdict: "needs_review",
        reasons: ["Hairline crack length near the rubric's 2/3 boundary."],
        agreement: 0.74,
        region: "mid",
        axialPosition: 0.6,
        areaRatio: 0.018,
        elongation: 5.1,
        bbox: { x: 0.45, y: 0.46, width: 0.18, height: 0.04 },
        rationale: "Thin elongated feature; crack-like aspect ratio, moderate length.",
      }),
    ],
  },
  {
    id: "T04-2017",
    turbineId: "T04",
    year: 2017,
    imageRef: "/images/T04-2017.jpg",
    imageWidth: 586,
    imageHeight: 371,
    provenance: PROVENANCE,
    defects: [],
  },

  // T05..T08 — ok with minor findings.
  ...minorTurbine("T05", 2, 0.86),
  ...minorTurbine("T06", 2, 0.88),
  ...minorTurbine("T07", 1, 0.9),
  ...minorTurbine("T08", 1, 0.92),

  // T09..T12 — ok, clean or near-clean.
  ...cleanTurbine("T09"),
  ...cleanTurbine("T10"),
  ...cleanTurbine("T11"),
  ...cleanTurbine("T12"),
];

/** Build an "ok" turbine with one low-severity verified defect. */
function minorTurbine(id: string, severity: Severity, confidence: number): Inspection[] {
  return [
    {
      id: `${id}-2018`,
      turbineId: id,
      year: 2018,
      imageRef: `/images/${id}-2018.jpg`,
      imageWidth: 586,
      imageHeight: 371,
      provenance: PROVENANCE,
      defects: [
        makeDefect({
          id: `D-${id}-2018-01`,
          concept: "dirt",
          score: 0.58,
          severity,
          confidence,
          verdict: "ok",
          reasons: [],
          agreement: 0.88,
          region: "root",
          axialPosition: 0.2,
          areaRatio: 0.015,
          elongation: 1.3,
          bbox: { x: 0.15, y: 0.5, width: 0.1, height: 0.08 },
          rationale: "Low-severity soiling; no structural concern.",
        }),
      ],
    },
    {
      id: `${id}-2017`,
      turbineId: id,
      year: 2017,
      imageRef: `/images/${id}-2017.jpg`,
      imageWidth: 586,
      imageHeight: 371,
      provenance: PROVENANCE,
      defects: [],
    },
  ];
}

/** Build a clean "ok" turbine with no defects in either year. */
function cleanTurbine(id: string): Inspection[] {
  return [2018, 2017].map((year) => ({
    id: `${id}-${year}`,
    turbineId: id,
    year,
    imageRef: `/images/${id}-${year}.jpg`,
    imageWidth: 586,
    imageHeight: 371,
    provenance: PROVENANCE,
    defects: [],
  }));
}

// --- Turbines (derived ranking) -------------------------------------------

const VERDICT_RANK: Record<Verdict, number> = { ok: 0, needs_review: 1, reinspect: 2 };

/** Worst verdict among a set of defects, defaulting to "ok" when empty. */
function worstVerdict(defects: Defect[]): Verdict {
  return defects.reduce<Verdict>(
    (worst, d) =>
      VERDICT_RANK[d.verification.verdict] > VERDICT_RANK[worst] ? d.verification.verdict : worst,
    "ok",
  );
}

/** Highest severity among a set of defects, defaulting to 1 when empty. */
function maxSeverity(defects: Defect[]): Severity {
  return defects.reduce<Severity>(
    (max, d) => (d.assessment.severity > max ? d.assessment.severity : max),
    1,
  );
}

function buildTurbines(allInspections: Inspection[]): Turbine[] {
  const ids = Array.from(new Set(allInspections.map((i) => i.turbineId))).sort();
  const turbines = ids.map((id) => {
    const owned = allInspections
      .filter((i) => i.turbineId === id)
      .sort((a, b) => b.year - a.year);
    const defects = owned.flatMap((i) => i.defects);
    const status = worstVerdict(defects);
    const sev = maxSeverity(defects);
    // Priority blends the worst verdict, max severity and defect count.
    const priority =
      VERDICT_RANK[status] * 100 + sev * 10 + defects.length + owned[0].year / 100000;
    return {
      id,
      name: `Turbine ${id}`,
      rank: 0, // filled in after sorting
      priority: Math.round(priority * 100) / 100,
      status,
      maxSeverity: sev,
      defectCount: defects.length,
      inspectionIds: owned.map((i) => i.id),
      latestInspectionId: owned[0].id,
    } satisfies Turbine;
  });
  turbines.sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
  turbines.forEach((t, idx) => {
    t.rank = idx + 1;
  });
  return turbines;
}

const turbines: Turbine[] = buildTurbines(inspections);

// --- Work orders & report --------------------------------------------------

const workOrders: WorkOrder[] = [
  {
    id: "WO-001",
    turbineId: "T01",
    title: "Re-inspect suspected tip crack",
    priority: "reinspect",
    action:
      "Schedule a close-range re-inspection of the T01 outboard blade to confirm the tip crack before any repair decision.",
    defectIds: ["D-T01-2018-01"],
    rationale:
      "The severity-5 crack has low model confidence and poor agreement between the two looks; a guess here is not acceptable.",
  },
  {
    id: "WO-002",
    turbineId: "T02",
    title: "Re-inspect suspected lightning damage",
    priority: "reinspect",
    action: "Re-image the T02 tip region under better lighting to separate scorching from soiling.",
    defectIds: ["D-T02-2018-01"],
    rationale:
      "Lightning damage pattern is ambiguous and confidence is below threshold; verify before dispatching a crew.",
  },
  {
    id: "WO-003",
    turbineId: "T03",
    title: "Review mid-span surface damage",
    priority: "needs_review",
    action: "Have an inspector confirm the severity of the T03 mid-span coating loss.",
    defectIds: ["D-T03-2018-01"],
    rationale:
      "Surface damage sits on the rubric 2/3 boundary; growth since 2017 suggests monitoring is warranted.",
  },
  {
    id: "WO-004",
    turbineId: "T04",
    title: "Review hairline crack",
    priority: "needs_review",
    action: "Confirm the length and depth of the T04 mid-span hairline crack.",
    defectIds: ["D-T04-2018-01"],
    rationale: "Crack-like aspect ratio with moderate length; human confirmation requested.",
  },
];

const report: Report = {
  generatedAt: "2018-06-01T09:00:00Z",
  summary:
    "Across 12 turbines, two require re-inspection (T01 tip crack, T02 lightning damage) before any repair is scheduled, and two need human review (T03, T04). The remaining eight show only low-severity soiling or are clean. No repair is recommended without a verified assessment.",
  rankedTurbineIds: turbines.map((t) => t.id),
  workOrders,
};

// --- Agent trace -----------------------------------------------------------

const agentTrace: AgentStep[] = [
  {
    index: 1,
    tool: "list_turbines",
    args: { farm: "synthetic-dtu" },
    output: "Returned 12 turbines (T01..T12), each with 2017 and 2018 inspections.",
    note: "Seeded synthetic grouping of real DTU drone photos.",
  },
  {
    index: 2,
    tool: "get_inspection",
    args: { inspectionId: "T01-2018" },
    output: "2 defects: a tip crack (score 0.82) and mid-span leading edge erosion (score 0.74).",
  },
  {
    index: 3,
    tool: "compare_inspections",
    args: { turbineId: "T01", from: "T01-2017", to: "T01-2018" },
    output: "Erosion extent grew from 0.028 to 0.054 area ratio; new tip crack appeared in 2018.",
    note: "Year-over-year growth raises T01 priority.",
  },
  {
    index: 4,
    tool: "assess_image",
    args: { defectId: "D-T01-2018-01" },
    output: "Severity 5, confidence 0.48, rationale references transverse crack length vs chord.",
  },
  {
    index: 5,
    tool: "request_reinspection",
    args: { defectId: "D-T01-2018-01", reason: "low confidence and look disagreement" },
    output: "Flagged D-T01-2018-01 for re-inspection; no repair claim made.",
    note: "Abstention rule: low confidence becomes reinspect, never a guess.",
  },
  {
    index: 6,
    tool: "assess_image",
    args: { defectId: "D-T02-2018-01" },
    output: "Severity 4, confidence 0.50; lightning pattern ambiguous against soiling.",
  },
  {
    index: 7,
    tool: "request_reinspection",
    args: { defectId: "D-T02-2018-01", reason: "ambiguous burn pattern" },
    output: "Flagged D-T02-2018-01 for re-inspection.",
  },
  {
    index: 8,
    tool: "create_work_order",
    args: { turbineId: "T01", defectIds: ["D-T01-2018-01"] },
    output: "Created WO-001 citing D-T01-2018-01.",
    note: "Work order cites defect evidence (no claim without a verified assessment).",
  },
  {
    index: 9,
    tool: "create_work_order",
    args: { turbineId: "T03", defectIds: ["D-T03-2018-01"] },
    output: "Created WO-003 citing D-T03-2018-01.",
  },
  {
    index: 10,
    tool: "write_report",
    args: { ranked: true },
    output: "Wrote the fleet report with 4 work orders and the priority ranking.",
  },
];

// --- Evaluation report -----------------------------------------------------

const evalReport: EvalReport = {
  split: "dev",
  iou: 0.3,
  metrics: {
    precision: 0.74,
    recall: 0.68,
    f1: 0.71,
    imageLevelRecall: 0.82,
    needsReviewShare: 0.19,
  },
  thresholdCurve: [
    { threshold: 0.3, precision: 0.52, recall: 0.86, missed: 12, falseAlarms: 61 },
    { threshold: 0.4, precision: 0.61, recall: 0.8, missed: 17, falseAlarms: 42 },
    { threshold: 0.5, precision: 0.7, recall: 0.73, missed: 23, falseAlarms: 28 },
    { threshold: 0.6, precision: 0.74, recall: 0.68, missed: 27, falseAlarms: 21 },
    { threshold: 0.7, precision: 0.81, recall: 0.57, missed: 36, falseAlarms: 12 },
    { threshold: 0.8, precision: 0.88, recall: 0.41, missed: 50, falseAlarms: 6 },
  ],
  limitations: [
    "Placeholder numbers: these metrics are illustrative mock data, not a measured evaluation.",
    "Sizes are relative to the blade mask (pixels), not millimetres.",
    "Severity uses an illustrative rubric, not an industry standard.",
    "The synthetic farm groups real DTU photos; it is not a real multi-turbine site.",
  ],
  evidenceRef: "docs/evidence/eval_dev.md",
};

// --- Exported dataset ------------------------------------------------------

export const mockDataset: FleetDataset = {
  farmLabel: FARM_LABEL,
  turbines,
  inspections,
  report,
  agentTrace,
  evalReport,
};
