import { describe, expect, it } from "vitest";

import { modelLabel, stagesByModel } from "./models";

describe("modelLabel", () => {
  it("names the two Muse Spark runs exactly as the run selector does", () => {
    expect(modelLabel("muse-spark-1.3", "meta")).toBe("Muse Spark (Model API)");
    expect(modelLabel("meta-models/muse-spark-open", "baseten")).toBe("Muse Spark Open (Baseten)");
    expect(modelLabel("sam-3.1", "meta")).toBe("SAM 3.1 (Model API)");
  });

  it("falls back to the raw model id when it is not a Muse Spark model", () => {
    expect(modelLabel("llama-4-scout", "baseten")).toBe("llama-4-scout");
    expect(modelLabel("muse-spark-1.3", "stub")).toBe("muse-spark-1.3 (stub)");
    expect(modelLabel(null, "meta")).toBe("unknown model");
  });

  it("groups stages by the model that ran them", () => {
    const groups = stagesByModel([
      { stage: "detection_proposals", model: "muse-spark-1.3", provider: "meta" },
      { stage: "segmentation", model: "sam-3.1", provider: "meta" },
      { stage: "severity", model: "meta-models/muse-spark-open", provider: "baseten" },
      { stage: "agent", model: "meta-models/muse-spark-open", provider: "baseten" },
    ]);
    expect(groups).toEqual([
      ["Muse Spark (Model API)", ["detection proposals"]],
      ["SAM 3.1 (Model API)", ["segmentation"]],
      ["Muse Spark Open (Baseten)", ["severity", "agent and report"]],
    ]);
  });
});
