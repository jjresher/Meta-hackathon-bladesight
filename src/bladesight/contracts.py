"""The API contract: every object the pipeline, the agent, the API and the web UI exchange.

One place for these models (implementation plan, section 4). `python -m bladesight.contracts`
exports the JSON Schema and example fixtures to `web/src/fixtures/`. Change a model here, bump
`SCHEMA_VERSION` if the change is not backward compatible, and regenerate the fixtures.

Conventions: pixel coordinates are in the source tile (586x371 for DTU tiles), origin top-left,
`x2`/`y2` exclusive. Sizes are relative (pixels, shares of the blade), never millimetres.
Timestamps are ISO 8601 with offset. Ids are stable strings:
`T03` (turbine), `T03-2018` (inspection), `T03-2018/DJI_0702_04_05` (image),
`T03-2018/DJI_0702_04_05/d1` (defect), `WO-001` (work order), `run-...` (agent run).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"

Provider = Literal["meta", "baseten", "stub"]
EvalLabel = Literal["damage", "dirt"]
DefectType = Literal[
    "leading_edge_erosion",
    "crack",
    "lightning_damage",
    "surface_damage",
    "dirt",
    "other",
]
Position = Literal["root", "mid", "tip", "unknown"]
Verdict = Literal["ok", "needs_review", "reinspect"]
TurbineStatus = Literal["critical", "attention", "ok", "needs_review"]
Trend = Literal["worse", "same", "better", "new"]
WorkOrderKind = Literal["repair", "monitor", "reinspect"]
Priority = Literal["P1", "P2", "P3"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- detection and measurement ----------------------------------------------------------------


class BBox(Contract):
    x1: float
    y1: float
    x2: float
    y2: float


class Defect(Contract):
    """One SAM 3.1 detection on one image."""

    id: str
    image_id: str
    concept: str = Field(description="SAM 3.1 text concept that produced the mask")
    label: EvalLabel = Field(description="dataset class the concept maps to, used for evaluation")
    score: float = Field(ge=0, le=1, description="SAM 3.1 confidence")
    bbox: BBox
    outline: list[tuple[float, float]] = Field(
        default_factory=list,
        description="mask outline as a closed polygon in image pixels, for drawing overlays",
    )
    mask_area_px: float = Field(ge=0)


class Measurement(Contract):
    """Relative size and position of a defect (pixels, not millimetres)."""

    defect_id: str
    area_px: float = Field(ge=0)
    blade_area_ratio: float | None = Field(
        default=None, ge=0, description="defect area / blade area in the image; null if no blade"
    )
    length_px: float = Field(ge=0, description="extent along the defect's principal axis")
    width_px: float = Field(ge=0, description="extent across the defect's principal axis")
    elongation: float = Field(ge=0, le=1, description="1 - width/length; near 1 is crack-like")
    inside_blade: float | None = Field(
        default=None, ge=0, le=1, description="share of the defect inside the blade mask"
    )
    position: Position = Field(description="along the visible blade segment, not the whole blade")
    position_t: float | None = Field(default=None, ge=0, le=1, description="0 root side, 1 tip")
    units: Literal["pixels"] = "pixels"


# --- assessment and verification --------------------------------------------------------------


class Assessment(Contract):
    """Muse Spark's grade of one defect against `docs/rubric.md`."""

    defect_id: str
    defect_type: DefectType
    severity: int = Field(ge=1, le=5)
    rationale: str
    confidence: float = Field(ge=0, le=1)
    rubric_version: str
    prompt_version: str
    model: str
    provider: Provider


class Check(Contract):
    name: str
    passed: bool
    detail: str


class Verification(Contract):
    """Second look plus rule checks; low confidence becomes needs_review or reinspect."""

    defect_id: str
    verdict: Verdict
    agreement: float = Field(ge=0, le=1)
    second_severity: int | None = Field(default=None, ge=1, le=5)
    checks: list[Check] = Field(default_factory=list)
    reasons: list[str] = Field(description="why this verdict; never empty")


class InspectedDefect(Contract):
    defect: Defect
    measurement: Measurement | None = None
    assessment: Assessment | None = None
    verification: Verification | None = None


# --- fleet ------------------------------------------------------------------------------------


