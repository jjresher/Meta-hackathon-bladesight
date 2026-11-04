import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import evalReports from "../fixtures/eval.json";
import fleetFixture from "../fixtures/fleet.json";
import inspectionFixture from "../fixtures/inspection_T03-2018.json";
import type { Inspection } from "../types";
import { stubApi, type Overrides } from "../test/mockApi";

const inspection = inspectionFixture as Inspection;

function open(path: string, overrides: Overrides = {}) {
  const fetchMock = stubApi(overrides);
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("Fleet", () => {
  it("ranks every turbine, labels the farm synthetic and links to the latest inspection", async () => {
    open("/");
    const rows = await screen.findAllByTestId("fleet-row");
    expect(rows).toHaveLength(12);
    expect(within(rows[0]).getByText("Turbine 03")).toBeInTheDocument();
    expect(screen.getByTestId("fleet-note")).toHaveTextContent(/synthetic/i);
    expect(within(rows[0]).getByRole("link", { name: /open latest inspection T03-2018/ })).toHaveAttribute(
      "href",
      "/inspections/T03-2018",
    );
  });

  it("sums the verdicts of every inspection in the fleet strip", async () => {
    open("/");
    const strip = await screen.findByTestId("verdict-strip");
    const inspections = fleetFixture.turbines.flatMap((t) => t.inspections);
    const sum = (key: "n_defects" | "n_needs_review" | "n_reinspect") => inspections.reduce((n, i) => n + i[key], 0);
    const review = sum("n_needs_review");
    const reinspect = sum("n_reinspect");
    expect(strip).toHaveTextContent(`${sum("n_defects")}defects in${inspections.length} inspections`);
    expect(strip).toHaveTextContent(`Verified ${sum("n_defects") - review - reinspect}`);
    expect(strip).toHaveTextContent(`Needs review ${review}`);
    expect(strip).toHaveTextContent(`Reinspect ${reinspect}`);
  });

  it("shows a clear error when the API is down", async () => {
    open("/", { "/api/fleet": () => ({ status: 500, body: { detail: "boom" } }) });
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});

describe("Inspection viewer", () => {
  const openViewer = async () => {
    open("/inspections/T03-2018");
    const photo = await screen.findByTestId("photo-viewer");
    const img = within(photo).getByRole("img", { name: /Drone photo/ });
    // findBy can return before the viewer's reset effect has run: flush it, or it would undo the load.
    await act(async () => {});
    fireEvent.load(img);
    return { photo, img };
  };

  it("shows the real tile streamed by the API, not a drawing", async () => {
    const { img } = await openViewer();
    expect(img).toHaveAttribute("src", "/images/DJI_0702_04_05.png");
  });

  it("draws masks and boxes from the API and toggles them separately", async () => {
    const user = userEvent.setup();
    const { photo } = await openViewer();
    expect(await within(photo).findAllByTestId("mask")).toHaveLength(2);
    expect(within(photo).getAllByTestId("box")).toHaveLength(2);

    await user.click(screen.getByTestId("toggle-masks"));
    expect(within(photo).queryAllByTestId("mask")).toHaveLength(0);
    expect(within(photo).getAllByTestId("box")).toHaveLength(2);

    await user.click(screen.getByTestId("toggle-boxes"));
    expect(within(photo).queryAllByTestId("box")).toHaveLength(0);

    await user.click(screen.getByTestId("toggle-masks"));
    expect(within(photo).getAllByTestId("mask")).toHaveLength(2);
  });

  it("marks each box with its verdict shape, not colour alone", async () => {
    const { photo } = await openViewer();
    const tags = within(photo).getAllByTestId("box-tag").map((t) => t.textContent);
    expect(tags).toEqual(["✓ d1", "◆ d2"]); // ok, needs_review in the fixture
  });

  it("offers the blade layer only when the photo has a blade outline", async () => {
    const { photo } = await openViewer();
    expect(within(photo).getByTestId("blade-outline")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByTestId("toggle-blade"));
    expect(within(photo).queryByTestId("blade-outline")).toBeNull();
  });

  it("says so, and draws nothing, when the photo does not load", async () => {
    open("/inspections/T03-2018");
    const photo = await screen.findByTestId("photo-viewer");
    fireEvent.error(within(photo).getByRole("img", { name: /Drone photo/ }));
    expect(await within(photo).findByTestId("photo-error")).toHaveTextContent("Photo unavailable");
    expect(within(photo).queryAllByTestId("mask")).toHaveLength(0);
    expect(within(photo).queryAllByTestId("box")).toHaveLength(0);
    // the defect data is still there
    expect(screen.getAllByTestId("defect-card").length).toBeGreaterThan(0);
  });

  it("opens the defect named in the URL and shows who graded it", async () => {
    const id = "T03-2018/DJI_0702_04_05/d2";
    open(`/inspections/T03-2018?image=${encodeURIComponent("T03-2018/DJI_0702_04_05")}&defect=${encodeURIComponent(id)}`);
    const card = (await screen.findAllByTestId("defect-card")).find((c) => c.dataset.defectId === id)!;
    expect(card).toHaveAttribute("data-selected", "true");
    expect(within(card).getByText(/Graded by/)).toBeInTheDocument();
  });

  it("lists every defect collapsed, with severity, verdict, why and the grading model", async () => {
    await openViewer();
    const cards = screen.getAllByTestId("defect-card");
    expect(cards).toHaveLength(2);
    for (const card of cards) expect(card).toHaveAttribute("data-selected", "false");
    expect(within(cards[0]).getByText(/severity \d of 5/)).toBeInTheDocument();
    expect(within(cards[0]).getByText("Verified")).toBeInTheDocument();
    expect(within(cards[0]).getByTestId("model-badge")).toHaveTextContent("Muse Spark (Model API)");
    // a flagged defect leads with the verification reason, taken as is from the data
    const flagged = inspection.images[0].defects[1];
    expect(within(cards[1]).getByText(flagged.verification!.reasons[0])).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /2 defects on this tile/i })).toHaveTextContent(
      "1 verified, 1 needs review",
    );
  });

  it("labels the open-weights grader from Assessment.provider", async () => {
    const data = structuredClone(inspection);
    data.images[0].defects[0].assessment!.provider = "baseten";
    data.images[0].defects[0].assessment!.model = "meta-models/muse-spark-open";
    open("/inspections/T03-2018", { "/api/inspections/T03-2018": () => ({ body: data }) });
    const card = (await screen.findAllByTestId("defect-card"))[0];
    expect(within(card).getByTestId("model-badge")).toHaveTextContent("Muse Spark Open (Baseten)");
  });

  it("lights up a defect's overlay when its card is hovered, and the card when its mask is", async () => {
    const { photo } = await openViewer();
    const [first, second] = screen.getAllByTestId("defect-card");
    fireEvent.mouseEnter(second);
    const masks = within(photo).getAllByTestId("mask");
    const lit = masks.filter((m) => m.classList.contains("is-hover"));
    expect(lit).toHaveLength(1);
    expect(photo).toHaveClass("has-hover");
    fireEvent.mouseLeave(second);
    expect(within(photo).getAllByTestId("mask").some((m) => m.classList.contains("is-hover"))).toBe(false);

    fireEvent.mouseEnter(masks.find((m) => !m.classList.contains("ov-mask--needs_review"))!);
    expect(first).toHaveClass("is-hover");
  });

  it("explains every overlay glyph, including ? for a defect that was never verified", async () => {
    const data = structuredClone(inspection);
    data.images[0].defects[0].verification = null;
    open("/inspections/T03-2018", { "/api/inspections/T03-2018": () => ({ body: data }) });
    const photo = await screen.findByTestId("photo-viewer");
    await act(async () => {});
    fireEvent.load(within(photo).getByRole("img", { name: /Drone photo/ }));
    const tags = (await within(photo).findAllByTestId("box-tag")).map((t) => t.textContent);
    expect(tags).toEqual(["? d1", "◆ d2"]);
    expect(screen.getByTestId("legend-unverified")).toHaveTextContent(/\?\s*Unverified: not checked/);
    for (const v of ["ok", "needs_review", "reinspect"]) expect(screen.getByTestId(`legend-${v}`)).toBeInTheDocument();
    const card = screen.getAllByTestId("defect-card")[0];
    expect(within(card).getByText("Unverified")).toHaveAttribute("title", expect.stringMatching(/did not run/));
  });

  it("counts tiles, not photos, in the inspection header", async () => {
    await openViewer();
    expect(screen.getByText(/2 tiles · 4 defects/)).toBeInTheDocument();
  });

  it("reports an unknown inspection as not found", async () => {
    open("/inspections/NOPE");
    expect(await screen.findByRole("alert")).toHaveTextContent(/not found/i);
  });
});

