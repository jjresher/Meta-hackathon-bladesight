import { describe, expect, it } from "vitest";

import inspectionFixture from "../fixtures/inspection_T03-2018.json";
import type { Inspection, InspectionImage, Verdict } from "../types";
import { sortTilesBySeverity } from "./tiles";

type Spec = [severity: number, verdict: Verdict | null];

const tile = (id: string, defects: Spec[]): InspectionImage => ({
  id,
  tile_id: id,
  image_url: `/images/${id}.png`,
  width: 586,
  height: 371,
  blade_outline: [],
  defects: defects.map(([severity, verdict], n) => ({
    defect: { id: `${id}/d${n}` },
    measurement: null,
    assessment: { severity },
    verification: verdict ? { verdict } : null,
    error: null,
  })) as unknown as InspectionImage["defects"],
});

const order = (tiles: InspectionImage[]) => sortTilesBySeverity(tiles).map((t) => t.id);

describe("sortTilesBySeverity", () => {
  it("puts the highest severity first and tiles without defects last", () => {
    const tiles = [tile("none", []), tile("low", [[1, "ok"]]), tile("high", [[4, "needs_review"]]), tile("mid", [[3, "ok"]])];
    expect(order(tiles)).toEqual(["high", "mid", "low", "none"]);
  });

  it("ranks a tile by its worst defect, not by how many it has", () => {
    const tiles = [tile("many", [[1, "ok"], [1, "ok"], [2, "ok"]]), tile("one", [[3, "ok"]])];
    expect(order(tiles)).toEqual(["one", "many"]);
  });

  it("puts verified before needs review at the same severity", () => {
    const tiles = [tile("review", [[3, "needs_review"]]), tile("verified", [[3, "ok"]])];
    expect(order(tiles)).toEqual(["verified", "review"]);
  });

  it("counts a verified defect only when it holds the top severity", () => {
    const tiles = [tile("low-verified", [[3, "needs_review"], [2, "ok"]]), tile("top-verified", [[3, "ok"]])];
    expect(order(tiles)).toEqual(["top-verified", "low-verified"]);
  });

  it("breaks a tie by reinspect defects, then by needs_review defects", () => {
    const tiles = [
      tile("two-review", [[3, "ok"], [2, "needs_review"], [2, "needs_review"]]),
      tile("one-review", [[3, "ok"], [2, "needs_review"]]),
      tile("one-reinspect", [[3, "ok"], [2, "reinspect"]]),
    ];
    expect(order(tiles)).toEqual(["one-reinspect", "two-review", "one-review"]);
  });

  it("never counts a defect without a verdict as verified, reinspect or needs review", () => {
    const tiles = [tile("unverified", [[3, null]]), tile("verified", [[3, "ok"]]), tile("review", [[3, "needs_review"]])];
    expect(order(tiles)).toEqual(["verified", "review", "unverified"]);
  });

  it("ranks a tile whose defects have no assessment after any graded tile", () => {
    const ungraded = tile("ungraded", [[0, null]]);
    (ungraded.defects[0] as { assessment: unknown }).assessment = null;
    expect(order([ungraded, tile("graded", [[1, "ok"]])])).toEqual(["graded", "ungraded"]);
  });

  it("keeps the original order on a full tie (stable) and does not mutate the input", () => {
    const tiles = [tile("a", [[2, "ok"]]), tile("b", [[2, "ok"]]), tile("empty-1", []), tile("c", [[2, "ok"]]), tile("empty-2", [])];
    const before = tiles.map((t) => t.id);
    expect(order(tiles)).toEqual(["a", "b", "c", "empty-1", "empty-2"]);
    expect(tiles.map((t) => t.id)).toEqual(before);
  });

  it("handles an inspection without tiles", () => {
    expect(sortTilesBySeverity([])).toEqual([]);
  });

  it("orders the example inspection with its most severe tile first", () => {
    const { images } = inspectionFixture as unknown as Inspection;
    const sorted = sortTilesBySeverity(images);
    expect(sorted).toHaveLength(images.length);
    expect(new Set(sorted.map((t) => t.id))).toEqual(new Set(images.map((t) => t.id)));
    const top = (t: InspectionImage) => Math.max(0, ...t.defects.map((d) => d.assessment?.severity ?? 0));
    expect(top(sorted[0])).toBe(Math.max(...images.map(top)));
  });
});
