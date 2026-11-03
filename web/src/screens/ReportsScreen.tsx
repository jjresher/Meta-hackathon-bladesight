import { useEffect, useState } from "react";

import { api } from "../api/client";
import StatusChip from "../components/StatusChip";
import type { Report } from "../types";

/**
 * Work orders and report screen: a first pass listing the work orders and
 * their cited defect ids. Fuller report layout arrives in FEAT-002.
 */
export default function ReportsScreen() {
  const [report, setReport] = useState<Report | null>(null);

  useEffect(() => {
    let active = true;
    api.getReport().then((data) => {
      if (active) setReport(data);
    });
    return () => {
      active = false;
    };
  }, []);

  if (!report) {
    return (
      <section className="screen">
        <p>Loading report…</p>
      </section>
    );
  }

  return (
    <section className="screen" aria-labelledby="reports-heading">
      <header className="screen__header">
        <h1 id="reports-heading">Work orders &amp; report</h1>
        <p className="screen__sub">{report.summary}</p>
      </header>

      <div className="work-order-list" data-testid="work-order-list">
        {report.workOrders.map((wo) => (
          <article key={wo.id} className="work-order" data-testid="work-order">
            <div className="work-order__head">
              <h2>
                {wo.id} · {wo.title}
              </h2>
              <StatusChip status={wo.priority} />
            </div>
            <p>{wo.action}</p>
            <p className="work-order__rationale">{wo.rationale}</p>
            <p className="work-order__cites">
              Cites defects: {wo.defectIds.join(", ")}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
