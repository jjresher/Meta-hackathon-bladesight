import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { ModelBadge } from "../components/Chips";
import { Async } from "../components/PageState";
import { InfoIcon } from "../components/icons";
import { GUARD_RULES } from "../evidence";
import { useAsyncData } from "../hooks/useAsyncData";
import { autonomyOf, latestRun, ordersOfRun } from "../lib/autonomy";
import { dateTime, duration, usd } from "../lib/format";
import { useRun } from "../lib/run";
import type { AgentRun, AgentStep, WorkOrder } from "../types";

type View = "decisions" | "all";

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

/** The model's own text before a call, or an explicit "no stated reason": never filled in. */
function Why({ text }: { text: string | null }) {
  return text ? (
    <q className="why__text">{text}</q>
  ) : (
    <span className="why__none" data-testid="no-reason">
      no stated reason
    </span>
  );
}

function Outcome({ step }: { step: AgentStep }) {
  if (!step.outcome) return null;
  return (
    <span className={`outcome outcome--${step.outcome}`} data-testid="outcome">
      {step.outcome === "accepted" ? "accepted" : "rejected"}
    </span>
  );
}

function BlockedBy({ step }: { step: AgentStep }) {
  if (!step.blocked_by_rule) return null;
  return (
    <p className="blocked" data-testid="blocked-by">
      Stopped by rule <code>{step.blocked_by_rule.id}</code>: {step.blocked_by_rule.text}
    </p>
  );
}

/** Each tool call with the result the tool returned right after it. */
function pairCalls(steps: AgentStep[]): { call: AgentStep; result: AgentStep | undefined }[] {
  const used = new Set<number>();
  return steps
    .map((step, i) => ({ step, i }))
    .filter(({ step }) => step.kind === "tool_call")
    .map(({ step, i }) => {
      const result = steps.find((s, j) => j > i && !used.has(j) && s.kind === "tool_result" && s.tool === step.tool);
      if (result) used.add(steps.indexOf(result));
      return { call: step, result };
    });
}