describe("Work orders", () => {
  it("lists orders that cite their defects and link into the viewer", async () => {
    open("/work-orders");
    const orders = await screen.findAllByTestId("work-order");
    expect(orders.length).toBeGreaterThan(0);
    const cite = within(orders[0]).getAllByRole("link").find((a) => a.getAttribute("href")?.startsWith("/inspections/"))!;
    expect(cite.getAttribute("href")).toContain("defect=");
    expect(await screen.findByText(/Report written by the agent/)).toBeInTheDocument();
  });
});

describe("Agent trace", () => {
  it("shows the latest run, flagged as a replay", async () => {
    open("/runs");
    expect(await screen.findByTestId("replay-note")).toHaveTextContent(/no model call/i);
    expect((await screen.findAllByTestId("trace-step")).length).toBeGreaterThan(0);
  });
});

describe("Evaluation", () => {
  it("shows dev numbers with intervals, the kappa with its honest reading, and a pending held-out tab", async () => {
    open("/eval");
    expect(await screen.findByTestId("kappa-value")).toHaveTextContent("0.12");
    expect(screen.getByTestId("kappa")).toHaveTextContent(/barely above chance/);
    expect(screen.getByTestId("kappa")).toHaveTextContent(/advisory/);
    expect(screen.getByTestId("tab-heldout")).toHaveTextContent(/pending/);
    expect(screen.getByTestId("sweep-chart")).toBeInTheDocument();
    // image-level recall never appears without its caveat
    expect(screen.getByTestId("image-recall-caption")).toHaveTextContent(/wherever it is/);
    expect(screen.getByTestId("image-recall-caption")).toHaveTextContent(/21%/);
  });

  it("puts the held-out report first once the API serves it", async () => {
    const heldout = { ...evalReports[0], split: "heldout" };
    open("/eval", { "/api/eval": () => ({ body: [evalReports[0], heldout] }) });
    expect(await screen.findByTestId("tab-heldout")).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(screen.queryByTestId("heldout-pending")).toBeNull());
  });
});

