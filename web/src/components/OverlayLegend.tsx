import { GLYPH, VERDICT_TEXT, type OverlayVerdict } from "./PhotoViewer";

const MEANING: Record<OverlayVerdict, string> = {
  ok: "two looks agreed, confidence was high enough and the rule checks passed",
  needs_review: "a person should look at it",
  reinspect: "take new photos before deciding",
  unverified: "not checked: the verification step did not run",
};

const ORDER: OverlayVerdict[] = ["ok", "needs_review", "reinspect", "unverified"];

/**
 * Key for the overlay: each verdict's glyph drawn exactly as on the photo tags, its name and what
 * it means. Text carries the meaning, so the key works without colour and for screen readers.
 */
export default function OverlayLegend() {
  return (
    <section className="legend" aria-labelledby="legend-title" data-testid="overlay-legend">
      <h2 id="legend-title" className="visually-hidden">
        Overlay key
      </h2>
      <ul className="legend__items">
        {ORDER.map((verdict) => (
          <li key={verdict} className="legend__item" data-testid={`legend-${verdict}`}>
            <span className={`legend__glyph photo__tag--${verdict}`} aria-hidden="true">
              {GLYPH[verdict]}
            </span>
            <span>
              <strong>{VERDICT_TEXT[verdict]}</strong>
              <span className="legend__meaning">: {MEANING[verdict]}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="legend__hint">
        SAM 3.1 masks (filled) and boxes (dashed), coloured by verdict. <strong>Verified</strong> is not proof the defect
        is on the blade. <kbd>←</kbd> <kbd>→</kbd> change tile, <kbd>Esc</kbd> clears the selection.
      </p>
    </section>
  );
}
