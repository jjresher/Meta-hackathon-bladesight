import { Link } from "react-router-dom";

import { api } from "../api/client";
import SeverityScale from "../components/SeverityScale";
import StatusChip from "../components/StatusChip";
import { InfoIcon } from "../components/icons";
import { useAsyncData } from "../hooks/useAsyncData";
import type { Turbine } from "../types";

/** Extract the two inspection years a turbine compares, newest first. */
function yearsCompared(t: Turbine): string {
  const years = t.inspectionIds
    .map((id) => {
      const match = /(\d{4})$/.exec(id);
      return match ? Number(match[1]) : null;
    })
    .filter((y): y is number => y !== null)
    .sort((a, b) => b - a);
  if (years.length >= 2) return `${years[0]} vs ${years[1]}`;
  if (years.length === 1) return `${years[0]}`;
  return "—";
}

/**
 * Fleet screen: every turbine ranked by inspection priority, each row carrying
 * a text+shape status chip, worst severity, defect count and the years
 * compared, linking to the turbine's latest inspection.
 */
export default function FleetScreen() {
  const state = useAsyncData(() => api.getFleet(), []);

  if (state.status === "loading") {
    return (
      <section className="screen">
        <p className="state">Loading fleet…</p>
      </section>
    );
  }
  if (state.status === "error") {
    return (
      <section className="screen">
        <p className="state" role="alert">
          Could not load the fleet: {state.error.message}
        </p>
      </section>
    );
  }

  const turbines = state.data;
  const maxPriority = turbines.reduce((m, t) => Math.max(m, t.priority), 1);
  const attention = turbines.filter((t) => t.status !== "ok").length;

  return (
    <section className="screen" aria-labelledby="fleet-heading">
      <header className="screen__header">
        <p className="screen__eyebrow">Fleet overview</p>
        <h1 id="fleet-heading">Fleet</h1>
        <p className="screen__sub">
          {turbines.length} turbines ranked by inspection priority. {attention} need attention
          (review or re-inspect) before any repair is scheduled.
        </p>
      </header>

      <p className="note">
        <InfoIcon className="note__icon" />
        <span>
          Synthetic farm built from real DTU drone photos. Priority blends the worst verified
          verdict, max severity and defect count; no repair is recommended without a verified
          assessment.
        </span>
      </p>

      <div className="table-wrap">
        <table className="data-table" data-testid="fleet-table">
          <thead>
            <tr>
              <th scope="col" className="col-num">
                Rank
              </th>
              <th scope="col">Turbine</th>
              <th scope="col">Status</th>
              <th scope="col" className="col-optional">
                Priority
              </th>
              <th scope="col" className="col-optional">
                Max severity
              </th>
              <th scope="col" className="col-num col-optional">
                Defects
              </th>
              <th scope="col" className="col-optional">
                Years compared
              </th>
            </tr>
          </thead>
          <tbody>
            {turbines.map((t) => (
              <tr key={t.id} data-testid="fleet-row">
                <td className="col-num">
                  <span className={`rank-badge${t.rank <= 3 ? " rank-badge--top" : ""}`}>
                    {t.rank}
                  </span>
                </td>
                <td>
                  <Link to={`/inspections/${t.latestInspectionId}`} className="turbine-cell">
                    <span className="turbine-cell__name">{t.name}</span>
                    <span className="turbine-cell__id">{t.latestInspectionId}</span>
                  </Link>
                </td>
                <td>
                  <StatusChip status={t.status} small />
                </td>
                <td className="col-optional">
                  <span className="pbar">
                    <span className="pbar__track">
                      <span
                        className="pbar__fill"
                        style={{ width: `${Math.round((t.priority / maxPriority) * 100)}%` }}
                      />
                    </span>
                    <span className="pbar__val">{t.priority.toFixed(1)}</span>
                  </span>
                </td>
                <td className="col-optional">
                  <SeverityScale value={t.maxSeverity} />
                </td>
                <td className="col-num col-optional">{t.defectCount}</td>
                <td className="col-optional num">{yearsCompared(t)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
