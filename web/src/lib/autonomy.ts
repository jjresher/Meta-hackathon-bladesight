import type { AgentRun, AgentStep, WorkOrder, WorkOrderKind } from "../types";

/** What the agent did on its own, counted from its stored trace (no model call, nothing inferred). */
export interface Autonomy {
  steps: number;
  turns: number | null;
  calls: AgentStep[];
  byTool: [string, number][];
  withReason: number;
  rejected: AgentStep[];
  /** calls whose outcome was not recorded: a rejection count would be unknown for them */
  unrecorded: number;
}

export function autonomyOf(run: AgentRun): Autonomy {
  const calls = run.steps.filter((s) => s.kind === "tool_call");
  const byTool = new Map<string, number>();
  for (const call of calls) {
    const tool = call.tool ?? "unnamed tool";
    byTool.set(tool, (byTool.get(tool) ?? 0) + 1);
  }
  const turns = run.steps.map((s) => s.turn).filter((t): t is number => t != null);
  return {
    steps: run.steps.length,
    turns: turns.length ? Math.max(...turns) : null,
    calls,
    byTool: [...byTool.entries()].sort((a, b) => a[0].localeCompare(b[0])),
    withReason: calls.filter((c) => c.rationale).length,
    rejected: calls.filter((c) => c.outcome === "rejected"),
    unrecorded: calls.filter((c) => c.outcome == null).length,
  };
}

/** Work orders a run wrote, by kind. Falls back to the run's own id list when orders lack run_id. */
export function ordersOfRun(run: AgentRun, orders: WorkOrder[]): Record<WorkOrderKind, number> & { total: number } {
  const mine = orders.filter((o) => o.run_id === run.id || (!o.run_id && run.work_order_ids.includes(o.id)));
  const count = (k: WorkOrderKind) => mine.filter((o) => o.kind === k).length;
  return { repair: count("repair"), monitor: count("monitor"), reinspect: count("reinspect"), total: mine.length };
}

/** The latest stored run (by start time). */
export function latestRun(runs: AgentRun[]): AgentRun | undefined {
  return [...runs].sort((a, b) => a.started_at.localeCompare(b.started_at)).at(-1);
}
