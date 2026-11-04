import { Link } from "react-router-dom";

import { api } from "../api/client";
import StatusChip from "../components/StatusChip";
import { InfoIcon } from "../components/icons";
import { useAsyncData } from "../hooks/useAsyncData";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

/**
 * Work orders and report screen: the written fleet summary plus each generated
 * work order, every one citing the defect ids and the turbine it addresses.
 */
export default function ReportsScreen() {
  const state = useAsyncData(() => api.getReport(), []);

  if (state.status === "loading") {
    return (
      <section className="screen">
        <p className="state">Loading report…</p>
      </section>
    );
  }
  if (state.status === "error") {
    return (
      <section className="screen">
        <p className="state" role="alert">
          Could not load the report: {state.error.message}
        </p>
      </section>
    );
  }

  const report = state.data;
  const reinspect = report.workOrders.filter((w) => w.priority === "reinspect").length;
  const review = report.workOrders.filter((w) => w.priority === "needs_review").length;

  return (
    <section className="screen" aria-labelledby="reports-heading">
      <header className="screen__header">
        <p className="screen__eyebrow">Fleet report</p>
        <h1 id="reports-heading">Work orders &amp; report</h1>
        <p className="screen__sub">
          {report.workOrders.length} work orders generated: {reinspect} to re-inspect, {review} to
          review. Each cites the defect evidence behind it.
        </p>
      </header>

      <div className="panel report-summary">
        <p>{report.summary}</p>
        <div className="report-summary__meta">
          <span>Generated {formatDate(report.generatedAt)}</span>
          <span className="num">{report.rankedTurbineIds.length} turbines ranked</span>
        </div>
      </div>

      <p className="note">
        <InfoIcon className="note__icon" />
        <span>No claim without evidence: every work order links to the defect ids that justify it.</span>
      </p>

      <div className="work-order-list" data-testid="work-order-list">
        {report.workOrders.map((wo) => {
          const latest = `${wo.turbineId}-2018`;
          return (
            <article key={wo.id} className="work-order" data-testid="work-order">
              <div className="work-order__head">
                <div>
                  <h3>{wo.title}</h3>
                  <span className="work-order__id">
                    {wo.id} · Turbine {wo.turbineId}
                  </span>
                </div>
                <StatusChip status={wo.priority} small />
              </div>
              <p className="work-order__action">{wo.action}</p>
              <p className="work-order__rationale">{wo.rationale}</p>
              <div className="cites">
                <span>Turbine:</span>
                <Link to={`/inspections/${latest}`} className="cite-chip">
                  {wo.turbineId}
                </Link>
                <span>Cites defects:</span>
                {wo.defectIds.map((defectId) => (
                  <span key={defectId} className="cite-chip">
                    {defectId}
                  </span>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
