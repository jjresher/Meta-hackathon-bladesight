import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { Async } from "../components/PageState";
import { InfoIcon } from "../components/icons";
import { useAsyncData } from "../hooks/useAsyncData";
import { dateTime, duration, usd } from "../lib/format";
import type { AgentRun, AgentStep } from "../types";

type Filter = "all" | "tools" | "thoughts";

const KIND_LABEL: Record<AgentStep["kind"], string> = {
  thought: "Thought",
  tool_call: "Tool call",
  tool_result: "Result",
  final: "Final",
  error: "Error",
};

const STATUS_LABEL: Record<AgentRun["status"], string> = {
  completed: "Completed",
  step_limit: "Stopped at the step limit",
  budget_exceeded: "Stopped at the budget cap",
  error: "Failed",
};

function prettyArgs(args: AgentStep["arguments"]): string {
  if (!args || Object.keys(args).length === 0) return "no arguments";
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join("\n");
}

function tryPretty(content: string): string {
  try {
    return JSON.stringify(JSON.parse(content), null, 1);
  } catch {
    return content;
  }
}

function Step({ step }: { step: AgentStep }) {
  const long = step.kind === "tool_result" && step.content.length > 220;
  return (
    <li className={`step step--${step.kind}`} data-testid="trace-step" data-kind={step.kind}>
      <span className="step__index num" aria-label={`Step ${step.index}`}>
        {step.index}
      </span>
      <div className="step__body">
        <p className="step__head">
          <span className="step__kind">{KIND_LABEL[step.kind]}</span>
          {step.tool && <code className="step__tool">{step.tool}</code>}
        </p>
        {step.kind === "tool_call" && <pre className="step__args">{prettyArgs(step.arguments)}</pre>}
        {step.kind === "tool_result" &&
          (long ? (
            <details>
              <summary>{step.content.slice(0, 180)}…</summary>
              <pre className="step__args">{tryPretty(step.content)}</pre>
            </details>
          ) : (
            <p className="step__text step__text--mono">{step.content}</p>
          ))}
        {(step.kind === "thought" || step.kind === "final" || step.kind === "error") && (
          <p className="step__text">{step.content}</p>
        )}
      </div>
      <div className="step__stats num">
        {step.duration_ms > 0 && <span>{duration(step.duration_ms)}</span>}
        {step.cost_usd > 0 && <span>{usd(step.cost_usd)}</span>}
      </div>
    </li>
  );
}

function RunBody({ run }: { run: AgentRun }) {
  const [filter, setFilter] = useState<Filter>("all");
  const calls = run.steps.filter((s) => s.kind === "tool_call");
  const toolCounts = new Map<string, number>();
  for (const call of calls) toolCounts.set(call.tool ?? "?", (toolCounts.get(call.tool ?? "?") ?? 0) + 1);
  const steps = run.steps.filter((s) => {
    if (filter === "tools") return s.kind === "tool_call" || s.kind === "tool_result";
    if (filter === "thoughts") return s.kind === "thought" || s.kind === "final" || s.kind === "error";
    return true;
  });
  const wallMs = run.finished_at ? new Date(run.finished_at).getTime() - new Date(run.started_at).getTime() : null;

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Agent trace</p>
        <h1>
          {calls.length} tool calls, one report, {run.work_order_ids.length} work orders
        </h1>
        <p className="lede">
          The ranking is a fixed score, not a model opinion. Work orders are created only through tools that refuse an
          unverified defect, and the report can only cite work orders that exist. The report's wording is the model's.
        </p>
      </header>

      {run.replay && (
        <p className="note" data-testid="replay-note">
          <InfoIcon className="note__icon" />
          <span>
            <strong>Replay.</strong> This is a recorded run: viewing it makes no model call and costs nothing. The cost
            below is what the original run spent.
          </span>
        </p>
      )}

      <dl className="stats stats--run">
        <div className="stat">
          <dt className="stat__label">status</dt>
          <dd className="stat__value">{STATUS_LABEL[run.status]}</dd>
        </div>
        <div className="stat">
          <dt className="stat__label">{run.provider === "meta" ? "Meta Model API" : run.provider}</dt>
          <dd className="stat__value num">{run.model}</dd>
        </div>
        <div className="stat">
          <dt className="stat__label">run cost (USD)</dt>
          <dd className="stat__value num">{usd(run.total_cost_usd)}</dd>
        </div>
        <div className="stat">
          <dt className="stat__label">wall time · {dateTime(run.started_at)}</dt>
          <dd className="stat__value num">{wallMs != null ? duration(wallMs) : "n/a"}</dd>
        </div>
        <div className="stat">
          <dt className="stat__label">steps</dt>
          <dd className="stat__value num">{run.steps.length}</dd>
        </div>
      </dl>

      <div className="trace-tools">
        <ul className="tool-tally" aria-label="Tool calls by tool">
          {[...toolCounts.entries()].map(([tool, n]) => (
            <li key={tool}>
              <code>{tool}</code> <span className="num">×{n}</span>
            </li>
          ))}
        </ul>
        <div className="seg seg--filters" role="group" aria-label="Filter steps">
          {(
            [
              ["all", "All steps"],
              ["tools", "Tool calls"],
              ["thoughts", "Thoughts"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`seg__item${filter === key ? " is-active" : ""}`}
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <ol className="trace" data-testid="trace">
        {steps.map((step) => (
          <Step key={step.index} step={step} />
        ))}
      </ol>
      <p className="trace-foot">
        Output: <Link to="/work-orders">{run.work_order_ids.length} work orders and the report</Link>
        {run.report_id ? <> ({run.report_id})</> : null}.
      </p>
    </>
  );
}

export default function RunsScreen() {
  const { id } = useParams();
  const state = useAsyncData(async () => {
    if (id) return api.run(id);
    const runs = await api.runs();
    const latest = [...runs].sort((a, b) => a.started_at.localeCompare(b.started_at)).at(-1);
    if (!latest) throw new Error("No agent run has been recorded yet.");
    return latest;
  }, [id]);
  return (
    <section className="screen" aria-label="Agent trace">
      <Async state={state} what="the agent trace">
        {(run) => <RunBody run={run} />}
      </Async>
    </section>
  );
}
