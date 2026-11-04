import { describe, expect, it } from "vitest";

import { defectLink, imageIdOfDefect, inspectionIdOfDefect, shortDefectId, worseVerdict } from "./format";

describe("defect ids", () => {
  const id = "T01-2018/DJI_0681_06_09/d2";

  it("splits into inspection, image and short id", () => {
    expect(inspectionIdOfDefect(id)).toBe("T01-2018");
    expect(imageIdOfDefect(id)).toBe("T01-2018/DJI_0681_06_09");
    expect(shortDefectId(id)).toBe("d2");
  });

  it("links to the viewer with the image and the defect preselected", () => {
    const link = defectLink(id);
    expect(link.startsWith("/inspections/T01-2018?")).toBe(true);
    const params = new URLSearchParams(link.split("?")[1]);
    expect(params.get("image")).toBe("T01-2018/DJI_0681_06_09");
    expect(params.get("defect")).toBe(id);
  });
});

describe("worseVerdict", () => {
  it("orders reinspect > needs_review > ok", () => {
    expect(worseVerdict("ok", "needs_review")).toBe("needs_review");
    expect(worseVerdict("reinspect", "needs_review")).toBe("reinspect");
    expect(worseVerdict("ok", "ok")).toBe("ok");
  });
});
