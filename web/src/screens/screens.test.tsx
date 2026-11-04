import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import evalReports from "../fixtures/eval.json";
import { stubApi, type Overrides } from "../test/mockApi";

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

  it("renders a replay inspection (empty blade outline, unknown position) with its photo and masks", async () => {
    const real = read("replay/inspections/T01-2018.json");
    open("/inspections/T01-2018", { "/api/inspections/T01-2018": () => ({ body: real }) });
    const photo = await screen.findByTestId("photo-viewer");
    fireEvent.load(within(photo).getByRole("img", { name: /Drone photo/ }));
    expect((await within(photo).findAllByTestId("mask")).length).toBeGreaterThan(0);
    expect(screen.getByTestId("toggle-blade")).toBeDisabled();
    expect(screen.getAllByText(/not determined \(no blade mask\)/).length).toBeGreaterThan(0);
  });
});
