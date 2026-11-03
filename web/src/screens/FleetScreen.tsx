import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import StatusChip from "../components/StatusChip";
import type { Turbine } from "../types";

/**
 * Fleet screen: turbines ranked by priority with status chips.
 * This is a functional first pass; richer detail arrives in FEAT-002.
 */
export default function FleetScreen() {
  const [turbines, setTurbines] = useState<Turbine[]>([]);

  useEffect(() => {
    let active = true;
    api.getFleet().then((rows) => {
      if (active) setTurbines(rows);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="screen" aria-labelledby="fleet-heading">
      <header className="screen__header">
        <h1 id="fleet-heading">Fleet</h1>
        <p className="screen__sub">Turbines ranked by inspection priority.</p>
      </header>

      <table className="data-table" data-testid="fleet-table">
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Turbine</th>
            <th scope="col">Status</th>
            <th scope="col">Max severity</th>
            <th scope="col">Defects</th>
            <th scope="col">Latest</th>
          </tr>
        </thead>
        <tbody>
          {turbines.map((t) => (
            <tr key={t.id} data-testid="fleet-row">
              <td>{t.rank}</td>
              <td>
                <Link to={`/inspections/${t.latestInspectionId}`}>{t.name}</Link>
              </td>
              <td>
                <StatusChip status={t.status} />
              </td>
              <td>{t.maxSeverity}</td>
              <td>{t.defectCount}</td>
              <td>
                <Link to={`/inspections/${t.latestInspectionId}`}>{t.latestInspectionId}</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
