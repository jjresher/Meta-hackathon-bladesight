import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { EvalReport } from "../types";

/**
 * Evaluation screen: a first pass showing headline metrics, the threshold
 * curve points and the honest limitations. The SVG curve arrives in FEAT-002.
 */
export default function EvalScreen() {
  const [report, setReport] = useState<EvalReport | null>(null);

  useEffect(() => {
    let active = true;
    api.getEvalReport().then((data) => {
      if (active) setReport(data);
    });
    return () => {
      active = false;
    };
  }, []);

  if (!report) {
    return (
      <section className="screen">
        <p>Loading evaluation…</p>
      </section>
    );
  }

  return (
    <section className="screen" aria-labelledby="eval-heading">
      <header className="screen__header">
        <h1 id="eval-heading">Evaluation</h1>
        <p className="screen__sub">
          Split: {report.split} · IoU ≥ {report.iou}
        </p>
      </header>

      <dl className="metric-grid" data-testid="metric-grid">
        {Object.entries(report.metrics).map(([name, value]) => (
          <div key={name} className="metric">
            <dt>{name}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <h2>Limitations</h2>
      <ul className="limitations">
        {report.limitations.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
