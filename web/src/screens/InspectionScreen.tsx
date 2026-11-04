import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, NotFoundError } from "../api/client";
import BladeImage from "../components/BladeImage";
import SeverityScale from "../components/SeverityScale";
import StatusChip from "../components/StatusChip";
import { ArrowLeftIcon, InfoIcon } from "../components/icons";
import { useAsyncData } from "../hooks/useAsyncData";
import type { Defect } from "../types";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** One toggle button for the overlay layers (masks / boxes), kept independent. */
function LayerToggle({
  label,
  variant,
  on,
  onChange,
}: {
  label: string;
  variant: "masks" | "boxes";
  on: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className={`toggle toggle--${variant}`} data-on={on}>
      <input
        type="checkbox"
        checked={on}
        onChange={(e) => onChange(e.target.checked)}
        data-testid={`toggle-${variant}`}
      />
      <span className="toggle__swatch" aria-hidden="true" />
      {label}
    </label>
  );
}

/**
 * Inspection viewer: a schematic inline-SVG drone image (no raster asset) with
 * independently toggleable defect masks and bounding boxes, alongside detailed
 * defect cards (measurement, assessment with a 1-5 severity scale, and the
 * verification verdict with its reasons).
 */
export default function InspectionScreen() {
  const { id = "" } = useParams();
  const state = useAsyncData(() => api.getInspection(id), [id]);

  const [showMasks, setShowMasks] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);

  if (state.status === "loading") {
    return (
      <section className="screen">
        <p className="state">Loading inspection…</p>
      </section>
    );
  }
  if (state.status === "error") {
    const message =
      state.error instanceof NotFoundError
        ? state.error.message
        : `Failed to load inspection: ${state.error.message}`;
    return (
      <section className="screen">
        <Link to="/" className="screen__back">
          <ArrowLeftIcon /> Back to fleet
        </Link>
        <p className="state" role="alert">
          {message}
        </p>
      </section>
    );
  }

  const inspection = state.data;
  const defects = inspection.defects;

  return (
    <section className="screen" aria-labelledby="inspection-heading">
      <Link to="/" className="screen__back">
        <ArrowLeftIcon /> Back to fleet
      </Link>

      <header className="screen__header">
        <p className="screen__eyebrow">Inspection viewer</p>
        <h1 id="inspection-heading">
          Turbine {inspection.turbineId} · {inspection.year}
        </h1>
        <p className="screen__sub">
          {defects.length === 0
            ? "No defects detected in this inspection."
            : `${defects.length} defect${defects.length === 1 ? "" : "s"} detected, with measurement, severity assessment and verification.`}
        </p>
      </header>

      <div className="inspect-layout">
        <div className="viewer">
          <div className="viewer__frame">
            <BladeImage
              inspection={inspection}
              defects={defects}
              showMasks={showMasks}
              showBoxes={showBoxes}
              activeId={activeId}
              onHover={setActiveId}
            />
            <div className="viewer__toolbar">
              <LayerToggle
                label="Masks"
                variant="masks"
                on={showMasks}
                onChange={setShowMasks}
              />
              <LayerToggle
                label="Boxes"
                variant="boxes"
                on={showBoxes}
                onChange={setShowBoxes}
              />
              <span className="viewer__legend">
                {defects.length} overlay{defects.length === 1 ? "" : "s"}
              </span>
            </div>
          </div>
          <p className="viewer__caption">
            Schematic placeholder, not the raw photo. Overlays use the defect masks and boxes;
            root/mid/tip guides mark the blade axis. Source: {inspection.provenance}.
          </p>
        </div>

        <div className="defect-list" data-testid="defect-list">
          {defects.length === 0 ? (
            <p className="note">
              <InfoIcon className="note__icon" />
              <span>This inspection is clean: no defects were segmented or assessed.</span>
            </p>
          ) : (
            defects.map((d) => (
              <DefectCard
                key={d.id}
                defect={d}
                active={d.id === activeId}
                onHover={setActiveId}
              />
            ))
          )}
        </div>
      </div>
    </section>
  );
}

/** A single defect card: measurement, assessment and verification. */
function DefectCard({
  defect: d,
  active,
  onHover,
}: {
  defect: Defect;
  active: boolean;
  onHover: (id: string | null) => void;
}) {
  const verdict = d.verification.verdict;
  return (
    <article
      className={`defect-card defect-card--${verdict}${active ? " is-active" : ""}`}
      data-testid="defect-card"
      onMouseEnter={() => onHover(d.id)}
      onMouseLeave={() => onHover(null)}
    >
      <div className="defect-card__head">
        <div>
          <h3>{d.assessment.type}</h3>
          <span className="defect-card__id">{d.id}</span>
        </div>
        <StatusChip status={verdict} small />
      </div>

      {/* Measurement */}
      <div className="defect-section">
        <p className="defect-section__label">Measurement</p>
        <dl className="kv">
          <div>
            <dt>Region</dt>
            <dd style={{ textTransform: "capitalize" }}>{d.measurement.region}</dd>
          </div>
          <div>
            <dt>Axial position</dt>
            <dd>{pct(d.measurement.axialPosition)}</dd>
          </div>
          <div>
            <dt>Area ratio</dt>
            <dd>{(d.measurement.areaRatio * 100).toFixed(1)}%</dd>
          </div>
          <div>
            <dt>Elongation</dt>
            <dd>{d.measurement.elongation.toFixed(1)}×</dd>
          </div>
        </dl>
      </div>

      {/* Assessment */}
      <div className="defect-section">
        <p className="defect-section__label">Assessment</p>
        <dl className="kv">
          <div>
            <dt>Severity</dt>
            <dd>
              <SeverityScale value={d.assessment.severity} />
            </dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>
              <span className="meter">
                <span className="meter__track">
                  <span
                    className="meter__fill"
                    style={{ width: pct(d.assessment.confidence) }}
                  />
                </span>
                {pct(d.assessment.confidence)}
              </span>
            </dd>
          </div>
        </dl>
        <p className="defect-card__rationale">{d.assessment.rationale}</p>
      </div>

      {/* Verification */}
      <div className="defect-section">
        <p className="defect-section__label">Verification</p>
        <p style={{ margin: 0 }}>
          Verdict: <StatusChip status={verdict} small />
        </p>
        {d.verification.reasons.length > 0 ? (
          <ul className="reasons">
            {d.verification.reasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        ) : (
          <p className="reasons" style={{ listStyle: "none", paddingLeft: 0 }}>
            Both looks agreed; no concerns raised.
          </p>
        )}
      </div>
    </article>
  );
}
