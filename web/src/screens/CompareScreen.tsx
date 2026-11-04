import { Link } from "react-router-dom";

import { api } from "../api/client";
import { ModelBadge } from "../components/Chips";
import { Async } from "../components/PageState";
import { InfoIcon } from "../components/icons";
import { OPEN_WEIGHTS_FARM as ow, evidenceUrl } from "../evidence";
import { useAsyncData } from "../hooks/useAsyncData";
import { autonomyOf, latestRun, ordersOfRun } from "../lib/autonomy";
import { STAGE_LABEL, modelLabel } from "../lib/models";
import { useRun } from "../lib/run";
import type { AgentRun, Fleet, ReplaySet, WorkOrder } from "../types";

interface Side {
  replay: ReplaySet;
  name: string;
  fleet: Fleet;
  run: AgentRun | undefined;
  orders: WorkOrder[];
}

const nameOf = (replay: ReplaySet): string => {
  const agent = replay.stages.find((s) => s.stage === "agent");
  return agent ? modelLabel(agent.model, agent.provider) : replay.label;
};

async function load(replays: ReplaySet[]): Promise<Side[]> {
  return Promise.all(
    replays.map(async (replay) => {
      const [fleet, runs, orders] = await Promise.all([
        api.fleet(replay.provider),
        api.runs(replay.provider),
        api.workOrders(replay.provider),
      ]);
      return { replay, name: nameOf(replay), fleet, run: latestRun(runs), orders };
    }),
  );
}

const capitalize = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1);

/** Stages run by the same model in both replays, and the ones that changed model. */
function sharedStages(a: ReplaySet, b: ReplaySet) {
  const same = a.stages.filter((s) => b.stages.some((t) => t.stage === s.stage && t.model === s.model && t.provider === s.provider));
  const changed = a.stages.filter((s) => !same.includes(s));
  return { same, changed };
}

function RunCard({ side, onShow }: { side: Side; onShow: () => void }) {
  const a = side.run ? autonomyOf(side.run) : null;
  const o = side.run ? ordersOfRun(side.run, side.orders) : null;
  return (
    <article className="cmp-run panel" data-testid="compare-run">
      <header className="cmp-run__head">
        <h2>{side.name}</h2>
        <p className="cmp-run__label">{side.replay.label}</p>
      </header>
      <dl className="cmp-run__stages">
        {side.replay.stages.map((s) => (
          <div key={s.stage} className="cmp-run__stage">
            <dt>{STAGE_LABEL[s.stage]}</dt>
            <dd>
              <ModelBadge model={s.model} provider={s.provider} />
            </dd>
          </div>
        ))}
      </dl>
      {side.run && a && o ? (
        <dl className="cmp-run__stats">
          <div>
            <dt>agent run</dt>
            <dd className="num">{side.run.id}</dd>
          </div>
          <div>
            <dt>steps · model turns</dt>
            <dd className="num">
              {a.steps} · {a.turns ?? "n/a"}
            </dd>
          </div>
          <div>
            <dt>tool calls · with a stated reason</dt>
            <dd className="num">
              {a.calls.length} · {a.withReason}
            </dd>
          </div>
          <div>
            <dt>calls rejected by a rule</dt>
            <dd className="num">{a.rejected.length}</dd>
          </div>
          <div>
            <dt>work orders: repair · monitor · reinspect</dt>
            <dd className="num">
              {o.repair} · {o.monitor} · {o.reinspect}
            </dd>
          </div>
        </dl>
      ) : (
        <p className="note">
          <InfoIcon className="note__icon" />
          <span>No agent run is stored for this replay.</span>
        </p>
      )}
      <p className="cmp-run__links">
        <button type="button" className="btn" onClick={onShow}>
          Browse this run
        </button>
        {side.run && <Link to={`/runs?provider=${side.replay.provider}`}>Open its trace</Link>}
      </p>
    </article>
  );
}

