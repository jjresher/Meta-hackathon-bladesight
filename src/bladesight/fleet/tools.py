"""The seven tools of the fleet agent. Every result is JSON text for the model.

Rule enforced in code (not by the prompt): a work order may only cite defects that exist in the
named inspection and whose verification verdict is `ok`; its evidence lines are written here from
the stored assessments, never taken from the model. Defects that are `needs_review` or
`reinspect` can only be the subject of a re-inspection request. Violations come back as a tool
error the agent can read and fix.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..contracts import InspectedDefect, Inspection, Report, WorkOrder
from ..meta import ToolSpec
from .rank import all_defects, build_fleet, summarize, verified
from .store import Store

PRIORITY = {"P1": 30, "P2": 90, "P3": 180}  # default due_within_days


class ToolError(Exception):
    """A rejected tool call; the message is returned to the model."""


def _json(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), default=str)


def _compact(d: InspectedDefect) -> dict[str, Any]:
    a, v, m = d.assessment, d.verification, d.measurement
    return {
        "defect_id": d.defect.id,
        "label": d.defect.label,
        "type": a.defect_type if a else None,
        "severity": a.severity if a else None,
        "confidence": a.confidence if a else None,
        "verdict": v.verdict if v else None,
        "agreement": v.agreement if v else None,
        "reasons": v.reasons if v else ([d.error] if d.error else []),
        "position": m.position if m else None,
        "tile_share": round(m.tile_area_ratio, 5) if m else None,
    }


class FleetTools:
    def __init__(self, store: Store, run_id: str) -> None:
        self.store = store
        self.run_id = run_id
        self.orders: list[WorkOrder] = []
        self.report: Report | None = None
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "list_turbines": self.list_turbines,
            "get_inspection": self.get_inspection,
            "compare_inspections": self.compare_inspections,
            "assess_image": self.assess_image,
            "create_work_order": self.create_work_order,
            "request_reinspection": self.request_reinspection,
            "write_report": self.write_report,
        }

    # --- dispatch -------------------------------------------------------------------------
    def call(self, name: str, arguments: dict[str, Any]) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            return _json({"error": f"unknown tool {name!r}", "tools": sorted(self._handlers)})
        try:
            return _json(handler(arguments))
        except ToolError as error:
            return _json({"error": str(error)})
        except KeyError as error:
            return _json({"error": f"unknown id or missing argument: {error}"})
        except (TypeError, ValueError) as error:
            return _json({"error": f"bad arguments: {error}"})

    # --- read tools -----------------------------------------------------------------------
    def _inspection(self, inspection_id: str) -> Inspection:
        return self.store.inspection(str(inspection_id))

    def list_turbines(self, args: dict[str, Any]) -> Any:
        fleet = build_fleet(self.store.inspections(), self.orders)
        return [
            {
                "turbine_id": t.id,
                "rank": t.rank,
                "priority_score": t.priority_score,
                "status": t.status,
                "trend": t.trend,
                "inspections": [i.id for i in t.inspections],
                "reason": t.reason,
            }
            for t in fleet.turbines
        ]

    def get_inspection(self, args: dict[str, Any]) -> Any:
        inspection = self._inspection(args["inspection_id"])
        return {
            "summary": summarize(inspection).model_dump(),
            "images": [
                {"image_id": img.id, "defects": [_compact(d) for d in img.defects]}
                for img in inspection.images
            ],
        }

    def compare_inspections(self, args: dict[str, Any]) -> Any:
        turbine = str(args["turbine_id"])
        items = sorted(
            (i for i in self.store.inspections() if i.summary.turbine_id == turbine),
            key=lambda i: i.summary.year,
        )
        if len(items) < 2:
            raise ToolError(f"{turbine} has fewer than two inspections to compare")
        rows = []
        for inspection in items:
            rows.append(
                {
                    "inspection_id": inspection.summary.id,
                    "year": inspection.summary.year,
                    "summary": summarize(inspection).model_dump(),
                    "verified_severities": sorted(
                        (
                            d.assessment.severity
                            for d in all_defects(inspection)
                            if verified(d) and d.assessment
                        ),
                        reverse=True,
                    ),
                }
            )
        return {
            "turbine_id": turbine,
            "synthetic_years": True,
            "note": "years are a synthetic grouping of real photos; compare counts, not photos",
            "inspections": rows,
        }

    def assess_image(self, args: dict[str, Any]) -> Any:
        image_id = str(args["image_id"])
        inspection_id = image_id.split("/", 1)[0]
        for image in self._inspection(inspection_id).images:
            if image.id == image_id:
                return {"image_id": image_id, "defects": [_compact(d) for d in image.defects]}
        raise ToolError(f"unknown image {image_id!r}; ids look like T03-2018/DJI_0702_04_05")

    # --- write tools ----------------------------------------------------------------------
    def _defects(self, inspection: Inspection, defect_ids: list[str]) -> list[InspectedDefect]:
        index = {d.defect.id: d for d in all_defects(inspection)}
        missing = [i for i in defect_ids if i not in index]
        if missing:
            raise ToolError(f"defects not in {inspection.summary.id}: {missing}")
        return [index[i] for i in defect_ids]

    def _next_id(self) -> str:
        n = len(self.orders) + 1
        return f"WO-{n:03d}"

    def create_work_order(self, args: dict[str, Any]) -> Any:
        kind = str(args.get("kind", "repair"))
        if kind not in ("repair", "monitor"):
            raise ToolError(
                "kind must be 'repair' or 'monitor' (use request_reinspection otherwise)"
            )
        priority = str(args.get("priority", "P2"))
        if priority not in PRIORITY:
            raise ToolError("priority must be P1, P2 or P3")
        defect_ids = [str(i) for i in args["defect_ids"]]
        if not defect_ids:
            raise ToolError("cite at least one defect id")
        inspection = self._inspection(args["inspection_id"])
        defects = self._defects(inspection, defect_ids)
        rejected = [
            f"{d.defect.id} ({d.verification.verdict if d.verification else 'not graded'})"
            for d in defects
            if not verified(d)
        ]
        if rejected:
            raise ToolError(
                "no work order without a verified assessment; these defects are not verified: "
                f"{rejected}. Use request_reinspection for them."
            )
        evidence = [
            f"{d.defect.id}: severity {d.assessment.severity} ({d.assessment.defect_type}), "  # type: ignore[union-attr]
            f"verdict ok, agreement {d.verification.agreement:.2f}, "  # type: ignore[union-attr]
            f"confidence {d.assessment.confidence:.2f}"  # type: ignore[union-attr]
            for d in defects
        ]
        order = WorkOrder(
            id=self._next_id(),
            kind=kind,  # type: ignore[arg-type]
            priority=priority,  # type: ignore[arg-type]
            turbine_id=inspection.summary.turbine_id,
            inspection_id=inspection.summary.id,
            defect_ids=defect_ids,
            action=str(args["action"])[:400],
            rationale=str(args["rationale"])[:800],
            evidence=evidence,
            due_within_days=int(args.get("due_within_days", PRIORITY[priority])),
            run_id=self.run_id,
        )
        self.orders.append(order)
        return {"created": order.id, "evidence": evidence}

    def request_reinspection(self, args: dict[str, Any]) -> Any:
        defect_ids = [str(i) for i in args["defect_ids"]]
        if not defect_ids:
            raise ToolError("cite at least one defect id")
        inspection = self._inspection(args["inspection_id"])
        defects = self._defects(inspection, defect_ids)
        evidence = []
        for d in defects:
            if d.verification is None and d.error is None:
                raise ToolError(f"{d.defect.id} was never assessed: use assess_image first")
            reasons = d.verification.reasons if d.verification else [d.error or "not graded"]
            evidence.append(f"{d.defect.id}: not verified ({'; '.join(reasons)})"[:300])
        order = WorkOrder(
            id=self._next_id(),
            kind="reinspect",
            priority="P2",
            turbine_id=inspection.summary.turbine_id,
            inspection_id=inspection.summary.id,
            defect_ids=defect_ids,
            action=str(args.get("action", "Re-inspect with closer, sharper photos"))[:400],
            rationale=str(args["reason"])[:800],
            evidence=evidence,
            due_within_days=int(args.get("due_within_days", 14)),
            run_id=self.run_id,
        )
        self.orders.append(order)
        return {"created": order.id, "evidence": evidence}

    def write_report(self, args: dict[str, Any]) -> Any:
        markdown = str(args["markdown"])
        known = {o.id for o in self.orders}
        cited = set(re.findall(r"WO-\d{3}", markdown))
        if cited - known:
            raise ToolError(
                f"the report cites work orders that do not exist: {sorted(cited - known)}"
            )
        defect_ids = set(re.findall(r"T\d{2}-\d{4}/DJI_\d{4}_\d{2}_\d{2}/d\d+", markdown))
        valid = {
            d.defect.id
            for i in self.store.inspections()
            for d in all_defects(i)
            if d.verification is not None
        }
        unknown = defect_ids - valid
        if unknown:
            raise ToolError(f"the report cites defects that were not assessed: {sorted(unknown)}")
        self.report = Report(
            id=f"report-{self.run_id}",
            run_id=self.run_id,
            title=str(args.get("title", "Farm inspection report"))[:200],
            markdown=markdown,
            work_order_ids=sorted(o.id for o in self.orders),
            model="",
            provider="meta",
            generated_at=datetime.now(UTC),
        )
        # no run id in the result: it would enter the next prompt and break cache replay
        return {"report_saved": True, "work_orders": self.report.work_order_ids}


def tool_specs() -> list[ToolSpec]:
    def obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {"type": "object", "properties": props, "required": required}

    ids = {"type": "array", "items": {"type": "string"}}
    return [
        ToolSpec(
            name="list_turbines",
            description="All turbines ranked by the deterministic priority score of verified "
            "defects, with status and trend.",
            parameters=obj({}, []),
        ),
        ToolSpec(
            name="get_inspection",
            description="One inspection: counts and every defect with severity, verdict, reasons.",
            parameters=obj(
                {"inspection_id": {"type": "string", "description": "e.g. T03-2018"}},
                ["inspection_id"],
            ),
        ),
        ToolSpec(
            name="compare_inspections",
            description="2017 vs 2018 inspections of one turbine (synthetic years): counts and "
            "verified severities.",
            parameters=obj(
                {"turbine_id": {"type": "string", "description": "e.g. T03"}}, ["turbine_id"]
            ),
        ),
        ToolSpec(
            name="assess_image",
            description="Stored assessment of one image's defects (no new model call).",
            parameters=obj(
                {"image_id": {"type": "string", "description": "e.g. T03-2018/DJI_0702_04_05"}},
                ["image_id"],
            ),
        ),
        ToolSpec(
            name="create_work_order",
            description="Create a repair or monitor work order. Every defect cited must have a "
            "verified (verdict ok) assessment; otherwise it is rejected.",
            parameters=obj(
                {
                    "inspection_id": {"type": "string"},
                    "defect_ids": ids,
                    "kind": {"type": "string", "enum": ["repair", "monitor"]},
                    "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                    "action": {"type": "string"},
                    "rationale": {"type": "string"},
                    "due_within_days": {"type": "integer"},
                },
                ["inspection_id", "defect_ids", "action", "rationale"],
            ),
        ),
        ToolSpec(
            name="request_reinspection",
            description="Ask for new photos of defects whose verdict is needs_review or "
            "reinspect, or that failed to grade. Never guess a severity instead.",
            parameters=obj(
                {
                    "inspection_id": {"type": "string"},
                    "defect_ids": ids,
                    "reason": {"type": "string"},
                    "action": {"type": "string"},
                },
                ["inspection_id", "defect_ids", "reason"],
            ),
        ),
        ToolSpec(
            name="write_report",
            description="Write the final Markdown report. It may only cite existing work orders "
            "(WO-001) and assessed defect ids.",
            parameters=obj(
                {"title": {"type": "string"}, "markdown": {"type": "string"}}, ["markdown"]
            ),
        ),
    ]
