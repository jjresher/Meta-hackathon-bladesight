/**
 * BladeSight data contract — ALL nine types in one file (issue #13).
 *
 * These mirror the pydantic contracts defined in the Python package
 * (`src/bladesight/`, see docs/plan/implementation_plan.md section 4):
 * Defect, Measurement, Assessment, Verification, Turbine, Inspection,
 * WorkOrder, AgentStep, EvalReport.
 *
 * The backend agent will later drop generated fixtures in
 * `web/src/fixtures/*.json`; these types describe the shape those fixtures
 * (and the mock placeholders in `web/src/mocks/`) must satisfy. Where the plan
 * does not pin a field, a reasonable, documented choice is made here and kept
 * internally consistent with the mock data.
 */

/** One of the three verification/status outcomes used across the UI. */
export type Verdict = "ok" | "needs_review" | "reinspect";

/** Position of a defect along the blade's principal axis. */
export type BladeRegion = "root" | "mid" | "tip";

/** Severity on the illustrative 1-5 rubric (docs/rubric.md). */
export type Severity = 1 | 2 | 3 | 4 | 5;

/** Axis-aligned bounding box in relative image coordinates (0..1). */
export interface BBox {
  /** Left edge, fraction of image width. */
  x: number;
  /** Top edge, fraction of image height. */
  y: number;
  /** Width, fraction of image width. */
  width: number;
  /** Height, fraction of image height. */
  height: number;
}

/**
 * Geometry derived from a defect mask (measure/ step).
 * Sizes are relative (pixels / mask ratios), not millimetres — see
 * docs/limitations.md.
 */
export interface Measurement {
  /** Defect mask area as a fraction of the blade mask area (0..1). */
  areaRatio: number;
  /** Bounding box of the defect, relative coordinates. */
  bbox: BBox;
  /** Longest-axis / shortest-axis ratio; high values suggest a crack. */
  elongation: number;
  /** Where along the blade the defect sits. */
  region: BladeRegion;
  /** Position along the blade principal axis, 0 (root) .. 1 (tip). */
  axialPosition: number;
}

/**
 * Muse Spark severity judgement against the rubric (assess/ step).
 */
export interface Assessment {
  /** Defect concept, e.g. "crack", "leading edge erosion", "lightning damage". */
  type: string;
  /** Severity on the 1-5 rubric. */
  severity: Severity;
  /** Model's written explanation grounded in the rubric. */
  rationale: string;
  /** Model confidence in this assessment, 0..1. */
  confidence: number;
  /** Which model produced the assessment (API vs open weights, issue #15). */
  model?: string;
}

/**
 * Second-look verification plus rule checks (verify/ step).
 * Low confidence or disagreement downgrades the verdict.
 */
export interface Verification {
  /** Final verdict after the second look and rule checks. */
  verdict: Verdict;
  /** Human-readable reasons behind the verdict; never empty for non-ok. */
  reasons: string[];
  /** Agreement between the first and second look, 0..1. */
  agreement: number;
}

/**
 * A single detected defect with its full evidence chain:
 * measurement -> assessment -> verification.
 */
export interface Defect {
  /** Stable identifier, cited by work orders (e.g. "D-T03-2018-01"). */
  id: string;
  /** Detected concept label from SAM 3.1 prompting. */
  concept: string;
  /** SAM detection score, 0..1. */
  score: number;
  /** Polygon mask in relative coordinates, as a flat [x0,y0,x1,y1,...] ring. */
  maskPolygon: number[];
  /** Geometry derived from the mask. */
  measurement: Measurement;
  /** Severity assessment (absent only if assessment failed). */
  assessment: Assessment;
  /** Verification verdict for this defect. */
  verification: Verification;
}

/**
 * One drone inspection of one turbine in a given year, with its defects.
 */
export interface Inspection {
  /** Stable identifier (e.g. "T03-2018"). */
  id: string;
  /** Owning turbine id (e.g. "T03"). */
  turbineId: string;
  /** Inspection year (dataset years are 2017 and 2018). */
  year: number;
  /**
   * Reference to the drone image. A relative path served by the backend;
   * the UI never bundles the raster asset itself (AGENTS.md rule 2).
   */
  imageRef: string;
  /** Natural image width in pixels (for overlay scaling). */
  imageWidth: number;
  /** Natural image height in pixels (for overlay scaling). */
  imageHeight: number;
  /** Defects found in this inspection. */
  defects: Defect[];
  /** Honest provenance label shown in the UI. */
  provenance: string;
}

