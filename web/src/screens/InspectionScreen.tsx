import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, imageUrl } from "../api/client";
import { TrendBadge, VerdictChip } from "../components/Chips";
import DefectCard from "../components/DefectCard";
import PhotoViewer, { type Layers } from "../components/PhotoViewer";
import { Async } from "../components/PageState";
import SeverityScale from "../components/SeverityScale";
import { ArrowLeftIcon, InfoIcon } from "../components/icons";
import { SEVERITY_AGREEMENT } from "../evidence";
import { useAsyncData } from "../hooks/useAsyncData";
import { defectsLabel, worseVerdict } from "../lib/format";
import type { Fleet, Inspection, InspectionImage, Verdict, WorkOrder } from "../types";

function worstVerdict(image: InspectionImage): Verdict | null {
  let worst: Verdict | null = null;
  for (const { verification } of image.defects) {
    if (verification) worst = worst ? worseVerdict(worst, verification.verdict) : verification.verdict;
  }
  return worst;
}

function LayerToggle({
  label,
  name,
  on,
  onChange,
  disabled,
  hint,
}: {
  label: string;
  name: keyof Layers;
  on: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <label className={`toggle toggle--${name}${disabled ? " is-disabled" : ""}`} data-on={on && !disabled} title={hint}>
      <input
        type="checkbox"
        checked={on && !disabled}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        data-testid={`toggle-${name}`}
      />
      <span className="toggle__swatch" aria-hidden="true" />
      {label}
    </label>
  );
}

function Thumb({ image, active, onClick }: { image: InspectionImage; active: boolean; onClick: () => void }) {
  const [failed, setFailed] = useState(false);
  const worst = worstVerdict(image);
  return (
    <button
      type="button"
      className={`thumb${active ? " is-active" : ""}`}
      onClick={onClick}
      aria-pressed={active}
      aria-label={`Tile ${image.tile_id}, ${defectsLabel(image.defects.length)}`}
      data-testid="thumb"
    >
      <span className="thumb__frame" style={{ aspectRatio: `${image.width} / ${image.height}` }}>
        {failed ? (
          <span className="thumb__missing">no photo</span>
        ) : (
          <img src={imageUrl(image.image_url)} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />
        )}
        <span className={`thumb__count${worst ? ` thumb__count--${worst}` : ""}`}>{image.defects.length}</span>
      </span>
      <span className="thumb__id">{image.tile_id.replace("DJI_", "")}</span>
    </button>
  );
}

