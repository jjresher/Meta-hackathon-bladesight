"""Structured autonomy fields of an agent trace, derived only from what the run recorded.

For every `tool_call` step:

- `rationale`: the model's own text in the same turn, before the call (the `thought` step the
  loop records); null when the model gave none. Never written by us.
- `decision`: what the call asked for, a fixed summary of the tool name and its arguments.
- `outcome` / `blocked_by_rule`: `rejected` with the rule id when the tool's result is an error
  (`rules.rule_for_error`), `accepted` otherwise.

The same function annotates a live run and backfills a run stored before these fields existed,
so both are derived the same way. Turn boundaries: a `thought` step opens a turn, and so does a
`tool_call` that carries the model call's duration or cost (the loop puts both on the first call
of a turn only). A stored step that is already annotated is recomputed, never trusted.
"""

from __future__ import annotations

from typing import Any

from ..contracts import AgentRun, AgentStep
from .rules import error_of, rule_for_error


def _ids(args: dict[str, Any]) -> int:
    ids = args.get("defect_ids")
    return len(ids) if isinstance(ids, list) else 0


def decision_for(tool: str, args: dict[str, Any] | None) -> str:
    a = args or {}
    n = _ids(a)
    defects = f"{n} defect{'s' if n != 1 else ''}"
    match tool:
        case "list_turbines":
            return "read the farm ranking"
        case "get_inspection":
            return f"read inspection {a.get('inspection_id', '?')}"
        case "compare_inspections":
            return f"compare the two inspections of {a.get('turbine_id', '?')}"
        case "assess_image":
            return f"read the stored assessments of image {a.get('image_id', '?')}"
        case "create_work_order":
            kind = a.get("kind", "repair")
            priority = a.get("priority", "P2")
            return f"{kind} work order ({priority}) for {a.get('inspection_id', '?')}: {defects}"
        case "request_reinspection":
            return f"re-inspection request for {a.get('inspection_id', '?')}: {defects}"
        case "write_report":
            markdown = a.get("markdown")
            size = len(markdown) if isinstance(markdown, str) else 0
            return f"write the farm report ({size} characters)"
        case _:
            return f"call {tool}"


def _turns(steps: list[AgentStep]) -> list[int | None]:
    """The model turn of each step: recorded by the loop, else inferred (module docstring)."""
    turns: list[int | None] = []
    turn = 0
    previous: AgentStep | None = None
    for step in steps:
        if step.turn is not None:
            turn = step.turn
            turns.append(turn)
        elif step.kind in ("thought", "final"):
            turn += 1
            turns.append(turn)
        elif step.kind == "tool_call":
            if previous is None or (
                previous.kind != "thought" and (step.duration_ms > 0 or step.cost_usd > 0)
            ):
                turn += 1
            turns.append(turn)
        elif step.kind == "tool_result":
            turns.append(turn)
        else:  # an error step (step limit, budget, failed call) is not a model turn
            turns.append(None)
        previous = step
    return turns


def annotate_steps(steps: list[AgentStep], provider: str | None) -> list[AgentStep]:
    turns = _turns(steps)
    thoughts = {t: s.content for s, t in zip(steps, turns, strict=True) if s.kind == "thought"}
    out: list[AgentStep] = []
    for i, (step, turn) in enumerate(zip(steps, turns, strict=True)):
        update: dict[str, Any] = {"turn": turn}
        if step.kind == "tool_call":
            result = steps[i + 1] if i + 1 < len(steps) else None
            error = (
                error_of(result.content)
                if result is not None and result.kind == "tool_result"
                else None
            )
            rule = rule_for_error(error) if error is not None else None
            update |= {
                "rationale": thoughts.get(turn) if turn is not None else None,
                "decision": decision_for(step.tool or "", step.arguments),
                "outcome": "rejected" if error is not None else "accepted",
                "blocked_by_rule": rule.ref() if rule else None,
            }
        if step.model is not None and step.provider is None and provider is not None:
            update["provider"] = provider
        out.append(step.model_copy(update=update))
    return out


def annotate_run(run: AgentRun) -> AgentRun:
    return run.model_copy(update={"steps": annotate_steps(run.steps, run.provider)})
