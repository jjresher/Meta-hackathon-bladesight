"""`docs/evidence/fleet_run.md`: what the farm processing and the agent run produced."""

from __future__ import annotations

from collections import Counter

from .compare import autonomy, autonomy_table, latest_run
from .rank import all_defects, summarize
from .store import Store


def render(
    store: Store,
    farm_cost_usd: float,
    agent_cost_usd: float,
    command_notes: str = "",
    open_store: Store | None = None,
) -> str:
    inspections = store.inspections()
    defects = [d for i in inspections for d in all_defects(i)]
    graded = [d for d in defects if d.assessment and d.verification]
    verdicts = Counter(d.verification.verdict for d in graded if d.verification)
    ok_sev = Counter(
        d.assessment.severity
        for d in graded
        if d.verification and d.assessment and d.verification.verdict == "ok"
    )
    all_sev = Counter(d.assessment.severity for d in graded if d.assessment)
    errors = sum(d.error is not None for d in defects)
    n = len(graded) or 1
    run = max(store.runs(), key=lambda r: r.started_at) if store.runs() else None
    orders = store.work_orders()
    lines = [
        "# Fleet run: farm processing and the agent",
        "",
        "Synthetic farm: 12 turbines x 2 inspections (2017, 2018) of 4 real DTU dev tiles",
        "each, an invented grouping (`DATA.md`). Pipeline per tile: Muse Spark box proposals",
        "-> SAM 3.1 masks -> measurement -> Muse Spark severity (`assess/v1`, rubric `v1`)",
        "-> second look and rule checks (`verify/v1`). At most 4 detections per tile are",
        "graded. Costs are documented prices times",
        "real usage (not invoice-checked)." + (f" {command_notes}" if command_notes else ""),
        "",
        "## Farm processing",
        "",
        f"- Inspections: {len(inspections)}; images: {sum(len(i.images) for i in inspections)}; "
        f"defects detected and kept: {len(defects)}; graded and verified: {len(graded)}; "
        f"left ungraded after an error: {errors}; images with no detection at all: "
        f"{sum(not img.defects for i in inspections for img in i.images)}.",
        f"- Verdicts over {len(graded)} graded defects: "
        f"`ok` {verdicts['ok']} ({verdicts['ok'] / n:.0%}), "
        f"`needs_review` {verdicts['needs_review']} ({verdicts['needs_review'] / n:.0%}), "
        f"`reinspect` {verdicts['reinspect']} ({verdicts['reinspect'] / n:.0%}).",
        f"- Severity of all graded defects: {dict(sorted(all_sev.items()))}; of the verified "
        f"(`ok`) ones: {dict(sorted(ok_sev.items()))}. No defect was graded above 3.",
        f"- Cost of the live runs that produced the store: {farm_cost_usd:.4f} USD.",
        "",
        "Verification thresholds (`verify.THRESHOLDS`: combined confidence 0.30 for `ok`, 0.15 for",
        "`reinspect`) were set on a first 17-defect sample of these dev tiles before this run was",
        "completed (`docs/decision_ledger.md`); the shares above therefore depend on that choice.",
        "",
        "## Agent run",
        "",
    ]
    if run is None:
        lines.append("No agent run stored.")
    else:
        kinds = Counter(s.kind for s in run.steps)
        lines += [
            f"- Run `{run.id}`: status `{run.status}`, model `{run.model}`, {len(run.steps)} steps "
            f"({kinds['tool_call']} tool calls, {kinds['thought']} notes), "
            f"cost {agent_cost_usd:.4f} USD; the run replays with no model call when the response "
            "cache (`.cache/`, not committed) is present, and the demo reads the stored results.",
            f"- Work orders: {len(orders)} "
            f"({sum(o.kind == 'repair' for o in orders)} repair, "
            f"{sum(o.kind == 'monitor' for o in orders)} monitor, "
            f"{sum(o.kind == 'reinspect' for o in orders)} re-inspection); every repair order "
            "cites "
            "only defects with an `ok` verdict (enforced by the tool, tested).",
            f"- Report: {'`' + run.report_id + '`' if run.report_id else 'none'}.",
            "",
            "Trace and orders: `replay/runs/`, `replay/work_orders.json`, `replay/reports/`.",
        ]
        runs = [(run, orders)]
        open_run = latest_run(open_store) if open_store is not None else None
        if open_store is not None and open_run is not None:
            runs.append((open_run, open_store.work_orders()))
        lines += [
            "",
            "## Agent autonomy",
            "",
            "Counted from the stored traces (`fleet/compare.py`). A rejection is a tool call the",
            "tool refused, with the rule it enforced (`fleet/rules.py`, stable ids); the agent",
            "reads the refusal and decides what to do next. The rationale is the model's own text",
            "in the same turn before the call (null when it wrote none); nothing is filled in.",
            "Both runs recorded these fields as they ran (`fleet backfill` changes nothing).",
            "The Muse Spark Open run grades its own re-graded farm (`replay/open-weights/`),",
            "so the two agents saw different verdicts: compare behaviour, not order lists.",
            "",
            *autonomy_table([autonomy(r, o) for r, o in runs]),
        ]
    top = sorted(inspections, key=lambda i: (i.summary.turbine_id, i.summary.year))
    lines += [
        "",
        "## Per inspection",
        "",
        "| Inspection | Defects | Max verified severity | Needs review | Reinspect |",
        "|---|---|---|---|---|",
    ]
    for i in top:
        s = summarize(i)
        lines.append(
            f"| {s.id} | {s.n_defects} | {s.max_severity or '-'} | "
            f"{s.n_needs_review} | {s.n_reinspect} |"
        )
    return "\n".join(lines) + "\n"