function InspectionBody({ inspection, fleet, orders }: { inspection: Inspection; fleet: Fleet | null; orders: WorkOrder[] }) {
  const [params, setParams] = useSearchParams();
  const { summary, images } = inspection;
  const [layers, setLayers] = useState<Layers>({ masks: true, boxes: true, blade: true });

  const imageParam = params.get("image");
  const image = images.find((i) => i.id === imageParam) ?? images.find((i) => i.defects.length > 0) ?? images[0];
  const defectParam = params.get("defect");
  const selectedId =
    image?.defects.find((d) => d.defect.id === defectParam)?.defect.id ?? (defectParam === "" ? null : (image?.defects[0]?.defect.id ?? null));

  const turbine = fleet?.turbines.find((t) => t.id === summary.turbine_id);
  const inspectionOrders = orders.filter((o) => o.inspection_id === summary.id);
  const hasBlade = (image?.blade_outline.length ?? 0) > 0;

  const setSelection = (imageId: string, defectId: string | null) => {
    const next = new URLSearchParams(params);
    next.set("image", imageId);
    next.set("defect", defectId ?? "");
    setParams(next, { replace: true });
  };

  // Left/right arrows move between the tiles of the inspection.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (event.key === "Escape" && image) setSelection(image.id, null);
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const at = images.findIndex((i) => i.id === image?.id);
      const next = images[at + (event.key === "ArrowRight" ? 1 : -1)];
      if (next) setSelection(next.id, next.defects[0]?.defect.id ?? null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const selectedDefect = useMemo(
    () => image?.defects.find((d) => d.defect.id === selectedId),
    [image, selectedId],
  );
  // When a defect is picked on the photo, bring its card into view inside the side panel. Only
  // where the panel scrolls on its own (wide layout): on a phone the page would jump past the photo.
  const sideRef = useRef<HTMLElement>(null);
  const firstSelection = useRef(true);
  useEffect(() => {
    if (firstSelection.current) {
      firstSelection.current = false;
      return;
    }
    const side = sideRef.current;
    if (!selectedId || !side || getComputedStyle(side).overflowY !== "auto") return;
    const card = side.querySelector<HTMLElement>(`[data-defect-id="${CSS.escape(selectedId)}"]`);
    if (card) side.scrollTo({ top: card.offsetTop - side.offsetTop - 8, behavior: "smooth" });
  }, [selectedId]);

  if (!image) {
    return (
      <p className="note">
        <InfoIcon className="note__icon" />
        <span>This inspection has no images.</span>
      </p>
    );
  }

  return (
    <>
      <header className="insp-head">
        <div>
          <Link to="/" className="back">
            <ArrowLeftIcon /> Fleet
          </Link>
          <h1>
            {turbine?.name ?? `Turbine ${summary.turbine_id}`} <span className="insp-head__year">{summary.year}</span>
          </h1>
          <p className="insp-head__meta">
            {turbine && <span>Rank {turbine.rank} of {fleet?.turbines.length}</span>}
            {turbine && <TrendBadge trend={turbine.trend} />}
            <span>
              {summary.n_images} photos · {defectsLabel(summary.n_defects)}
            </span>
            <span>
              {summary.n_needs_review} to review · {summary.n_reinspect} to reinspect
            </span>
            <span className="insp-head__sev">
              max severity <SeverityScale value={summary.max_severity} />
            </span>
            {inspectionOrders.length > 0 && (
              <span className="insp-head__orders">
                Work orders
                {inspectionOrders.map((order) => (
                  <Link key={order.id} to={`/work-orders#${order.id}`} className="year-chip" data-testid="wo-link">
                    {order.id}
                  </Link>
                ))}
              </span>
            )}
          </p>
        </div>
        {turbine && turbine.inspections.length > 1 && (
          <nav className="seg" aria-label="Inspection year">
            {[...turbine.inspections]
              .sort((a, b) => a.year - b.year)
              .map((insp) => (
                <Link
                  key={insp.id}
                  to={`/inspections/${encodeURIComponent(insp.id)}`}
                  className={`seg__item${insp.id === summary.id ? " is-active" : ""}`}
                  aria-current={insp.id === summary.id ? "page" : undefined}
                >
                  {insp.year}
                </Link>
              ))}
          </nav>
        )}
      </header>

      <div className="insp-grid">
        <div className="insp-main">
          <div className="stage">
            <PhotoViewer
              key={image.id}
              image={image}
              layers={layers}
              selectedId={selectedId}
              onSelect={(defectId) => setSelection(image.id, defectId)}
            />
            <div className="stage__bar">
              <div className="stage__layers" role="group" aria-label="Overlay layers">
                <LayerToggle label="Masks" name="masks" on={layers.masks} onChange={(v) => setLayers({ ...layers, masks: v })} />
                <LayerToggle label="Boxes" name="boxes" on={layers.boxes} onChange={(v) => setLayers({ ...layers, boxes: v })} />
                <LayerToggle
                  label="Blade"
                  name="blade"
                  on={layers.blade}
                  disabled={!hasBlade}
                  hint={hasBlade ? undefined : "No blade outline was segmented on this photo"}
                  onChange={(v) => setLayers({ ...layers, blade: v })}
                />
              </div>
              <p className="stage__meta num">
                {image.tile_id} · {image.width}×{image.height}px
              </p>
            </div>
          </div>

          <div className="legend" aria-label="Overlay colours">
            <span className="legend__item legend__item--ok">✓ Verified</span>
            <span className="legend__item legend__item--needs_review">◆ Needs review</span>
            <span className="legend__item legend__item--reinspect">▲ Reinspect</span>
            <span className="legend__hint">
              SAM 3.1 masks and boxes, coloured by verdict. <strong>Verified</strong> means two looks agreed and the rule checks
              passed, not that the defect is confirmed on the blade. ← → switch photo.
            </span>
          </div>

          <ul className="filmstrip" aria-label="Photos in this inspection">
            {images.map((i) => (
              <li key={i.id}>
                <Thumb image={i} active={i.id === image.id} onClick={() => setSelection(i.id, i.defects[0]?.defect.id ?? null)} />
              </li>
            ))}
          </ul>
        </div>

        <aside className="insp-side" ref={sideRef} aria-label="Defects on this photo">
          <h2 className="side-title">
            {image.defects.length === 0 ? "No defects on this photo" : `${defectsLabel(image.defects.length)} on this photo`}
          </h2>
          {image.defects.length === 0 && (
            <p className="note">
              <InfoIcon className="note__icon" />
              <span>SAM 3.1 found nothing on this tile. That is not proof the blade is clean here.</span>
            </p>
          )}
          <div className="defect-list" data-testid="defect-list">
            {image.defects.map((item) => (
              <DefectCard
                key={item.defect.id}
                item={item}
                selected={item.defect.id === selectedDefect?.defect.id}
                onSelect={() =>
                  setSelection(image.id, item.defect.id === selectedDefect?.defect.id ? null : item.defect.id)
                }
              />
            ))}
          </div>
          {selectedDefect && orders.some((o) => o.defect_ids.includes(selectedDefect.defect.id)) && (
            <p className="side-foot side-foot--cites">
              Cited by{" "}
              {orders
                .filter((o) => o.defect_ids.includes(selectedDefect.defect.id))
                .map((o) => (
                  <Link key={o.id} to={`/work-orders#${o.id}`} className="year-chip">
                    {o.id}
                  </Link>
                ))}
            </p>
          )}
          {selectedDefect?.verification && (
            <p className="side-foot">
              <VerdictChip verdict={selectedDefect.verification.verdict} small /> Severity is advisory: agreement with a
              human grader is low (kappa {SEVERITY_AGREEMENT.kappa}).{" "}
              <Link to="/eval">See the evaluation</Link>
            </p>
          )}
        </aside>
      </div>
    </>
  );
}

export default function InspectionScreen() {
  const { id = "" } = useParams();
  const inspection = useAsyncData(() => api.inspection(id), [id]);
  // Siblings, name and rank come from the fleet; the viewer works without it.
  const fleet = useAsyncData(() => api.fleet(), []);
  const orders = useAsyncData(() => api.workOrders().catch(() => [] as WorkOrder[]), []);

  return (
    <section className="screen screen--wide" aria-label="Inspection viewer">
      <Async state={inspection} what="inspection">
        {(data) => <InspectionBody
            inspection={data}
            fleet={fleet.status === "ready" ? fleet.data : null}
            orders={orders.status === "ready" ? orders.data : []}
          />}
      </Async>
    </section>
  );
}
