import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, imageUrl } from "../api/client";
import { TrendBadge } from "../components/Chips";
import DefectCard from "../components/DefectCard";
import OverlayLegend from "../components/OverlayLegend";
import PhotoViewer, { VERDICT_TEXT, type Layers } from "../components/PhotoViewer";
import { Async } from "../components/PageState";
import SeverityScale from "../components/SeverityScale";
import { ArrowLeftIcon, InfoIcon } from "../components/icons";
import { SEVERITY_AGREEMENT } from "../evidence";
import { useAsyncData } from "../hooks/useAsyncData";
import { useRun } from "../lib/run";
import { defectsLabel, tilesLabel, worseVerdict } from "../lib/format";
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
          <span className="thumb__missing">no image</span>
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
  const [hoverId, setHoverState] = useState<string | null>(null);
  // Touch screens emulate mouseenter on tap and never send mouseleave, so a highlight would stick:
  // follow the pointer only where it can really hover. Keyboard focus still lights the pair.
  const canHover = useMemo(
    () => typeof window.matchMedia !== "function" || !window.matchMedia("(hover: none)").matches,
    [],
  );

  const imageParam = params.get("image");
  const image = images.find((i) => i.id === imageParam) ?? images.find((i) => i.defects.length > 0) ?? images[0];
  const defectParam = params.get("defect");
  // Nothing is opened by default, so every defect on the tile reads at a glance (severity, verdict,
  // why); a link with ?defect= (from a work order) opens that one.
  const selectedId = image?.defects.find((d) => d.defect.id === defectParam)?.defect.id ?? null;

  const turbine = fleet?.turbines.find((t) => t.id === summary.turbine_id);
  const inspectionOrders = orders.filter((o) => o.inspection_id === summary.id);
  const hasBlade = (image?.blade_outline.length ?? 0) > 0;

  const setHoverId = (id: string | null, fromFocus = false) => {
    if (id === null || fromFocus || canHover) setHoverState(id);
  };

  const setSelection = (imageId: string, defectId: string | null) => {
    setHoverState(null);
    const next = new URLSearchParams(params);
    next.set("image", imageId);
    next.set("defect", defectId ?? "");
    setParams(next, { replace: true });
  };

  // Left/right arrows move between the tiles of the inspection; Escape clears the selection.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (event.key === "Escape" && image) setSelection(image.id, null);
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const at = images.findIndex((i) => i.id === image?.id);
      const next = images[at + (event.key === "ArrowRight" ? 1 : -1)];
      if (next) setSelection(next.id, null);
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
      <p className="note note--empty">
        <InfoIcon className="note__icon" />
        <span>This inspection has no tiles.</span>
      </p>
    );
  }

  // "2 verified, 2 needs review": the verdicts of this tile at a glance, counted from the data.
  const tally = (["ok", "needs_review", "reinspect", "unverified"] as const)
    .map((v) => [v, image.defects.filter((d) => (d.verification?.verdict ?? "unverified") === v).length] as const)
    .filter(([, n]) => n > 0)
    .map(([v, n]) => `${n} ${VERDICT_TEXT[v].toLowerCase()}`)
    .join(", ");
  const citing = (defectId: string) => orders.filter((o) => o.defect_ids.includes(defectId)).map((o) => o.id);

  return (
    <>
      <header className="insp-head">
        <div className="insp-head__main">
          <Link to="/" className="back">
            <ArrowLeftIcon /> Fleet
          </Link>
          <h1>
            {turbine?.name ?? `Turbine ${summary.turbine_id}`} <span className="insp-head__year">{summary.year}</span>
          </h1>
          <p className="insp-head__meta">
            {turbine && (
              <span>
                Rank {turbine.rank} of {fleet?.turbines.length}
              </span>
            )}
            {turbine && <TrendBadge trend={turbine.trend} />}
            <span>
              {tilesLabel(summary.n_images)} · {defectsLabel(summary.n_defects)}
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
        <div className="stage">
          <PhotoViewer
            key={image.id}
            image={image}
            layers={layers}
            selectedId={selectedId}
            onSelect={(defectId) => setSelection(image.id, defectId)}
            hoverId={hoverId}
            onHover={(id) => setHoverId(id)}
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
                hint={hasBlade ? undefined : "No blade outline was segmented on this tile"}
                onChange={(v) => setLayers({ ...layers, blade: v })}
              />
            </div>
            <p className="stage__meta num">
              {image.tile_id} · {image.width}×{image.height}px tile
            </p>
          </div>
        </div>

        <OverlayLegend />

        <ul className="filmstrip" aria-label="Tiles in this inspection">
          {images.map((i) => (
            <li key={i.id}>
              <Thumb image={i} active={i.id === image.id} onClick={() => setSelection(i.id, null)} />
            </li>
          ))}
        </ul>

        <aside className="insp-side" ref={sideRef} aria-label="Defects on this tile">
          <h2 className="side-title">
            {image.defects.length === 0 ? "No defects on this tile" : `${defectsLabel(image.defects.length)} on this tile`}
            {tally && <span className="side-title__tally">{tally}</span>}
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
                hovered={item.defect.id === hoverId}
                onHover={(on, fromFocus) => setHoverId(on ? item.defect.id : null, fromFocus)}
                workOrders={citing(item.defect.id)}
                onSelect={() =>
                  setSelection(image.id, item.defect.id === selectedDefect?.defect.id ? null : item.defect.id)
                }
              />
            ))}
          </div>
          {image.defects.some((d) => d.assessment) && (
            <p className="side-foot">
              Severity is advisory: agreement with a human grader is low (kappa {SEVERITY_AGREEMENT.kappa}).{" "}
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
  const { provider } = useRun();
  const inspection = useAsyncData(() => api.inspection(id, provider), [id, provider]);
  // Siblings, name and rank come from the fleet; the viewer works without it.
  const fleet = useAsyncData(() => api.fleet(provider), [provider]);
  const orders = useAsyncData(() => api.workOrders(provider).catch(() => [] as WorkOrder[]), [provider]);

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
