"""Turbine ranking from VERIFIED assessments only (rule: no claim without a verified assessment).

Only defects whose verification is `ok` count in the score and the status `critical`/`attention`;
`needs_review` adds a small pending score and the status `needs_review`; `reinspect` and
ungraded defects add nothing and are listed for new photos. The score is a transparent sum, not a
model output, so the ranking is reproducible and the agent can only explain it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..contracts import (
    Fleet,
    InspectedDefect,
    Inspection,
    InspectionSummary,
    Trend,
    Turbine,
    TurbineStatus,
    WorkOrder,
)
from .build import NOTE

SEVERITY_WEIGHT = {1: 0.0, 2: 1.0, 3: 4.0, 4: 10.0, 5: 20.0}
PENDING_FACTOR = 0.25  # a needs_review defect counts a quarter of its weight, flagged pending


def verified(d: InspectedDefect) -> bool:
    return bool(d.assessment and d.verification and d.verification.verdict == "ok")


def all_defects(inspection: Inspection) -> list[InspectedDefect]:
    return [d for image in inspection.images for d in image.defects]


def summarize(inspection: Inspection) -> InspectionSummary:
    """Recount an inspection from its defects (the single source of the summary numbers)."""
    defects = all_defects(inspection)
    ok_severities = [d.assessment.severity for d in defects if verified(d) and d.assessment]
    return inspection.summary.model_copy(
        update={
            "n_images": len(inspection.images),
            "n_defects": len(defects),
            "max_severity": max(ok_severities) if ok_severities else None,
            "n_needs_review": sum(
                bool(d.verification and d.verification.verdict == "needs_review") for d in defects
            ),
            "n_reinspect": sum(
                bool(d.verification and d.verification.verdict == "reinspect") for d in defects
            ),
        }
    )


def score(inspection: Inspection) -> float:
    total = 0.0
    for d in all_defects(inspection):
        if not d.assessment or not d.verification:
            continue
        weight = SEVERITY_WEIGHT[d.assessment.severity]
        if d.verification.verdict == "ok":
            total += weight
        elif d.verification.verdict == "needs_review":
            total += weight * PENDING_FACTOR
    return round(total, 2)


def status_of(inspection: Inspection) -> TurbineStatus:
    summary = summarize(inspection)
    if summary.max_severity is not None and summary.max_severity >= 4:
        return "critical"
    if summary.n_needs_review or summary.n_reinspect:
        return "needs_review"
    if summary.max_severity is not None and summary.max_severity >= 3:
        return "attention"
    return "ok"


def trend_of(previous: Inspection | None, latest: Inspection) -> Trend:
    if previous is None:
        return "new"
    before, after = summarize(previous).max_severity or 0, summarize(latest).max_severity or 0
    s_before, s_after = score(previous), score(latest)
    if after > before or s_after > s_before * 1.25 + 1:
        return "worse"
    if after < before or s_after < s_before * 0.75 - 1:
        return "better"
    return "same"


def reason_of(latest: Inspection, trend: Trend) -> str:
    s = summarize(latest)
    parts = [
        f"max verified severity {s.max_severity}" if s.max_severity else "no verified defect",
        f"{s.n_defects} defects",
    ]
    if s.n_needs_review:
        parts.append(f"{s.n_needs_review} need review")
    if s.n_reinspect:
        parts.append(f"{s.n_reinspect} need new photos")
    parts.append(f"trend {trend} vs the previous inspection")
    return "; ".join(parts)


def build_fleet(
    inspections: list[Inspection],
    work_orders: list[WorkOrder],
    run_id: str | None = None,
    farm: str = "Synthetic farm (12 turbines of real DTU photos)",
) -> Fleet:
    by_turbine: dict[str, list[Inspection]] = {}
    for inspection in inspections:
        by_turbine.setdefault(inspection.summary.turbine_id, []).append(inspection)
    turbines = []
    for tid, items in by_turbine.items():
        items.sort(key=lambda i: i.summary.year)
        latest = items[-1]
        previous = items[-2] if len(items) > 1 else None
        trend = trend_of(previous, latest)
        turbines.append(
            Turbine(
                id=tid,
                name=f"Turbine {tid[1:]}",
                rank=1,
                priority_score=score(latest),
                status=status_of(latest),
                trend=trend,
                inspections=[summarize(i) for i in items],
                open_work_orders=sum(o.turbine_id == tid for o in work_orders),
                reason=reason_of(latest, trend),
            )
        )
    turbines.sort(key=lambda t: (-t.priority_score, t.id))
    for rank, turbine in enumerate(turbines, start=1):
        turbine.rank = rank
    return Fleet(
        farm=farm, note=NOTE, turbines=turbines, run_id=run_id, generated_at=datetime.now(UTC)
    )
