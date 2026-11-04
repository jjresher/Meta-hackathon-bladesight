import { DEFECT_TYPE_LABEL, conceptLabel, pct, shortDefectId } from "../lib/format";
import type { InspectedDefect, Provider } from "../types";
import { VerdictChip } from "./Chips";
import SeverityScale from "./SeverityScale";
import { ToneGlyph } from "./icons";

const PROVIDER: Record<Provider, string> = {
  meta: "Meta Model API",
  baseten: "Baseten, open weights",
  stub: "stub (no real model)",
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="kv__row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

interface DefectCardProps {
  item: InspectedDefect;
  selected: boolean;
  onSelect: () => void;
}

/**
 * One defect: detection, measurement, Muse Spark's assessment and the verification verdict with
 * its reasons. Collapsed it is one line; selected it opens everything the agent knows.
 */
export default function DefectCard({ item, selected, onSelect }: DefectCardProps) {
  const { defect, measurement, assessment, verification, error } = item;
  const verdict = verification?.verdict;
  const title = assessment ? DEFECT_TYPE_LABEL[assessment.defect_type] : defect.concept;

  return (
    <article
      className={`dcard${selected ? " is-selected" : ""}${verdict ? ` dcard--${verdict}` : ""}`}
      data-testid="defect-card"
      data-defect-id={defect.id}
      data-selected={selected}
    >
      <button
        type="button"
        className="dcard__head"
        onClick={onSelect}
        aria-expanded={selected}
        aria-controls={selected ? `dcard-${defect.id}` : undefined}
      >
        <span className="dcard__id">{shortDefectId(defect.id)}</span>
        <span className="dcard__title">{title}</span>
        <SeverityScale value={assessment?.severity} />
        {verdict ? <VerdictChip verdict={verdict} small /> : <span className="chip chip--sm">Unverified</span>}
      </button>

      {selected && (
        <div className="dcard__body" id={`dcard-${defect.id}`}>
          {error && (
            <p className="dcard__error" role="alert">
              <ToneGlyph tone="alert" /> A stage is missing for this defect: {error}
            </p>
          )}

          {assessment && (
            <section className="dsec">
              <h4>Assessment</h4>
              <blockquote className="rationale">{assessment.rationale}</blockquote>
              <dl className="kv">
                <Row label="Confidence">
                  <span className="meter">
                    <span className="meter__track">
                      <span className="meter__fill" style={{ width: pct(assessment.confidence) }} />
                    </span>
                    <span className="num">{assessment.confidence.toFixed(2)}</span>
                  </span>
                </Row>
                <Row label="Graded by">
                  <span className="num">{assessment.model}</span> · {PROVIDER[assessment.provider]}
                </Row>
                <Row label="Rubric / prompt">
                  <span className="num">
                    {assessment.rubric_version} · {assessment.prompt_version}
                  </span>
                </Row>
              </dl>
            </section>
          )}

          {verification && (
            <section className="dsec">
              <h4>Verification</h4>
              <ul className="reasons">
                {verification.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <dl className="kv">
                <Row label="Agreement">
                  <span className="num">{verification.agreement.toFixed(2)}</span>
                  {verification.second_severity != null && (
                    <>
                      {" "}
                      · second look severity <span className="num">{verification.second_severity}</span>
                    </>
                  )}
                </Row>
              </dl>
              {verification.checks.length > 0 && (
                <ul className="checks" aria-label="Rule checks">
                  {verification.checks.map((check) => (
                    <li key={check.name} className={check.passed ? "is-pass" : "is-fail"}>
                      <ToneGlyph tone={check.passed ? "ok" : "alert"} size={11} />
                      <span className="checks__name">{check.name.replace(/_/g, " ")}</span>
                      <span className="checks__detail">{check.detail}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          <section className="dsec">
            <h4>Detection and measurement</h4>
            <dl className="kv">
              <Row label="SAM 3.1">
                {conceptLabel(defect)} · score <span className="num">{defect.score.toFixed(2)}</span>
              </Row>
              {measurement && (
                <>
                  <Row label="Size">
                    <span className="num">{pct(measurement.tile_area_ratio, 2)}</span> of the photo ·{" "}
                    <span className="num">
                      {Math.round(measurement.length_px)} × {Math.round(measurement.width_px)} px
                    </span>
                  </Row>
                  <Row label="Elongation">
                    <span className="num">{measurement.elongation.toFixed(2)}</span> (1 is a thin line)
                  </Row>
                  <Row label="Position">
                    {measurement.position === "unknown"
                      ? "not determined (no blade mask)"
                      : `${measurement.position}${
                          measurement.position_t != null ? ` (${pct(measurement.position_t)} root→tip)` : ""
                        }`}
                  </Row>
                  {measurement.blade_area_ratio != null && (
                    <Row label="Of the blade">
                      <span className="num">{pct(measurement.blade_area_ratio, 1)}</span>
                    </Row>
                  )}
                </>
              )}
            </dl>
            <p className="dsec__foot">Sizes are relative (pixels), never millimetres.</p>
          </section>
        </div>
      )}
    </article>
  );
}
