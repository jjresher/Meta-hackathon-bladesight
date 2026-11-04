import { useState } from "react";

import { api } from "../api/client";
import { Async } from "../components/PageState";
import RangeBar from "../components/RangeBar";
import SweepChart from "../components/SweepChart";
import { InfoIcon } from "../components/icons";
import { useAsyncData } from "../hooks/useAsyncData";
import { SEVERITY_AGREEMENT, evidenceUrl } from "../evidence";
import { pct, usd } from "../lib/format";
import type { ClassMetrics, EvalReport, Interval } from "../types";

const SPLIT_LABEL = { dev: "Dev split", heldout: "Held-out split" } as const;

function ci(interval: Interval | null): string {
  return interval ? `${pct(interval.low)}–${pct(interval.high)}` : "no interval";
}

function Headline({
  label,
  value,
  interval,
  caption,
}: {
  label: string;
  value: number;
  interval: Interval | null;
  caption: string;
}) {
  return (
    <div className="headline">
      <p className="headline__label">{label}</p>
      <p className="headline__value num">{pct(value, 1)}</p>
      <RangeBar value={value} interval={interval} />
      <p className="headline__ci num">95% interval {ci(interval)}</p>
      <p className="headline__caption">{caption}</p>
    </div>
  );
}

function ClassTable({ title, classes }: { title: string; classes: ClassMetrics[] }) {
  if (classes.length === 0) return null;
  return (
    <div className="table-wrap">
      <table className="metric-table">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">Class</th>
            <th scope="col" className="r">TP</th>
            <th scope="col" className="r">FP</th>
            <th scope="col" className="r">FN</th>
            <th scope="col" className="r">Precision</th>
            <th scope="col" className="r">Recall</th>
            <th scope="col" className="r">F1</th>
          </tr>
        </thead>
        <tbody>
          {classes.map((c) => (
            <tr key={c.label}>
              <th scope="row">{c.label}</th>
              <td className="r num">{Math.round(c.tp)}</td>
              <td className="r num">{Math.round(c.fp)}</td>
              <td className="r num">{Math.round(c.fn)}</td>
              <td className="r num">
                {pct(c.precision, 1)}
                <span className="metric-table__ci">{ci(c.precision_ci)}</span>
              </td>
              <td className="r num">
                {pct(c.recall, 1)}
                <span className="metric-table__ci">{ci(c.recall_ci)}</span>
              </td>
              <td className="r num">{c.f1.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Detection({ report }: { report: EvalReport }) {
  const damage = report.classes.find((c) => c.label === "damage");
  const dirt = report.classes.find((c) => c.label === "dirt");
  return (
    <>
      <div className="headlines">
        {damage && (
          <>
            <Headline
              label="Damage recall"
              value={damage.recall}
              interval={damage.recall_ci}
              caption={`Share of annotated damage boxes matched at IoU ≥ ${report.iou_threshold}.`}
            />
            <Headline
              label="Damage precision"
              value={damage.precision}
              interval={damage.precision_ci}
              caption="Share of predicted damage boxes that match an annotation."
            />
          </>
        )}
        <div className="headline">
          <p className="headline__label">Image-level recall</p>
          <p className="headline__value num">{pct(report.image_recall, 1)}</p>
          <RangeBar value={report.image_recall} interval={null} />
          <p className="headline__ci num">no interval reported</p>
          <p className="headline__caption">Damaged photos with at least one damage prediction, wherever it is.</p>
        </div>
      </div>

      <p className="note note--warn">
        <InfoIcon className="note__icon" />
        <span>
          {damage && damage.recall < 0.5 && (
            <>
              Read these as <strong>weak</strong>:{" "}
            </>
          )}
          {damage && `${pct(1 - damage.recall)} of annotated damage is missed at IoU ≥ ${report.iou_threshold}`}
          {dirt && `, and the dirt class has ${pct(dirt.precision, 1)} precision`}. Intervals are bootstrap over tiles; tiles
          of one photo are correlated, so they are probably a little too narrow.
          {report.sample_note ? ` ${report.sample_note}` : " The sample over-represents damaged tiles, so precision is optimistic for a real inspection."}
        </span>
      </p>

      <div className="two">
        <ClassTable title={`Box matching, IoU ≥ ${report.iou_threshold} (primary)`} classes={report.classes} />
        <ClassTable title="Box matching, IoU ≥ 0.5 (stricter)" classes={report.classes_iou50} />
      </div>

      {report.sweep.length > 0 && (
        <div className="panel sweep-panel">
          <h3 className="panel__title">Damage by score threshold</h3>
          <div className="sweep-panel__body">
            <SweepChart points={report.sweep} />
            <table className="metric-table metric-table--sweep">
              <caption className="visually-hidden">Threshold sweep, damage class</caption>
              <thead>
                <tr>
                  <th scope="col">Score ≥</th>
                  <th scope="col" className="r">Recall</th>
                  <th scope="col" className="r">Precision</th>
                  <th scope="col" className="r">False alarms / image</th>
                </tr>
              </thead>
              <tbody>
                {report.sweep.map((p) => (
                  <tr key={p.threshold}>
                    <th scope="row" className="num">{p.threshold}</th>
                    <td className="r num">{pct(p.recall, 1)}</td>
                    <td className="r num">{pct(p.precision, 1)}</td>
                    <td className="r num">{p.false_alarms_per_image.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="provenance">
        {report.n_images} tiles · cost {usd(report.cost_usd)} · prompts{" "}
        <span className="num">{Object.values(report.prompt_versions).join(", ") || "n/a"}</span> · evidence{" "}
        <a href={evidenceUrl(report.evidence_path)} target="_blank" rel="noreferrer">
          {report.evidence_path}
        </a>
      </p>
    </>
  );
}

function SeverityAgreement() {
  const s = SEVERITY_AGREEMENT;
  return (
    <section className="panel kappa" aria-labelledby="kappa-title" data-testid="kappa">
      <h3 id="kappa-title" className="panel__title">Severity vs a human grader</h3>
      <div className="kappa__grid">
        <div className="kappa__num">
          <p className="headline__label">Quadratic weighted kappa</p>
          <p className="headline__value num" data-testid="kappa-value">{s.kappa.toFixed(2)}</p>
          <p className="headline__ci num">
            95% interval {s.kappaLow.toFixed(2)} to {s.kappaHigh.toFixed(2)} · n = {s.crops}
          </p>
          <p className="kappa__scale">
            0 is chance. 1 is perfect agreement. This is <strong>barely above chance</strong>.
          </p>
        </div>
        <div className="kappa__text">
          <p>
            One person with no wind-energy experience graded {s.crops} defect crops with our own rubric, blind to the
            model. Muse Spark graded the same crops. It agreed exactly on {s.exactAgreementPct}% and within one level on{" "}
            {s.withinOnePct}%; it gave severity 1 to {s.modelGradedOne} of {s.crops} crops where the human did so for{" "}
            {s.humanGradedOne}, and grades {Math.abs(s.meanModelMinusHuman)} levels lower on average.
          </p>
          <p>
            So <strong>severity is advisory</strong>. The product does not rely on it alone: a second look and rule
            checks can downgrade any verdict to <em>needs review</em> or <em>reinspect</em>, and no work order is written
            for an unverified defect. That is a safety net, not a validation of the grade.
          </p>
          <p className="kappa__limits">
            One non-specialist rater, no second rater, {s.crops} crops chosen by size. This is agreement with the rubric
            as a non-specialist applies it, not severity validated by a wind-turbine specialist.{" "}
            <a href={evidenceUrl(s.file)} target="_blank" rel="noreferrer">
              {s.file}
            </a>
          </p>
        </div>
      </div>
    </section>
  );
}

function EvalBody({ reports }: { reports: EvalReport[] }) {
  const heldout = reports.find((r) => r.split === "heldout");
  const dev = reports.find((r) => r.split === "dev");
  const [split, setSplit] = useState<"dev" | "heldout">(heldout ? "heldout" : "dev");
  const report = split === "heldout" ? heldout : dev;

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Evaluation</p>
        <h1>What the system gets right, and what it does not</h1>
        <p className="lede">
          Detection is scored against the dataset's own annotations. Severity is scored against one human grader. Both are
          reported as measured, with intervals.
        </p>
      </header>

      <div className="seg seg--tabs" role="tablist" aria-label="Evaluation split">
        {(["heldout", "dev"] as const).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={split === key}
            className={`seg__item${split === key ? " is-active" : ""}`}
            onClick={() => setSplit(key)}
            data-testid={`tab-${key}`}
          >
            {SPLIT_LABEL[key]}
            {key === "heldout" && !heldout ? " · pending" : ""}
          </button>
        ))}
      </div>

      {split === "heldout" && !heldout && (
        <p className="note" data-testid="heldout-pending">
          <InfoIcon className="note__icon" />
          <span>
            The held-out run is a single, pre-registered evaluation on photos nobody tuned on. Its result is not published
            here yet; when it is, it appears in this tab exactly as measured. The dev numbers were used to tune thresholds
            and prompts, so they are optimistic by construction.
          </span>
        </p>
      )}
      {split === "dev" && heldout && (
        <p className="note">
          <InfoIcon className="note__icon" />
          <span>The dev split was used to tune thresholds and prompts. Quote the held-out numbers, not these.</span>
        </p>
      )}

      {report && <Detection report={report} />}
      <SeverityAgreement />
    </>
  );
}

export default function EvalScreen() {
  const state = useAsyncData(() => api.evaluations(), []);
  return (
    <section className="screen" aria-label="Evaluation">
      <Async state={state} what="the evaluation">
        {(reports) => <EvalBody reports={reports} />}
      </Async>
    </section>
  );
}
