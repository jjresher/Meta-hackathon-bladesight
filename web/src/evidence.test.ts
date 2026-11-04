import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { DEV_FALSE_ALARM_RATE as far, SEVERITY_AGREEMENT as s } from "./evidence";

/** AGENTS.md rule 5: a number shown in the UI must match the evidence file it links to. */
describe("SEVERITY_AGREEMENT matches its evidence file", () => {
  const text = readFileSync(resolve(process.cwd(), "..", s.file), "utf8");

  it("kappa and its interval", () => {
    const m = /Quadratic weighted kappa: \*\*(-?[\d.]+)\*\* \(95% bootstrap interval (-?[\d.]+) to (-?[\d.]+)\)/.exec(text);
    expect(m, "kappa line not found").not.toBeNull();
    expect([Number(m![1]), Number(m![2]), Number(m![3])]).toEqual([s.kappa, s.kappaLow, s.kappaHigh]);
  });

  it("agreement shares, crop counts and bias", () => {
    expect(text).toContain(`Crops: ${s.crops}; compared: ${s.crops}.`);
    expect(text).toContain(`Exact agreement: ${s.exactAgreementPct}%; within one level: ${s.withinOnePct}%`);
    expect(text).toContain(`mean (model - human):\n  ${s.meanModelMinusHuman.toFixed(2)} levels`);
    expect(text).toContain(`Model severity distribution: {1: ${s.modelGradedOne},`);
    expect(text).toContain(`Human severity distribution: {1: ${s.humanGradedOne},`);
  });
});

describe("DEV_FALSE_ALARM_RATE matches its evidence file", () => {
  it("false-alarm rate on tiles with no dataset box", () => {
    const text = readFileSync(resolve(process.cwd(), "..", far.file), "utf8");
    expect(text).toContain(`False-alarm rate on tiles with no box at all: **${far.rate.toFixed(3)}** over ${far.cleanTiles} tiles`);
  });
});
