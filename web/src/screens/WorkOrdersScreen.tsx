import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { Async, Loading } from "../components/PageState";
import { TurbineArt } from "../components/icons";
import { ModelBadge } from "../components/Chips";
import { useAsyncData, type AsyncState } from "../hooks/useAsyncData";
import { PROVIDER_LABEL } from "../lib/models";
import { useRun } from "../lib/run";
import { dateTime, defectLink, shortDefectId } from "../lib/format";
import { Markdown } from "../lib/markdown";
import type { Report, WorkOrder, WorkOrderKind } from "../types";

const KIND_LABEL: Record<WorkOrderKind, string> = {
  repair: "Repair",
  monitor: "Monitor",
  reinspect: "Reinspect",
};

function OrderCard({ order }: { order: WorkOrder }) {
  return (
    <article className={`wo wo--${order.kind}`} id={order.id} data-testid="work-order">
      <header className="wo__head">
        <div>
          <p className="wo__id num">{order.id}</p>
          <h3 className="wo__title">
            {KIND_LABEL[order.kind]} · {order.turbine_id}
          </h3>
        </div>
        <div className="wo__badges">
          <span className={`prio prio--${order.priority}`} title="Priority">
            {order.priority}
          </span>
          <span className="due num">within {order.due_within_days} days</span>
        </div>
      </header>

      <p className="wo__action">{order.action}</p>
      <p className="wo__why">{order.rationale}</p>

      <div className="wo__cites">
        <p className="wo__label">Cites {order.defect_ids.length} defect{order.defect_ids.length === 1 ? "" : "s"}</p>
        <ul className="cite-list">
          {order.defect_ids.map((id) => (
            <li key={id}>
              <Link to={defectLink(id)} className="cite" title={`Open ${id} in the viewer`}>
                <span className="cite__insp">{id.split("/")[0]}</span>
                <span className="cite__tile">{id.split("/")[1]?.replace("DJI_", "")}</span>
                <span className="cite__id">{shortDefectId(id)}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>

      <details className="wo__evidence">
        <summary>Evidence ({order.evidence.length})</summary>
        <ul>
          {order.evidence.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </details>

      <footer className="wo__foot">
        <Link to={`/inspections/${encodeURIComponent(order.inspection_id)}`}>Open {order.inspection_id}</Link>
        <span className="wo__by">
          created by {order.created_by}
          <ModelBadge model={order.model} provider={order.provider} />
          {order.run_id && (
            <>
              {" "}
              in <Link to={`/runs/${encodeURIComponent(order.run_id)}`}>{order.run_id}</Link>
            </>
          )}
        </span>
      </footer>
    </article>
  );
}

function ReportPanel({ report }: { report: Report }) {
  return (
    <aside className="report panel" aria-label="Fleet report">
      <header className="report__head">
        <p className="eyebrow">Report written by the agent</p>
        <h2>{report.title}</h2>
        <p className="report__meta">
          <span className="num">{report.model}</span> · {PROVIDER_LABEL[report.provider]} ·{" "}
          {dateTime(report.generated_at)} ·{" "}
          <Link to={`/runs/${encodeURIComponent(report.run_id)}`}>{report.run_id}</Link>
        </p>
      </header>
      <Markdown source={report.markdown} />
    </aside>
  );
}

function Body({ orders, report }: { orders: WorkOrder[]; report: AsyncState<Report | null> }) {
  const [kind, setKind] = useState<WorkOrderKind | "all">("all");
  const { hash } = useLocation();
  const shown = kind === "all" ? orders : orders.filter((o) => o.kind === kind);
  const count = (k: WorkOrderKind) => orders.filter((o) => o.kind === k).length;

  // Deep links (#WO-001) from the viewer or the fleet.
  useEffect(() => {
    if (!hash) return;
    let id = hash.slice(1);
    try {
      id = decodeURIComponent(id);
    } catch {
      // a malformed hash just does not match any order
    }
    document.getElementById(id)?.scrollIntoView({ block: "center" });
  }, [hash, orders]);

  return (
    <>
      <header className="page-head">
        <h1>
          {count("repair")} to repair, {count("reinspect")} to reinspect
        </h1>
        <p className="lede">
          Every order cites the defects and the verified assessments behind it. The agent does not write an order for a
          defect that is not verified: those get a reinspection request instead.
        </p>
      </header>

      <div className="split">
        <div>
          <div className="seg seg--filters" role="group" aria-label="Filter work orders">
            {(["all", "repair", "reinspect", "monitor"] as const).map((k) => (
              <button
                key={k}
                type="button"
                className={`seg__item${kind === k ? " is-active" : ""}`}
                aria-pressed={kind === k}
                onClick={() => setKind(k)}
              >
                {k === "all" ? `All ${orders.length}` : `${KIND_LABEL[k]} ${count(k)}`}
              </button>
            ))}
          </div>
          {shown.length === 0 ? (
            <p className="note note--empty">
              <TurbineArt className="note__art" />
              <span>No work orders of this kind.</span>
            </p>
          ) : (
            <div className="wo-list" data-testid="work-order-list">
              {shown.map((order) => (
                <OrderCard key={order.id} order={order} />
              ))}
            </div>
          )}
        </div>
        {report.status === "loading" && <Loading what="the report" />}
        {report.status === "ready" && report.data && <ReportPanel report={report.data} />}
        {report.status === "ready" && !report.data && (
          <p className="note note--empty">
            <TurbineArt className="note__art" />
            <span>No report has been written yet.</span>
          </p>
        )}
      </div>
    </>
  );
}

export default function WorkOrdersScreen() {
  const { provider } = useRun();
  const orders = useAsyncData(() => api.workOrders(provider), [provider]);
  const report = useAsyncData(() => api.latestReport(provider).catch(() => null), [provider]);
  return (
    <section className="screen" aria-label="Work orders">
      <Async state={orders} what="work orders">
        {(data) => <Body orders={data} report={report} />}
      </Async>
    </section>
  );
}