class InspectionImage(Contract):
    id: str
    tile_id: str = Field(description="DTU tile id, e.g. DJI_0702_04_05")
    image_url: str = Field(description="relative URL served by the API, e.g. /images/<tile>.png")
    width: int
    height: int
    blade_outline: list[tuple[float, float]] = Field(default_factory=list)
    defects: list[InspectedDefect] = Field(default_factory=list)


class InspectionSummary(Contract):
    id: str
    turbine_id: str
    year: int = Field(description="synthetic grouping: the DTU tiles carry no real year")
    n_images: int
    n_defects: int
    max_severity: int | None = Field(default=None, ge=1, le=5)
    n_needs_review: int
    n_reinspect: int


class Inspection(Contract):
    summary: InspectionSummary
    images: list[InspectionImage]


class Turbine(Contract):
    id: str
    name: str
    rank: int = Field(ge=1, description="1 = most urgent")
    priority_score: float = Field(ge=0)
    status: TurbineStatus
    trend: Trend = Field(description="latest vs previous inspection")
    inspections: list[InspectionSummary]
    open_work_orders: int
    reason: str = Field(description="one line: why this rank")


class Fleet(Contract):
    farm: str
    synthetic: Literal[True] = True
    note: str
    turbines: list[Turbine]
    run_id: str | None = None
    generated_at: datetime


class WorkOrder(Contract):
    id: str
    kind: WorkOrderKind
    priority: Priority
    turbine_id: str
    inspection_id: str
    defect_ids: list[str] = Field(min_length=1, description="every order cites its defects")
    action: str
    rationale: str
    evidence: list[str] = Field(
        min_length=1, description="verified assessments cited, e.g. 'T03-2018/.../d1: severity 4'"
    )
    due_within_days: int = Field(ge=0)
    created_by: Literal["agent", "human"] = "agent"
    run_id: str | None = None


class Report(Contract):
    id: str
    run_id: str
    title: str
    markdown: str
    work_order_ids: list[str]
    model: str
    provider: Provider
    generated_at: datetime


# --- agent ------------------------------------------------------------------------------------


class AgentStep(Contract):
    index: int = Field(ge=0)
    kind: Literal["thought", "tool_call", "tool_result", "final", "error"]
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    content: str = Field(description="model text, tool result summary or error message")
    duration_ms: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    model: str | None = None


class AgentRun(Contract):
    id: str
    status: Literal["completed", "step_limit", "budget_exceeded", "error"]
    replay: bool = Field(description="true when served from recorded results, no live call")
    model: str
    provider: Provider
    started_at: datetime
    finished_at: datetime | None
    steps: list[AgentStep]
    total_cost_usd: float = Field(ge=0)
    work_order_ids: list[str] = Field(default_factory=list)
    report_id: str | None = None


# --- evaluation -------------------------------------------------------------------------------


class Interval(Contract):
    low: float
    high: float
    method: Literal["bootstrap", "wilson"] = "bootstrap"


class ClassMetrics(Contract):
    label: EvalLabel
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    precision_ci: Interval | None = None
    recall_ci: Interval | None = None


class SweepPoint(Contract):
    threshold: float
    recall: float
    precision: float
    false_alarms_per_image: float


class EvalReport(Contract):
    split: Literal["dev", "heldout"]
    n_images: int
    iou_threshold: float
    classes: list[ClassMetrics]
    classes_iou50: list[ClassMetrics] = Field(default_factory=list)
    image_recall: float = Field(description="share of damaged images with at least one hit")
    sweep: list[SweepPoint] = Field(default_factory=list)
    needs_review_share: float | None = None
    severity_kappa: float | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    cost_usd: float = Field(ge=0)
    evidence_path: str = Field(description="docs/evidence/... file that backs these numbers")
    generated_at: datetime


class Health(Contract):
    status: Literal["ok"]
    mode: Literal["replay", "live"]
    version: str
    schema_version: str = SCHEMA_VERSION


EXPORTED: dict[str, type[Contract]] = {
    "Health": Health,
    "Fleet": Fleet,
    "Turbine": Turbine,
    "Inspection": Inspection,
    "InspectionSummary": InspectionSummary,
    "InspectionImage": InspectionImage,
    "InspectedDefect": InspectedDefect,
    "Defect": Defect,
    "Measurement": Measurement,
    "Assessment": Assessment,
    "Verification": Verification,
    "WorkOrder": WorkOrder,
    "Report": Report,
    "AgentStep": AgentStep,
    "AgentRun": AgentRun,
    "EvalReport": EvalReport,
}
