import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { GUARD_RULES, OPEN_WEIGHTS_FARM } from "../evidence";
import runFixture from "../fixtures/run_run-example-001.json";
import { stubApi, type Overrides } from "../test/mockApi";
import type { AgentRun } from "../types";

const run = runFixture as AgentRun;

function open(path: string, overrides: Overrides = {}) {
  const fetchMock = stubApi(overrides);
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return fetchMock;
}

const calledWith = (fetchMock: ReturnType<typeof stubApi>, url: string) =>
  fetchMock.mock.calls.some(([input]) => String(input) === url);

afterEach(() => vi.unstubAllGlobals());

describe("Run selector", () => {
  it("offers both stored runs with their exact labels, the default checked", async () => {
    open("/");
    const bar = await screen.findByTestId("run-bar");
    expect(within(bar).getByLabelText("Muse Spark (Model API)")).toBeChecked();
    expect(within(bar).getByLabelText("Muse Spark Open (Baseten)")).not.toBeChecked();
  });

  it("says which model ran each stage: detection and SAM 3.1 stay on the Model API", async () => {
    open("/?provider=baseten");
    const stages = await screen.findByTestId("run-stages");
    await waitFor(() => expect(stages).toHaveTextContent("severity, second look, agent: Muse Spark Open (Baseten)"));
    expect(stages).toHaveTextContent("detection: Muse Spark (Model API)");
    expect(stages).toHaveTextContent("masks: SAM 3.1 (Model API)");
  });

  it("switches every data call to the chosen run with ?provider=", async () => {
    const fetchMock = open("/");
    await screen.findAllByTestId("fleet-row");
    await userEvent.setup().click(await screen.findByLabelText("Muse Spark Open (Baseten)"));
    await waitFor(() => expect(calledWith(fetchMock, "/api/fleet?provider=baseten")).toBe(true));
    expect(screen.getByLabelText("Muse Spark Open (Baseten)")).toBeChecked();
  });

  it("reads the run from the URL", async () => {
    const fetchMock = open("/work-orders?provider=baseten");
    await screen.findAllByTestId("work-order");
    expect(calledWith(fetchMock, "/api/work-orders?provider=baseten")).toBe(true);
  });

  it("is hidden when the API lists fewer than two runs", async () => {
    open("/", { "/api/replays": () => ({ body: [] }) });
    await screen.findAllByTestId("fleet-row");
    expect(screen.queryByTestId("run-bar")).toBeNull();
  });
});

describe("Model badges", () => {
  it("on work orders and on the second look", async () => {
    open("/work-orders");
    const order = (await screen.findAllByTestId("work-order"))[0];
    expect(within(order).getByTestId("model-badge")).toHaveTextContent("Muse Spark (Model API)");
  });

  it("on the verification of an opened defect", async () => {
    open("/inspections/T03-2018");
    const card = (await screen.findAllByTestId("defect-card"))[0];
    await userEvent.setup().click(within(card).getAllByRole("button")[0]);
    expect(within(card).getByText("Second look by")).toBeInTheDocument();
  });
});

describe("Defect card accessibility", () => {
  it("has a short accessible name and the why as its description", async () => {
    open("/inspections/T03-2018");
    const card = (await screen.findAllByTestId("defect-card"))[0];
    const button = within(card).getByRole("button", { name: /^d1 .+, verified, severity \d of 5$/ });
    const why = document.getElementById(button.getAttribute("aria-describedby")!);
    expect(why?.textContent?.length).toBeGreaterThan(10);
  });

  it("ignores pointer hover on touch screens, so a highlight never sticks", async () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query === "(hover: none)", media: query }));
    open("/inspections/T03-2018");
    const photo = await screen.findByTestId("photo-viewer");
    await act(async () => {});
    fireEvent.load(within(photo).getByRole("img", { name: /Drone photo/ }));
    fireEvent.mouseEnter((await screen.findAllByTestId("defect-card"))[1]);
    expect(photo).not.toHaveClass("has-hover");
  });
});

describe("Compare runs", () => {
  it("shows the evidence-backed agreement and both run cards, without ranking the models", async () => {
    open("/compare");
    expect(await screen.findAllByTestId("compare-run")).toHaveLength(2);
    const agreement = screen.getByTestId("agreement");
    expect(agreement).toHaveTextContent(`${OPEN_WEIGHTS_FARM.sameSeverity} of ${OPEN_WEIGHTS_FARM.defects}`);
    expect(agreement).toHaveTextContent(`${OPEN_WEIGHTS_FARM.sameVerdict} of ${OPEN_WEIGHTS_FARM.defects}`);
    expect(agreement).toHaveTextContent(String(OPEN_WEIGHTS_FARM.spearman));
    expect(screen.getByTestId("shared-stages")).toHaveTextContent(/segmentation by SAM 3\.1 \(Model API\)/);
    expect(screen.getByRole("link", { name: OPEN_WEIGHTS_FARM.file })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\bbetter\b|\bworse model\b|\bwins?\b/i);
  });
});

describe("Agent trace decisions", () => {
  it("shows why, what was decided and the rule that stopped a call", async () => {
    open("/runs");
    const turns = await screen.findAllByTestId("decision-turn");
    expect(turns.length).toBeGreaterThan(0);
    const first = run.steps.find((s) => s.kind === "tool_call" && s.rationale)!;
    expect(screen.getByText(first.rationale!)).toBeInTheDocument();
    // a call with no stated reason says so instead of inventing one
    expect(screen.getAllByTestId("no-reason").length).toBeGreaterThan(0);
    const blocked = screen.getByTestId("blocked-by");
    expect(blocked).toHaveTextContent("verified_only");
    expect(screen.getByTestId("rule-summary")).toHaveTextContent(/1 call was rejected: step 6 \(verified_only\)/);
    expect(screen.getAllByTestId("guard-rules")[0].querySelectorAll("li")).toHaveLength(GUARD_RULES.rules.length);
  });

  it("says plainly when no call was blocked, and lists the rules in force", async () => {
    const clean = structuredClone(run);
    for (const s of clean.steps) {
      if (s.outcome === "rejected") {
        s.outcome = "accepted";
        s.blocked_by_rule = null;
      }
      if (s.kind === "tool_call") s.rationale = null;
    }
    open("/runs", { "/api/runs": () => ({ body: [clean] }) });
    expect(await screen.findByTestId("rule-summary")).toHaveTextContent("No call was rejected by a rule in this run.");
    expect(screen.queryByTestId("blocked-by")).toBeNull();
    expect(screen.getByTestId("reason-count")).toHaveTextContent(/no text before any call/);
    expect(screen.getByTestId("order-count")).toHaveTextContent(/1 repair, 0 monitor and 1 re-inspection/);
  });

  it("does not claim zero rejections when outcomes were not recorded", async () => {
    const legacy = structuredClone(run);
    for (const s of legacy.steps) {
      if (s.kind === "tool_call") {
        s.outcome = null;
        s.blocked_by_rule = null;
      }
    }
    open("/runs", { "/api/runs": () => ({ body: [legacy] }) });
    expect(await screen.findByTestId("rule-summary")).toHaveTextContent(/Rejections were not recorded for \d+ of the calls/);
    expect(screen.getByTestId("rule-summary")).not.toHaveTextContent("No call was rejected");
  });
});
