import { Link } from "react-router-dom";

import { DEFECT_TYPE_LABEL, conceptLabel, pct, shortDefectId } from "../lib/format";
import { PROVIDER_LABEL } from "../lib/models";
import type { InspectedDefect } from "../types";
import { ModelBadge, UnverifiedChip, VerdictChip } from "./Chips";
import SeverityScale from "./SeverityScale";
import { ToneGlyph } from "./icons";

const VERDICT_NAME = { ok: "verified", needs_review: "needs review", reinspect: "reinspect" } as const;

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
  /** Its overlay is under the pointer (or this card has focus): both light up together. */
  hovered?: boolean;
  onHover?: (on: boolean, fromFocus?: boolean) => void;
  /** Work orders that cite this defect. */
  workOrders?: string[];
}

/**
 * One defect: detection, measurement, Muse Spark's assessment and the verification verdict with
 * its reasons. Collapsed it shows severity, verdict and why in three short lines; selected it
 * opens everything the agent knows.
 */
export default function DefectCard({ item, selected, onSelect, hovered, onHover, workOrders = [] }: DefectCardProps) {
  const { defect, measurement, assessment, verification, error } = item;
  const verdict = verification?.verdict;
  const title = assessment ? DEFECT_TYPE_LABEL[assessment.defect_type] : defect.concept;
  const id = shortDefectId(defect.id);
  // Why a defect is flagged comes first: it is what a person has to act on.
  const flag = verdict && verdict !== "ok" ? verification?.reasons[0] : undefined;
  const why = assessment?.rationale ?? error ?? undefined;
  const whyId = `dcard-why-${defect.id}`;

  return (
    <article
      className={`dcard${selected ? " is-selected" : ""}${hovered ? " is-hover" : ""} dcard--${verdict ?? "unverified"}`}
      data-testid="defect-card"
      data-defect-id={defect.id}
      data-selected={selected}
      onMouseEnter={() => onHover?.(true)}
      onMouseLeave={() => onHover?.(false)}
      onFocus={() => onHover?.(true, true)}
      onBlur={() => onHover?.(false, true)}
    >
      {/* The whole summary is a click target for the pointer; the button is the keyboard and
          screen-reader control, with a short name and the "why" as its description. */}
      <div className="dcard__summary" onClick={onSelect}>
        <button
          type="button"
          className="dcard__head"
          aria-expanded={selected}
          aria-controls={selected ? `dcard-${defect.id}` : undefined}
          aria-label={`${id} ${title}, ${verdict ? VERDICT_NAME[verdict] : "unverified"}, ${
            assessment ? `severity ${assessment.severity} of 5` : "not graded"
          }`}
          aria-describedby={!selected && (flag || why) ? whyId : undefined}
        >
          <span className="dcard__id">{id}</span>
          <span className="dcard__title">{title}</span>
          {verdict ? <VerdictChip verdict={verdict} small /> : <UnverifiedChip small />}
        </button>
        <span className="dcard__line dcard__line--meta">
          <SeverityScale value={assessment?.severity} />
          {assessment && <ModelBadge model={assessment.model} provider={assessment.provider} />}
        </span>
        {!selected && (flag || why) && (
          <p className="dcard__why" id={whyId}>
            {flag && <span className={`dcard__flag dcard__flag--${verdict}`}>{flag}</span>}
            {why && <span className={`dcard__gist${flag ? " is-short" : ""}`}>{why}</span>}
          </p>
        )}
      </div>

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
                  <span className="num">{assessment.model}</span> · {PROVIDER_LABEL[assessment.provider]}
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
                {verification.model && (
                  <Row label="Second look by">
                    <ModelBadge model={verification.model} provider={verification.provider} />
                  </Row>
                )}
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
                    <span className="num">{pct(measurement.tile_area_ratio, 2)}</span> of the tile ·{" "}
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

          {workOrders.length > 0 && (
            <p className="dcard__cites">
              Cited by
              {workOrders.map((order) => (
                <Link key={order} to={`/work-orders#${order}`} className="year-chip">
                  {order}
                </Link>
              ))}
            </p>
          )}
        </div>
      )}
    </article>
  );
}
