import type { Defect, DefectType, Turbine, Verdict } from "../types";

export const pct = (value: number, digits = 0): string => `${(value * 100).toFixed(digits)}%`;

export const usd = (value: number): string => `$${value.toFixed(value < 1 ? 4 : 2)}`;

export function duration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function dateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  });
}

export const DEFECT_TYPE_LABEL: Record<DefectType, string> = {
  leading_edge_erosion: "Leading-edge erosion",
  crack: "Crack",
  lightning_damage: "Lightning damage",
  surface_damage: "Surface damage",
  dirt: "Dirt",
  other: "Other",
};

/** `T01-2018/DJI_0681_06_09/d2` -> `d2`. */
export const shortDefectId = (id: string): string => id.slice(id.lastIndexOf("/") + 1);

/** `T01-2018/DJI_0681_06_09/d2` -> `T01-2018/DJI_0681_06_09`. */
export const imageIdOfDefect = (defectId: string): string =>
  defectId.slice(0, defectId.lastIndexOf("/"));

/** `T01-2018/DJI_0681_06_09/d2` -> `T01-2018`. */
export const inspectionIdOfDefect = (defectId: string): string =>
  defectId.slice(0, defectId.indexOf("/"));

/** Link that opens the viewer on one defect (image and defect preselected). */
export function defectLink(defectId: string): string {
  const query = new URLSearchParams({
    image: imageIdOfDefect(defectId),
    defect: defectId,
  });
  return `/inspections/${encodeURIComponent(inspectionIdOfDefect(defectId))}?${query}`;
}

export function latestInspection(turbine: Turbine) {
  return [...turbine.inspections].sort((a, b) => b.year - a.year)[0];
}

/** The most urgent of two verdicts: reinspect > needs_review > ok. */
const VERDICT_RANK: Record<Verdict, number> = { ok: 0, needs_review: 1, reinspect: 2 };
export const worseVerdict = (a: Verdict, b: Verdict): Verdict =>
  VERDICT_RANK[a] >= VERDICT_RANK[b] ? a : b;

export const defectsLabel = (n: number): string => `${n} defect${n === 1 ? "" : "s"}`;

/** Detector confidence band of a SAM defect, for the card header. */
export const conceptLabel = (defect: Defect): string =>
  defect.source === "box_prompt" ? `${defect.concept} · box prompt` : defect.concept;
