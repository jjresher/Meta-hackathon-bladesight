import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { AgentStep } from "../types";

/**
 * Agent trace screen: a first pass showing each tool-call step in order.
 * Richer step detail arrives in FEAT-002.
 */
export default function RunsScreen() {
  const [trace, setTrace] = useState<AgentStep[]>([]);

  useEffect(() => {
    let active = true;
    api.getAgentTrace().then((steps) => {
      if (active) setTrace(steps);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="screen" aria-labelledby="runs-heading">
      <header className="screen__header">
        <h1 id="runs-heading">Agent trace</h1>
        <p className="screen__sub">Each tool call the fleet agent made, step by step.</p>
      </header>

      <ol className="trace" data-testid="trace">
        {trace.map((step) => (
          <li key={step.index} className="trace__step" data-testid="trace-step">
            <code className="trace__tool">{step.tool}</code>
            <p className="trace__output">{step.output}</p>
            {step.note && <p className="trace__note">{step.note}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}
