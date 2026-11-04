import { api } from "../api/client";
import { InfoIcon } from "../components/icons";
import { useAsyncData } from "../hooks/useAsyncData";

/** Render tool arguments as compact, readable JSON. */
function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (entries.length === 0) return "{}";
  return entries.map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join("\n");
}

/**
 * Agent trace screen: the fleet agent's run as an ordered, inspectable list of
 * tool-call steps. Each step shows its index, the tool, the arguments, the
 * output and any rule/thought note.
 */
export default function RunsScreen() {
  const state = useAsyncData(() => api.getAgentTrace(), []);

  if (state.status === "loading") {
    return (
      <section className="screen">
        <p className="state">Loading agent trace…</p>
      </section>
    );
  }
  if (state.status === "error") {
    return (
      <section className="screen">
        <p className="state" role="alert">
          Could not load the agent trace: {state.error.message}
        </p>
      </section>
    );
  }

  const trace = state.data;

  return (
    <section className="screen" aria-labelledby="runs-heading">
      <header className="screen__header">
        <p className="screen__eyebrow">Agent run</p>
        <h1 id="runs-heading">Agent trace</h1>
        <p className="screen__sub">
          {trace.length} tool calls the fleet agent made, step by step — inputs, outputs and the
          rules it applied.
        </p>
      </header>

      <p className="note">
        <InfoIcon className="note__icon" />
        <span>
          Every ranking and work order is produced by these auditable tool calls, not by a free
          text guess.
        </span>
      </p>

      <ol className="trace" data-testid="trace">
        {trace.map((step) => (
          <li key={step.index} className="trace__step" data-testid="trace-step">
            <span className="trace__index" aria-hidden="true">
              {step.index}
            </span>
            <div className="trace__card">
              <code className="trace__tool">{step.tool}</code>
              <pre className="trace__args" aria-label="arguments">
                {formatArgs(step.args)}
              </pre>
              <p className="trace__output">{step.output}</p>
              {step.note && (
                <p className="trace__note">
                  <InfoIcon size={13} className="note__icon" />
                  <span>{step.note}</span>
                </p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
