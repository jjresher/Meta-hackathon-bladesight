import { api } from "../api/client";
import ThresholdCurve from "../components/ThresholdCurve";
import { InfoIcon } from "../components/icons";
import { useAsyncData } from "../hooks/useAsyncData";

/** Human labels for the metric keys we expect in the mock/fixtures. */
const METRIC_LABELS: Record<string, string> = {
  precision: "Precision",
  recall: "Recall",
  f1: "F1",
  imageLevelRecall: "Image-level recall",
  needsReviewShare: "Needs-review share",
};

function labelFor(key: string): string {
  if (METRIC_LABELS[key]) return METRIC_LABELS[key];
  // Fall back to a readable form of an unknown camelCase key.
  return key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/^./, (c) => c.toUpperCase());
}

function formatMetric(value: number): string {
  // Values in 0..1 render as a percentage; anything else as-is.
  return value >= 0 && value <= 1 ? `${(value * 100).toFixed(0)}%` : String(value);
}

/**
 * Evaluation screen: headline metrics, the threshold curve drawn as inline SVG
 * and the honest limitations list. Labels stay honest: the mock numbers are
 * flagged as illustrative.
 */
export default function EvalScreen() {
  const state = useAsyncData(() => api.getEvalReport(), []);

  if (state.status === "loading") {
    return (
      <section className="screen">
        <p className="state">Loading evaluation…</p>
      </section>
    );
  }
  if (state.status === "error") {
    return (
      <section className="screen">
        <p className="state" role="alert">
          Could not load the evaluation: {state.error.message}
        </p>
      </section>
    );
  }

  const report = state.data;

  return (
    <section className="screen" aria-labelledby="eval-heading">
      <header className="screen__header">
        <p className="screen__eyebrow">Evaluation</p>
        <h1 id="eval-heading">Evaluation</h1>
        <p className="screen__sub">
          Split: <span className="num">{report.split}</span> · matched at IoU ≥{" "}
          <span className="num">{report.iou}</span>. Evidence: {report.evidenceRef}.
        </p>
      </header>

      <p className="note">
        <InfoIcon className="note__icon" />
        <span>
          These numbers are illustrative mock data, not a measured evaluation. See the limitations
          below for what they do and do not represent.
        </span>
      </p>

      <div className="eval-grid">
        <dl className="metric-grid" data-testid="metric-grid">
          {Object.entries(report.metrics).map(([name, value]) => (
            <div key={name} className="metric">
              <dt>{labelFor(name)}</dt>
              <dd>{formatMetric(value)}</dd>
            </div>
          ))}
        </dl>

        <div className="panel curve">
          <ThresholdCurve points={report.thresholdCurve} />
        </div>

        <div className="panel" style={{ padding: "16px" }}>
          <h2 style={{ margin: "0 0 10px", fontSize: "15px" }}>Limitations</h2>
          <ul className="limitations">
            {report.limitations.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