/**
 * A turbine in the synthetic farm, ranked for the fleet view.
 */
export interface Turbine {
  /** Stable identifier (e.g. "T03"). */
  id: string;
  /** Display name (e.g. "Turbine T03"). */
  name: string;
  /** 1-based rank by priority; 1 is the most urgent. */
  rank: number;
  /** Priority score used for ranking, higher is more urgent. */
  priority: number;
  /** Fleet-level status chip, derived from the worst verified defect. */
  status: Verdict;
  /** Highest severity observed across the turbine's defects. */
  maxSeverity: Severity;
  /** Total number of defects across inspections. */
  defectCount: number;
  /** Inspection ids available for this turbine, newest first. */
  inspectionIds: string[];
  /** Latest inspection id (convenience for the fleet row link). */
  latestInspectionId: string;
}

/**
 * A repair work order produced by the fleet agent. Every work order cites the
 * defect ids that justify it (AGENTS.md rule 5: no claim without evidence).
 */
export interface WorkOrder {
  /** Stable identifier (e.g. "WO-001"). */
  id: string;
  /** Turbine the work order targets. */
  turbineId: string;
  /** Short title of the recommended action. */
  title: string;
  /** Priority chip, mirrors the turbine status scale. */
  priority: Verdict;
  /** Recommended action text. */
  action: string;
  /** Defect ids that justify the order; must be non-empty. */
  defectIds: string[];
  /** Agent's rationale for the order. */
  rationale: string;
}

/**
 * The written fleet report: a summary plus the ordered work orders.
 */
export interface Report {
  /** When the report was generated (ISO 8601). */
  generatedAt: string;
  /** Executive summary paragraph. */
  summary: string;
  /** Turbine ids in priority order. */
  rankedTurbineIds: string[];
  /** Work orders in priority order. */
  workOrders: WorkOrder[];
}

/**
 * One step of the fleet agent's tool-calling loop (the visible trace).
 */
export interface AgentStep {
  /** 1-based step index in the loop. */
  index: number;
  /** Tool invoked, e.g. "list_turbines", "assess_image", "create_work_order". */
  tool: string;
  /** Arguments passed to the tool. */
  args: Record<string, unknown>;
  /** Tool result summary or output. */
  output: string;
  /** Optional free-text note (model thought or rule applied). */
  note?: string;
}

/** A single point on the detection threshold sweep curve. */
export interface ThresholdPoint {
  /** Score threshold applied to detections, 0..1. */
  threshold: number;
  /** Precision at this threshold. */
  precision: number;
  /** Recall at this threshold. */
  recall: number;
  /** Count of missed defects (false negatives) at this threshold. */
  missed: number;
  /** Count of false alarms (false positives) at this threshold. */
  falseAlarms: number;
}

/**
 * The evaluation report: headline metrics, the threshold curve and the
 * honest list of limitations. Every number links to docs/evidence/.
 */
export interface EvalReport {
  /** Split the evaluation was run on (e.g. "dev"). */
  split: string;
  /** IoU threshold used for matching (e.g. 0.3). */
  iou: number;
  /** Headline metrics keyed by name (precision, recall, f1, ...). */
  metrics: Record<string, number>;
  /** Threshold sweep points for the curve. */
  thresholdCurve: ThresholdPoint[];
  /** Known gaps and caveats, shown verbatim in the UI. */
  limitations: string[];
  /** Link to the backing evidence file (docs/evidence/...). */
  evidenceRef: string;
}

/**
 * The full dataset the API client serves. Mock placeholders and the future
 * JSON fixtures both conform to this shape.
 */
export interface FleetDataset {
  /** Farm-level provenance label (honest about the synthetic grouping). */
  farmLabel: string;
  /** Turbines, ranked by priority. */
  turbines: Turbine[];
  /** All inspections, keyed into by id. */
  inspections: Inspection[];
  /** The written fleet report with work orders. */
  report: Report;
  /** The agent trace for the latest run. */
  agentTrace: AgentStep[];
  /** The evaluation report. */
  evalReport: EvalReport;
}
