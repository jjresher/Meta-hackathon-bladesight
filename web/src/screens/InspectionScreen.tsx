import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, NotFoundError } from "../api/client";
import StatusChip from "../components/StatusChip";
import type { Inspection } from "../types";

/**
 * Inspection viewer: a first pass listing the inspection's defect cards.
 * The drone-image overlay with toggleable masks and boxes arrives in FEAT-002.
 */
export default function InspectionScreen() {
  const { id = "" } = useParams();
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setInspection(null);
    setError(null);
    api
      .getInspection(id)
      .then((data) => {
        if (active) setInspection(data);
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof NotFoundError ? err.message : "Failed to load inspection");
        }
      });
    return () => {
      active = false;
    };
  }, [id]);

  if (error) {
    return (
      <section className="screen">
        <p role="alert">{error}</p>
        <Link to="/">Back to fleet</Link>
      </section>
    );
  }

  if (!inspection) {
    return (
      <section className="screen">
        <p>Loading inspection…</p>
      </section>
    );
  }

  return (
    <section className="screen" aria-labelledby="inspection-heading">
      <header className="screen__header">
        <h1 id="inspection-heading">
          {inspection.turbineId} · {inspection.year}
        </h1>
        <p className="screen__sub">{inspection.provenance}</p>
      </header>

      <div className="defect-list" data-testid="defect-list">
        {inspection.defects.length === 0 ? (
          <p>No defects detected in this inspection.</p>
        ) : (
          inspection.defects.map((d) => (
            <article key={d.id} className="defect-card" data-testid="defect-card">
              <div className="defect-card__head">
                <h2>{d.concept}</h2>
                <StatusChip status={d.verification.verdict} />
              </div>
              <dl className="defect-card__meta">
                <div>
                  <dt>Severity</dt>
                  <dd>{d.assessment.severity} / 5</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{Math.round(d.assessment.confidence * 100)}%</dd>
                </div>
                <div>
                  <dt>Region</dt>
                  <dd>{d.measurement.region}</dd>
                </div>
              </dl>
              <p className="defect-card__rationale">{d.assessment.rationale}</p>
              {d.verification.reasons.length > 0 && (
                <ul className="defect-card__reasons">
                  {d.verification.reasons.map((reason, i) => (
                    <li key={i}>{reason}</li>
                  ))}
                </ul>
              )}
            </article>
          ))
        )}
      </div>

      <Link to="/">Back to fleet</Link>
    </section>
  );
}