/** Tool calls grouped by model turn: why (once per turn), then what each call decided. */
function Decisions({ run }: { run: AgentRun }) {
  const pairs = pairCalls(run.steps);
  const turns: { turn: number | null; items: typeof pairs }[] = [];
  for (const pair of pairs) {
    const last = turns.at(-1);
    if (last && last.turn !== null && last.turn === pair.call.turn) last.items.push(pair);
    else turns.push({ turn: pair.call.turn, items: [pair] });
  }
  return (
    <ol className="turns" data-testid="trace">
      {turns.map(({ turn, items }) => {
        const reasons = [...new Set(items.map((p) => p.call.rationale))];
        const first = items[0].call;
        return (
          <li key={first.index} className="turn" data-testid="decision-turn">
            <header className="turn__head">
              <span className="turn__label">{turn != null ? `Turn ${turn}` : "Call"}</span>
              <ModelBadge model={first.model} provider={first.provider} />
            </header>
            {reasons.map((reason, i) => (
              <p key={i} className="why">
                <span className="why__label">Why</span> <Why text={reason} />
              </p>
            ))}
            <ol className="calls">
              {items.map(({ call, result }) => (
                <li
                  key={call.index}
                  className={`call${call.outcome === "rejected" ? " is-rejected" : ""}`}
                  data-testid="trace-step"
                  data-kind="tool_call"
                >
                  <p className="call__line">
                    <span className="call__index num" aria-label={`Step ${call.index}`}>
                      {call.index}
                    </span>
                    <code className="step__tool">{call.tool}</code>
                    <span className="call__decision">{call.decision ?? prettyArgs(call.arguments)}</span>
                    <Outcome step={call} />
                  </p>
                  <BlockedBy step={call} />
                  <details className="call__details">
                    <summary>Arguments and result</summary>
                    <pre className="step__args">{prettyArgs(call.arguments)}</pre>
                    {result && <pre className="step__args">{tryPretty(result.content)}</pre>}
                  </details>
                </li>
              ))}
            </ol>
          </li>
        );
      })}
    </ol>
  );
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
          {step.kind === "tool_call" && <Outcome step={step} />}
          <ModelBadge model={step.model} provider={step.provider} />
        </p>
        {step.kind === "tool_call" && (
          <>
            <p className="why">
              <span className="why__label">Why</span> <Why text={step.rationale} />
            </p>
            {step.decision && (
              <p className="why">
                <span className="why__label">Decided</span> {step.decision}
              </p>
            )}
            <BlockedBy step={step} />
            <pre className="step__args">{prettyArgs(step.arguments)}</pre>
          </>
        )}
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

function Autonomy({ run, orders }: { run: AgentRun; orders: WorkOrder[] }) {
  const a = autonomyOf(run);
  const o = ordersOfRun(run, orders);
  const nRules = GUARD_RULES.rules.length;
  return (
    <div className="autonomy" data-testid="autonomy">
      <section className="autonomy__box panel" aria-labelledby="autonomy-did">
        <h2 id="autonomy-did" className="panel__title">
          What the agent did on its own
        </h2>
        <ul className="autonomy__list">
          <li>
            <span className="num">{a.turns ?? "n/a"}</span> model turns, <span className="num">{a.calls.length}</span> tool
            calls, <span className="num">{a.steps}</span> steps in the trace.
          </li>
          <li>
            <ul className="tool-tally" aria-label="Tool calls by tool">
              {a.byTool.map(([tool, n]) => (
                <li key={tool}>
                  <code>{tool}</code> <span className="num">×{n}</span>
                </li>
              ))}
            </ul>
          </li>
          <li data-testid="reason-count">
            {a.withReason === 0 ? (
              <>The model wrote no text before any call, so every call shows "no stated reason".</>
            ) : (
              <>
                <span className="num">{a.withReason}</span> of <span className="num">{a.calls.length}</span> calls came
                with the model's own text before them.
              </>
            )}
          </li>
          <li data-testid="order-count">
            <span className="num">{o.repair}</span> repair, <span className="num">{o.monitor}</span> monitor and{" "}
            <span className="num">{o.reinspect}</span> re-inspection orders. Defects that are not verified get a
            re-inspection request, never a repair.
          </li>
        </ul>
      </section>

      <section className="autonomy__box panel" aria-labelledby="autonomy-rules">
        <h2 id="autonomy-rules" className="panel__title">
          Rules that could stop it
        </h2>
        <p className="autonomy__rules" data-testid="rule-summary">
          {a.rejected.length === 0 ? (
            <>No call was rejected by a rule in this run.</>
          ) : (
            <>
              <span className="num">{a.rejected.length}</span> call{a.rejected.length === 1 ? " was" : "s were"} rejected:{" "}
              {a.rejected.map((c) => `step ${c.index} (${c.blocked_by_rule?.id ?? "tool error"})`).join(", ")}.
            </>
          )}{" "}
          These rules are enforced in code by the tools, not only stated in the prompt:
        </p>
        <details className="rules">
          <summary>
            The {nRules} rules (<code>{GUARD_RULES.file.replace("src/bladesight/", "")}</code>)
          </summary>
          <ul className="rules__list" data-testid="guard-rules">
            {GUARD_RULES.rules.map((rule) => (
              <li key={rule.id}>
                <code>{rule.id}</code> {rule.text}
              </li>
            ))}
          </ul>
        </details>
      </section>
    </div>
  );
}

function RunBody({ run, orders }: { run: AgentRun; orders: WorkOrder[] }) {
  const [view, setView] = useState<View>("decisions");
  const calls = run.steps.filter((s) => s.kind === "tool_call");
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
          <dt className="stat__label">agent model</dt>
          <dd className="stat__value">
            <ModelBadge model={run.model} provider={run.provider} />
          </dd>
        </div>
        <div className="stat">
          <dt className="stat__label">run cost (USD)</dt>
          <dd className="stat__value num">{usd(run.total_cost_usd)}</dd>
        </div>
        <div className="stat">
          <dt className="stat__label">wall time · {dateTime(run.started_at)}</dt>
          <dd className="stat__value num">{wallMs != null ? duration(wallMs) : "n/a"}</dd>
        </div>
      </dl>

      <Autonomy run={run} orders={orders} />

      <div className="trace-tools">
        <h2 className="section-title">{view === "decisions" ? "Decisions, turn by turn" : "Every step"}</h2>
        <div className="seg seg--filters" role="group" aria-label="Trace view">
          {(
            [
              ["decisions", "Decisions"],
              ["all", "All steps"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`seg__item${view === key ? " is-active" : ""}`}
              aria-pressed={view === key}
              onClick={() => setView(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {view === "decisions" ? (
        <Decisions run={run} />
      ) : (
        <ol className="trace" data-testid="trace">
          {run.steps.map((step) => (
            <Step key={step.index} step={step} />
          ))}
        </ol>
      )}
      <p className="trace-foot">
        Output: <Link to="/work-orders">{run.work_order_ids.length} work orders and the report</Link>
        {run.report_id ? <> ({run.report_id})</> : null}.
      </p>
    </>
  );
}

export default function RunsScreen() {
  const { id } = useParams();
  const { provider } = useRun();
  const state = useAsyncData(async () => {
    const [run, orders] = await Promise.all([
      id
        ? api.run(id, provider)
        : api.runs(provider).then((runs) => {
            const latest = latestRun(runs);
            if (!latest) throw new Error("No agent run has been recorded yet.");
            return latest;
          }),
      api.workOrders(provider).catch(() => [] as WorkOrder[]),
    ]);
    return { run, orders };
  }, [id, provider]);
  return (
    <section className="screen" aria-label="Agent trace">
      <Async state={state} what="the agent trace">
        {({ run, orders }) => <RunBody run={run} orders={orders} />}
      </Async>
    </section>
  );
}