/** The real stored results (not the made-up fixtures) go through the same screens. */
describe("real stored data", () => {
  const read = (path: string) => JSON.parse(readFileSync(resolve(process.cwd(), "..", path), "utf8"));

  it("renders docs/evidence/eval_dev.json as measured", async () => {
    const dev = read("docs/evidence/eval_dev.json");
    open("/eval", { "/api/eval": () => ({ body: [{ sample_note: null, severity_kappa: null, ...dev }] }) });
    const damage = dev.classes.find((c: { label: string }) => c.label === "damage");
    expect((await screen.findAllByText(`${(damage.recall * 100).toFixed(1)}%`)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(`${(damage.precision * 100).toFixed(1)}%`).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/95% interval 18%–26%/).length).toBeGreaterThan(0);
  });

  it("renders docs/evidence/eval_heldout.json with its own false-alarm rate, held-out tab first", async () => {
    const dev = read("docs/evidence/eval_dev.json");
    const held = read("docs/evidence/eval_heldout.json");
    open("/eval", { "/api/eval": () => ({ body: [dev, held] }) });
    expect(await screen.findByTestId("tab-heldout")).toHaveAttribute("aria-pressed", "true");
    const damage = held.classes.find((c: { label: string }) => c.label === "damage");
    expect((await screen.findAllByText(`${(damage.recall * 100).toFixed(1)}%`)).length).toBeGreaterThan(0);
    expect(screen.getByTestId("image-recall-caption")).toHaveTextContent(/300 held-out tiles[\s\S]*24%/);
    expect(screen.queryByTestId("heldout-pending")).toBeNull();
  });

  it("renders a replay inspection (empty blade outline, unknown position) with its photo and masks", async () => {
    const real = read("replay/inspections/T01-2018.json");
    open("/inspections/T01-2018", { "/api/inspections/T01-2018": () => ({ body: real }) });
    const photo = await screen.findByTestId("photo-viewer");
    await act(async () => {});
    fireEvent.load(within(photo).getByRole("img", { name: /Drone photo/ }));
    expect((await within(photo).findAllByTestId("mask")).length).toBeGreaterThan(0);
    expect(screen.getByTestId("toggle-blade")).toBeDisabled();
    await userEvent.setup().click(within(screen.getAllByTestId("defect-card")[0]).getAllByRole("button")[0]);
    expect(screen.getAllByText(/not determined \(no blade mask\)/).length).toBeGreaterThan(0);
  });
});
