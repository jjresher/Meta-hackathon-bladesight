import { describe, expect, it } from "vitest";

import { ApiClient, NotFoundError } from "./client";

describe("ApiClient (mock mode)", () => {
  const api = new ApiClient();

  it("exposes the honest farm label", () => {
    expect(api.getFarmLabel()).toBe("Synthetic farm built from real DTU drone photos");
  });

  it("returns 12 turbines ranked 1..12 by priority", async () => {
    const fleet = await api.getFleet();
    expect(fleet).toHaveLength(12);
    expect(fleet.map((t) => t.rank)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    // Ranks are monotonic with descending priority.
    for (let i = 1; i < fleet.length; i++) {
      expect(fleet[i - 1].priority).toBeGreaterThanOrEqual(fleet[i].priority);
    }
  });

  it("derives each turbine status from its worst defect verdict", async () => {
    const fleet = await api.getFleet();
    const t01 = fleet.find((t) => t.id === "T01");
    expect(t01?.status).toBe("reinspect");
  });

  it("returns an inspection by id and throws NotFoundError otherwise", async () => {
    const inspection = await api.getInspection("T01-2018");
    expect(inspection.turbineId).toBe("T01");
    expect(inspection.defects.length).toBeGreaterThan(0);
    await expect(api.getInspection("does-not-exist")).rejects.toBeInstanceOf(NotFoundError);
  });

  it("only cites defect ids that exist in the inspections", async () => {
    const workOrders = await api.getWorkOrders();
    const inspections = await Promise.all(
      (await api.getFleet()).flatMap((t) => t.inspectionIds).map((id) => api.getInspection(id)),
    );
    const knownDefectIds = new Set(inspections.flatMap((i) => i.defects.map((d) => d.id)));
    expect(workOrders.length).toBeGreaterThan(0);
    for (const wo of workOrders) {
      expect(wo.defectIds.length).toBeGreaterThan(0);
      for (const defectId of wo.defectIds) {
        expect(knownDefectIds.has(defectId)).toBe(true);
      }
    }
  });

  it("returns the agent trace in step order", async () => {
    const trace = await api.getAgentTrace();
    expect(trace.length).toBeGreaterThan(0);
    expect(trace.map((s) => s.index)).toEqual(
      [...trace.map((s) => s.index)].sort((a, b) => a - b),
    );
  });

  it("returns an eval report with a threshold curve and limitations", async () => {
    const report = await api.getEvalReport();
    expect(report.thresholdCurve.length).toBeGreaterThan(0);
    expect(report.limitations.length).toBeGreaterThan(0);
    expect(report.metrics).toHaveProperty("recall");
  });

  it("accepts an injected dataset for the one-line fixtures switch", async () => {
    const custom = new ApiClient({
      farmLabel: "custom",
      turbines: [],
      inspections: [],
      report: { generatedAt: "", summary: "", rankedTurbineIds: [], workOrders: [] },
      agentTrace: [],
      evalReport: {
        split: "dev",
        iou: 0.3,
        metrics: {},
        thresholdCurve: [],
        limitations: [],
        evidenceRef: "",
      },
    });
    expect(custom.getFarmLabel()).toBe("custom");
    expect(await custom.getFleet()).toHaveLength(0);
  });
});
