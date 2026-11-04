import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { DETECTOR_V2 as d2, FALSE_ALARM_RATE, GUARD_RULES, OPEN_WEIGHTS_FARM as ow, SEVERITY_AGREEMENT as s } from "./evidence";

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

describe("FALSE_ALARM_RATE matches its evidence files", () => {
  for (const split of ["dev", "heldout"] as const) {
    it(`${split}: false-alarm rate on tiles with no dataset box`, () => {
      const far = FALSE_ALARM_RATE[split];
      const text = readFileSync(resolve(process.cwd(), "..", far.file), "utf8");
      expect(text).toContain(
        `False-alarm rate on tiles with no box at all: **${far.rate.toFixed(3)}** over ${far.cleanTiles} tiles`,
      );
    });
  }
});

describe("DETECTOR_V2 matches its evidence file", () => {
  it("verdict, F1 and false alarms", () => {
    const text = readFileSync(resolve(process.cwd(), "..", d2.file), "utf8");
    expect(text).toContain("## Verdict: **v2 wins**");
    expect(text).toContain(`Tiles: ${d2.tiles} fresh dev tiles`);
    expect(text).toContain(`damage F1 at IoU 0.3: v1 ${d2.f1V1.toFixed(3)}, v2 ${d2.f1V2.toFixed(3)}`);
    const rate = d2.falseAlarm.toFixed(3);
    expect(text).toContain(`false-alarm rate on tiles with no box: v1 ${rate}, v2 ${rate}`);
  });
});

describe("OPEN_WEIGHTS_FARM matches its evidence file", () => {
  const text = readFileSync(resolve(process.cwd(), "..", ow.file), "utf8");
  const v = ow.verdicts;

  it("per-defect agreement and verdict counts", () => {
    expect(text).toContain(`Defects graded and verified in both runs: ${ow.defects} (Meta ${ow.defects}, Open ${ow.defects};`);
    expect(text).toContain(
      `Same severity: **${ow.sameSeverity} of ${ow.defects}** (${ow.sameSeverityPct}%); within one level: ${ow.withinOne} (${ow.withinOnePct}%).`,
    );
    expect(text).toContain(
      `Same verdict: **${ow.sameVerdict} of ${ow.defects}** (${ow.sameVerdictPct}%). Verdict counts: ` +
        `Meta \`ok\` ${v.meta.ok}, \`needs_review\` ${v.meta.needs_review}, \`reinspect\` ${v.meta.reinspect}; ` +
        `Open \`ok\` ${v.baseten.ok}, \`needs_review\` ${v.baseten.needs_review}, \`reinspect\` ${v.baseten.reinspect}.`,
    );
  });

  it("verdict matrix", () => {
    const rows = ["`ok`", "`needs_review`", "`reinspect`"];
    ow.verdictMatrix.forEach((row, i) => expect(text).toContain(`| ${rows[i]} | ${row.join(" | ")} |`));
  });

  it("ranking and work orders", () => {
    expect(text).toContain(`Spearman rank correlation over the ${ow.turbines} turbines: ${ow.spearman}.`);
    expect(text).toContain(`in both: ${ow.topSixInBoth} of 6.`);
    expect(text).toContain(
      `Meta run \`${ow.orders.metaRun}\`: ${ow.orders.meta} orders; Open run \`${ow.orders.openRun}\`: ${ow.orders.baseten} orders.`,
    );
    const r = ow.repairDefects;
    expect(text).toContain(`Defects in a repair order in both runs: ${r.both} of ${r.union} (Meta ${r.meta}, Open ${r.baseten}).`);
    const x = ow.reinspectDefects;
    expect(text).toContain(
      `Defects in a re-inspection request in both runs: ${x.both} of ${x.union} (Meta ${x.meta}, Open ${x.baseten}).`,
    );
  });
});

describe("GUARD_RULES matches src/bladesight/fleet/rules.py", () => {
  it("same ids, same order, same text", () => {
    const source = readFileSync(resolve(process.cwd(), "..", GUARD_RULES.file), "utf8");
    const found = [...source.matchAll(/_rule\(\s*"([a-z_]+)",\s*((?:"(?:[^"\\]|\\.)*"\s*)+),/g)].map((m) => ({
      id: m[1],
      text: [...m[2].matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((part) => part[1]).join(""),
    }));
    expect(found.length).toBeGreaterThan(0);
    expect(found).toEqual(GUARD_RULES.rules.map((r) => ({ id: r.id, text: r.text })));
  });
});
