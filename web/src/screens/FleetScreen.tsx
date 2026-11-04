import { Link } from "react-router-dom";

import { api } from "../api/client";
import { TrendBadge, TurbineStatusChip } from "../components/Chips";
import { Async } from "../components/PageState";
import SeverityScale from "../components/SeverityScale";
import { InfoIcon } from "../components/icons";
import { useAsyncData } from "../hooks/useAsyncData";
import { useRun } from "../lib/run";
import { defectsLabel, latestInspection } from "../lib/format";
import type { Fleet, Turbine } from "../types";

function Stat({ value, label, tone }: { value: number | string; label: string; tone?: "alert" | "review" }) {
  return (
    <div className={`stat${tone ? ` stat--${tone}` : ""}`}>
      <dt className="stat__label">{label}</dt>
      <dd className="stat__value num">{value}</dd>
    </div>
  );
}

function TurbineRow({ turbine, maxScore }: { turbine: Turbine; maxScore: number }) {
  const latest = latestInspection(turbine);
  const href = `/inspections/${encodeURIComponent(latest.id)}`;
  return (
    <li className={`frow frow--${turbine.status}`} data-testid="fleet-row">
      <span className={`rank${turbine.rank <= 3 ? " rank--top" : ""}`} aria-label={`Rank ${turbine.rank}`}>
        {turbine.rank}
      </span>

      <div className="frow__main">
        <Link to={href} className="frow__name stretched">
          {turbine.name}
          <span className="visually-hidden">, open latest inspection {latest.id}</span>
        </Link>
        <p className="frow__reason">{turbine.reason}</p>
      </div>

      <div className="frow__status">
        <TurbineStatusChip status={turbine.status} />
        <TrendBadge trend={turbine.trend} />
      </div>

      <div className="frow__score" title={`Priority score ${turbine.priority_score}`}>
        <span className="pbar">
          <span className="pbar__track">
            <span
              className="pbar__fill"
              style={{ width: `${maxScore > 0 ? Math.max(3, (turbine.priority_score / maxScore) * 100) : 0}%` }}
            />
          </span>
        </span>
        <span className="num frow__score-val">{turbine.priority_score.toFixed(2)}</span>
      </div>

      <div className="frow__sev">
        <SeverityScale value={latest.max_severity} />
        <span className="frow__sub">verified max, {latest.year}</span>
      </div>

      <div className="frow__counts num">
        <span>{defectsLabel(latest.n_defects)}</span>
        <span className="frow__sub">
          {latest.n_needs_review} review · {latest.n_reinspect} reinspect
        </span>
      </div>

      <div className="frow__years">
        {[...turbine.inspections]
          .sort((a, b) => a.year - b.year)
          .map((insp) => (
            <Link
              key={insp.id}
              to={`/inspections/${encodeURIComponent(insp.id)}`}
              className="year-chip"
              aria-label={`Open the ${insp.year} inspection of ${turbine.name}`}
            >
              {insp.year}
            </Link>
          ))}
        {turbine.open_work_orders > 0 && (
          <Link to="/work-orders" className="year-chip year-chip--wo" title="Open work orders">
            {turbine.open_work_orders} WO
          </Link>
        )}
      </div>
    </li>
  );
}

function FleetBody({ fleet }: { fleet: Fleet }) {
  const turbines = [...fleet.turbines].sort((a, b) => a.rank - b.rank);
  const maxScore = Math.max(0, ...turbines.map((t) => t.priority_score));
  const count = (status: Turbine["status"]) => turbines.filter((t) => t.status === status).length;
  const orders = turbines.reduce((sum, t) => sum + t.open_work_orders, 0);

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Fleet</p>
        <h1>{turbines.length} turbines, ranked by what needs a person first</h1>
        <p className="lede">
          Only <em>verified</em> defects (two looks agreed, rule checks passed) set a turbine's status and severity. A
          defect that needs review adds a quarter of its weight to the priority score; one that needs reinspection adds
          nothing. Both ask for a person or new photos.
        </p>
      </header>

      <p className="note" data-testid="fleet-note">
        <InfoIcon className="note__icon" />
        <span>
          {fleet.note}
        </span>
      </p>

      <dl className="stats">
        <Stat value={count("critical")} label="critical" tone="alert" />
        <Stat value={count("attention")} label="attention" tone="review" />
        <Stat value={count("needs_review")} label="need review" tone="review" />
        <Stat value={count("ok")} label="no verified issue" />
        <Stat value={orders} label="open work orders" />
      </dl>

      <div className="fhead" aria-hidden="true">
        <span>#</span>
        <span>Turbine</span>
        <span>Status</span>
        <span>Priority</span>
        <span>Severity</span>
        <span>Latest inspection</span>
        <span>Inspections</span>
      </div>
      <ol className="fleet-list" data-testid="fleet-list">
        {turbines.map((turbine) => (
          <TurbineRow key={turbine.id} turbine={turbine} maxScore={maxScore} />
        ))}
      </ol>
    </>
  );
}

export default function FleetScreen() {
  const { provider } = useRun();
  const state = useAsyncData(() => api.fleet(provider), [provider]);
  return (
    <section className="screen" aria-label="Fleet">
      <Async state={state} what="the fleet">
        {(fleet) => <FleetBody fleet={fleet} />}
      </Async>
    </section>
  );
}
