"""The fleet agent: a Muse Spark tool-calling loop with a step limit, a budget and a full trace.

The agent reads the stored, verified results through `FleetTools`, creates work orders (only for
verified defects: enforced by the tool), asks for re-inspection where the evidence is weak, and
writes the report. Every step is an `AgentStep`; the finished `AgentRun` is saved to the store, and
because every model call is cached by `bladesight.meta`, a recorded run replays for free.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from ..contracts import AgentRun, AgentStep
from ..meta import ChatMessage, ChatRequest, MetaClient, MetaError, MetaSettings, ToolCall
from .store import Store
from .tools import FleetTools, tool_specs
from .trace import annotate_steps

MAX_STEPS = 40
MAX_COST_USD = 1.0
MAX_TOKENS = 3000
TRACE_CHARS = 700

SYSTEM = """You are the planning agent of a wind farm inspection system. Drone photos of blades \
were already analysed: SAM 3.1 found defects, Muse Spark graded each one against a severity \
rubric (1 cosmetic to 5 critical) and a second look verified it. You plan the maintenance for the \
whole farm using ONLY the tools; you cannot see photos.

Rules:
- Never state a defect, a severity or a trend that a tool did not return. Cite defect ids.
- Create a repair or monitor work order only for defects whose verdict is "ok". For defects with \
verdict needs_review or reinspect (or no grade), call request_reinspection instead: low \
confidence means asking for better evidence, never guessing.
- Use list_turbines for the ranking and do not re-rank it; explain it. The farm is synthetic (an \
invented grouping of real photos); years 2017/2018 are part of that grouping, say so in the report.
- Severity 4-5 -> P1 repair, 3 -> P2 repair, 2 -> P3 monitor; severity 1 needs no order.
- Work through at most the 6 highest-ranked turbines: get_inspection of the latest inspection, \
compare_inspections when there are two, then orders. Then call write_report once with a short \
Markdown report (ranking, work orders as WO-001 style ids, re-inspections, limits) and stop with a \
two-sentence summary."""
USER = "Plan the maintenance for the farm now and write the report."


def _trace(text: str) -> str:
    return text if len(text) <= TRACE_CHARS else text[:TRACE_CHARS] + " ..."


def run_agent(
    client: MetaClient,
    settings: MetaSettings,
    store: Store,
    *,
    max_steps: int = MAX_STEPS,
    max_cost_usd: float = MAX_COST_USD,
    run_id: str | None = None,
    provider: str = "meta",
    model: str | None = None,
    max_tokens: int = MAX_TOKENS,
) -> AgentRun:
    """`model` defaults to `settings.chat_model` (Muse Spark); pass the Baseten model id and a
    larger `max_tokens` for Muse Spark Open (`bladesight.chat.ChatTarget`)."""
    model = model or settings.chat_model
    started = datetime.now(UTC)
    run_id = run_id or f"run-{started:%Y%m%d-%H%M%S}"
    tools = FleetTools(store, run_id)
    messages = [ChatMessage.of("system", SYSTEM), ChatMessage.of("user", USER)]
    steps: list[AgentStep] = []
    status = "completed"
    spent = 0.0
    chat_records_start = len(client.records)

    def add(kind: str, content: str, ms: int, cost: float = 0.0, **extra: Any) -> None:
        steps.append(
            AgentStep.model_validate(
                {
                    "index": len(steps),
                    "kind": kind,
                    "content": content,
                    "duration_ms": ms,
                    "cost_usd": cost,
                    "model": model if kind not in ("tool_result", "error") else None,
                    "turn": turns if kind != "error" else None,
                    **extra,
                }
            )
        )

    turns = 0
    while True:
        if turns >= max_steps:
            status = "step_limit"
            add("error", f"step limit of {max_steps} model turns reached", 0)
            break
        if spent >= max_cost_usd:
            status = "budget_exceeded"
            add("error", f"budget of {max_cost_usd:.2f} USD reached", 0)
            break
        turns += 1
        t0 = time.monotonic()
        before = len(client.records)
        try:
            reply = client.chat(
                ChatRequest(
                    model=model,
                    messages=messages,
                    tools=tool_specs(),
                    max_tokens=max_tokens,
                )
            )
        except MetaError as error:  # keep the partial trace instead of losing it
            status = "error"
            add(
                "error",
                f"model call failed: {str(error)[:300]}",
                int((time.monotonic() - t0) * 1000),
            )
            break
        ms = int((time.monotonic() - t0) * 1000)
        cost = sum(r.cost_usd for r in client.records[before:])
        spent += cost
        if not reply.tool_calls:
            add("final", reply.text.strip() or "(no text)", ms, cost)
            break
        if reply.text.strip():
            add("thought", _trace(reply.text.strip()), 0)
        messages.append(ChatMessage.of("assistant", reply.text, tool_calls=list(reply.tool_calls)))
        for number, call in enumerate(reply.tool_calls):
            add(
                "tool_call",
                f"{call.name}({_trace(str(call.arguments))})",
                ms if number == 0 else 0,
                cost if number == 0 else 0.0,
                tool=call.name,
                arguments=call.arguments,
            )
            t1 = time.monotonic()
            result = _execute(tools, call)
            add(
                "tool_result",
                _trace(result),
                int((time.monotonic() - t1) * 1000),
                tool=call.name,
            )
            messages.append(ChatMessage.of("tool", result, tool_call_id=call.id))

    orders = [o.model_copy(update={"model": model, "provider": provider}) for o in tools.orders]
    store.save_work_orders(orders)
    report_id = None
    if tools.report is not None:
        report = tools.report.model_copy(update={"model": model, "provider": provider})
        store.save_report(report)
        report_id = report.id
    chat_records = client.records[chat_records_start:]
    run = AgentRun(
        id=run_id,
        status=status,  # type: ignore[arg-type]
        replay=bool(chat_records) and all(r.source == "cache" for r in chat_records),
        model=model,
        provider=provider,  # type: ignore[arg-type]
        started_at=started,
        finished_at=datetime.now(UTC),
        steps=annotate_steps(steps, provider),
        total_cost_usd=round(spent, 6),
        work_order_ids=[o.id for o in orders],
        report_id=report_id,
    )
    store.save_run(run)
    return run


def _execute(tools: FleetTools, call: ToolCall) -> str:
    return tools.call(call.name, call.arguments)
