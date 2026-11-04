import { useEffect, useRef, useState } from "react";

import { imageUrl } from "../api/client";
import { shortDefectId } from "../lib/format";
import type { InspectedDefect, InspectionImage, Polygon } from "../types";
import { ImageOffIcon } from "./icons";

export interface Layers {
  masks: boolean;
  boxes: boolean;
  blade: boolean;
}

interface PhotoViewerProps {
  image: InspectionImage;
  layers: Layers;
  selectedId: string | null;
  onSelect: (defectId: string | null) => void;
}

/** SVG path for a set of closed polygons in image pixels. */
function outlinePath(polygons: Polygon[]): string {
  return polygons
    .filter((ring) => ring.length >= 3)
    .map((ring) => `M${ring.map(([x, y]) => `${x} ${y}`).join(" L")} Z`)
    .join(" ");
}

function verdictOf(item: InspectedDefect): string {
  return item.verification?.verdict ?? "unverified";
}

/**
 * The real tile streamed by the API, with the SAM masks and boxes drawn on top as SVG in image
 * pixel coordinates. Masks and boxes are separate layers. If the photo cannot be loaded the
 * viewer says so and draws nothing over a blank: geometry without its photo would mislead.
 */
export default function PhotoViewer({ image, layers, selectedId, onSelect }: PhotoViewerProps) {
  const src = imageUrl(image.image_url);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const imgRef = useRef<HTMLImageElement>(null);
  const { width, height } = image;

  // A new tile (or a retry) starts from "loading"; a cached image may already be complete.
  useEffect(() => {
    setStatus("loading");
    const el = imgRef.current;
    if (el?.complete) setStatus(el.naturalWidth > 0 ? "ready" : "error");
  }, [src, attempt]);

  const defects = image.defects;
  // The selected defect is drawn last so it sits on top of overlapping ones.
  const ordered = [...defects].sort(
    (a, b) => Number(a.defect.id === selectedId) - Number(b.defect.id === selectedId),
  );
  const bladePath = outlinePath(image.blade_outline);

  return (
    <div className="photo" style={{ aspectRatio: `${width} / ${height}` }} data-testid="photo-viewer">
      {status !== "error" && (
        <img
          key={`${src}#${attempt}`}
          ref={imgRef}
          className={`photo__img${status === "ready" ? " is-ready" : ""}`}
          src={attempt > 0 ? `${src}${src.includes("?") ? "&" : "?"}retry=${attempt}` : src}
          alt={`Drone photo ${image.tile_id} with ${defects.length} detected defect${defects.length === 1 ? "" : "s"}`}
          width={width}
          height={height}
          decoding="async"
          onLoad={() => setStatus("ready")}
          onError={() => setStatus("error")}
          draggable={false}
        />
      )}

      {status === "loading" && <div className="photo__skeleton" aria-hidden="true" />}

      {status === "error" && (
        <div className="photo__error" role="alert" data-testid="photo-error">
          <ImageOffIcon />
          <p className="photo__error-title">Photo unavailable</p>
          <p className="photo__error-detail">
            The tile <code>{image.tile_id}</code> could not be loaded from <code>{image.image_url}</code>.
            The defect data beside it is unaffected.
          </p>
          <button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>
            Try again
          </button>
        </div>
      )}

      {status === "ready" && (
        <>
          <svg
            className="photo__overlay"
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="none"
            role="group"
            aria-label="Detection overlay"
            onClick={() => onSelect(null)}
          >
            {layers.blade && bladePath && (
              <path d={bladePath} className="ov-blade" vectorEffect="non-scaling-stroke" data-testid="blade-outline" />
            )}
            {layers.masks &&
              ordered.map(({ defect, verification }) => {
                const d = outlinePath(defect.outline);
                if (!d) return null;
                const selected = defect.id === selectedId;
                return (
                  <path
                    key={defect.id}
                    d={d}
                    className={`ov-mask ov-mask--${verification?.verdict ?? "unverified"}${selected ? " is-selected" : ""}`}
                    vectorEffect="non-scaling-stroke"
                    data-testid="mask"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(defect.id);
                    }}
                  />
                );
              })}
            {layers.boxes &&
              ordered.map((item) => {
                const { defect } = item;
                const selected = defect.id === selectedId;
                return (
                  <rect
                    key={defect.id}
                    x={defect.bbox.x1}
                    y={defect.bbox.y1}
                    width={defect.bbox.x2 - defect.bbox.x1}
                    height={defect.bbox.y2 - defect.bbox.y1}
                    className={`ov-box ov-box--${verdictOf(item)}${selected ? " is-selected" : ""}`}
                    vectorEffect="non-scaling-stroke"
                    data-testid="box"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(defect.id);
                    }}
                  />
                );
              })}
          </svg>

          {layers.boxes &&
            defects.map((item) => {
              const { defect } = item;
              const inside = defect.bbox.y1 / height < 0.09; // no room above the box
              return (
                <span
                  key={defect.id}
                  className={`photo__tag photo__tag--${verdictOf(item)}${defect.id === selectedId ? " is-selected" : ""}${inside ? " is-inside" : ""}`}
                  style={{
                    left: `${(defect.bbox.x1 / width) * 100}%`,
                    top: `${(defect.bbox.y1 / height) * 100}%`,
                  }}
                  aria-hidden="true"
                >
                  {shortDefectId(defect.id)}
                </span>
              );
            })}
        </>
      )}
    </div>
  );
}