function Body({ sides }: { sides: Side[] }) {
  const { choose } = useRun();
  const [first, second] = sides;
  const split = first && second ? sharedStages(first.replay, second.replay) : null;
  const evidence = evidenceUrl(ow.file);
  // The evidence file's tables are always Meta rows, Open columns, whatever order the API lists.
  const META = "Muse Spark (Model API)";
  const OPEN = "Muse Spark Open (Baseten)";
  const VERDICTS = [
    ["ok", "Verified"],
    ["needs_review", "Needs review"],
    ["reinspect", "Reinspect"],
  ] as const;

  const ranks = new Map<string, number[]>();
  for (const side of sides) for (const t of side.fleet.turbines) ranks.set(t.id, [...(ranks.get(t.id) ?? []), t.rank]);
  const rankRows = [...ranks.entries()].sort((x, y) => x[1][0] - y[1][0]);

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Compare runs</p>
        <h1>Two models on the same detections</h1>
        <p className="lede">
          The farm was graded, verified and planned twice. These are counts of where the two models agree, not accuracy:
          neither run is a reference label, and n is small ({ow.defects} defects, {ow.turbines} turbines, one run each).
        </p>
      </header>

      {split && split.same.length > 0 && (
        <p className="note" data-testid="shared-stages">
          <InfoIcon className="note__icon" />
          <span>
            <strong>Same detections in both runs.</strong>{" "}
            {capitalize(split.same.map((s) => `${STAGE_LABEL[s.stage]} by ${modelLabel(s.model, s.provider)}`).join(" and "))}{" "}
            ran once
            and both runs reuse the stored result
            {split.same.some((s) => s.stage === "segmentation") ? " (SAM 3.1 has no open-weights path)" : ""}. Only{" "}
            {split.changed.map((s) => STAGE_LABEL[s.stage]).join(", ")} changed model.
          </span>
        </p>
      )}

      <div className="cmp-runs">
        {sides.map((side) => (
          <RunCard key={side.replay.provider} side={side} onShow={() => choose(side.replay.provider)} />
        ))}
      </div>

      <h2 className="section-title">Agreement between the two runs</h2>
      <div className="headlines" data-testid="agreement">
        <div className="headline">
          <p className="headline__label">Same severity</p>
          <p className="headline__value num">
            {ow.sameSeverity}
            <span className="headline__of"> of {ow.defects}</span>
          </p>
          <p className="headline__caption">
            {ow.sameSeverityPct}% exactly; {ow.withinOne} ({ow.withinOnePct}%) within one level.
          </p>
        </div>
        <div className="headline">
          <p className="headline__label">Same verdict</p>
          <p className="headline__value num">
            {ow.sameVerdict}
            <span className="headline__of"> of {ow.defects}</span>
          </p>
          <p className="headline__caption">{ow.sameVerdictPct}% of defects got the same verification verdict.</p>
        </div>
        <div className="headline">
          <p className="headline__label">Farm ranking</p>
          <p className="headline__value num">{ow.spearman}</p>
          <p className="headline__caption">
            Spearman rank correlation over {ow.turbines} turbines; {ow.topSixInBoth} of the top 6 are in both.
          </p>
        </div>
      </div>

      <div className="two">
        <div className="table-wrap">
          <table className="metric-table" data-testid="verdict-matrix">
            <caption>Verdicts: rows {META}, columns {OPEN}</caption>
            <thead>
              <tr>
                <th scope="col">
                  <span className="visually-hidden">{META} verdict</span>
                </th>
                {VERDICTS.map(([, label]) => (
                  <th key={label} scope="col" className="r">
                    {label}
                  </th>
                ))}
                <th scope="col" className="r">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {VERDICTS.map(([key, label], i) => (
                <tr key={key}>
                  <th scope="row">{label}</th>
                  {ow.verdictMatrix[i].map((n, j) => (
                    <td key={j} className={`r num${i === j ? " is-diag" : ""}`}>
                      {n}
                    </td>
                  ))}
                  <td className="r num">{ow.verdicts.meta[key]}</td>
                </tr>
              ))}
              <tr>
                <th scope="row">Total</th>
                {VERDICTS.map(([key]) => (
                  <td key={key} className="r num">
                    {ow.verdicts.baseten[key]}
                  </td>
                ))}
                <td className="r num">{ow.defects}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="table-wrap">
          <table className="metric-table metric-table--wrap" data-testid="order-overlap">
            <caption>Work orders, each agent's own run</caption>
            <thead>
              <tr>
                <th scope="col">
                  <span className="visually-hidden">Measure</span>
                </th>
                <th scope="col" className="r">
                  {META}
                </th>
                <th scope="col" className="r">
                  {OPEN}
                </th>
                <th scope="col" className="r">
                  In both
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Orders written</th>
                <td className="r num">{ow.orders.meta}</td>
                <td className="r num">{ow.orders.baseten}</td>
                <td className="r">n/a</td>
              </tr>
              <tr>
                <th scope="row">Defects in a repair order</th>
                <td className="r num">{ow.repairDefects.meta}</td>
                <td className="r num">{ow.repairDefects.baseten}</td>
                <td className="r num">
                  {ow.repairDefects.both} of {ow.repairDefects.union}
                </td>
              </tr>
              <tr>
                <th scope="row">Defects sent to re-inspection</th>
                <td className="r num">{ow.reinspectDefects.meta}</td>
                <td className="r num">{ow.reinspectDefects.baseten}</td>
                <td className="r num">
                  {ow.reinspectDefects.both} of {ow.reinspectDefects.union}
                </td>
              </tr>
            </tbody>
          </table>
          <p className="table-foot">
            Each agent planned from its own verdicts, so compare behaviour, not order lists.
          </p>
        </div>
      </div>

      {sides.length === 2 && (
        <div className="table-wrap cmp-ranks">
          <table className="metric-table metric-table--wrap" data-testid="rank-table">
            <caption>Rank of each turbine (deterministic score of verified defects), from the API</caption>
            <thead>
              <tr>
                <th scope="col">Turbine</th>
                {sides.map((s) => (
                  <th key={s.replay.provider} scope="col" className="r">
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rankRows.map(([id, r]) => (
                <tr key={id}>
                  <th scope="row">{id}</th>
                  {r.map((rank, i) => (
                    <td key={i} className="r num">
                      {rank}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="evidence-line">
        Agreement counts:{" "}
        <a href={evidence} target="_blank" rel="noreferrer">
          {ow.file}
        </a>
        . Run cards and ranks are read from the stored runs through the API.
      </p>
    </>
  );
}

export default function CompareScreen() {
  const { replays } = useRun();
  const key = replays.map((r) => r.provider).join(",");
  const state = useAsyncData(() => (replays.length < 2 ? Promise.resolve([] as Side[]) : load(replays)), [key]);
  if (replays.length < 2) {
    return (
      <section className="screen" aria-label="Compare runs">
        <p className="note">
          <InfoIcon className="note__icon" />
          <span>Only one stored run is available, so there is nothing to compare.</span>
        </p>
      </section>
    );
  }
  return (
    <section className="screen" aria-label="Compare runs">
      <Async state={state} what="both runs">
        {(sides) => <Body sides={sides} />}
      </Async>
    </section>
  );
}
