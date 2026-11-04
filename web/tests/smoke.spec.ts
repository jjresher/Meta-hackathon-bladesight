import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { deflateSync } from "node:zlib";

import { expect, test, type Page } from "@playwright/test";

const live = Boolean(process.env.SMOKE_BASE_URL);
const shots = process.env.SMOKE_SHOTS; // directory for screenshots, optional

const fixture = (name: string) => readFileSync(resolve(process.cwd(), "src/fixtures", name), "utf8");

/** A flat 586x371 PNG: the fixtures reference tiles that are never committed. */
function flatPng(width = 586, height = 371): Buffer {
  const crc = (buf: Buffer) => {
    let c = ~0;
    for (const byte of buf) {
      c ^= byte;
      for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
    }
    return ~c >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type), data]);
    const out = Buffer.alloc(body.length + 8);
    out.writeUInt32BE(data.length, 0);
    body.copy(out, 4);
    out.writeUInt32BE(crc(body), body.length + 4);
    return out;
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr.set([8, 2, 0, 0, 0], 8);
  const row = Buffer.concat([Buffer.from([0]), Buffer.alloc(width * 3, 0x70)]);
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

async function mockApi(page: Page) {
  const json = (body: string) => ({ status: 200, contentType: "application/json", body });
  await page.route("**/api/health", (r) => r.fulfill(json(fixture("health.json"))));
  await page.route("**/api/fleet", (r) => r.fulfill(json(fixture("fleet.json"))));
  await page.route("**/api/inspections/*", (r) => r.fulfill(json(fixture("inspection_T03-2018.json"))));
  await page.route("**/api/work-orders", (r) => r.fulfill(json(fixture("work_orders.json"))));
  await page.route("**/api/reports/latest", (r) => r.fulfill(json(fixture("report_latest.json"))));
  await page.route("**/api/runs", (r) => r.fulfill(json(fixture("runs.json"))));
  await page.route("**/api/eval", (r) => r.fulfill(json(fixture("eval.json"))));
  const png = flatPng();
  await page.route("**/images/*.png", (r) => r.fulfill({ status: 200, contentType: "image/png", body: png }));
}

test("fleet -> inspection -> work order, with no console or network errors", async ({ page }, info) => {
  const problems: string[] = [];
  page.on("console", (m) => m.type() === "error" && problems.push(`console: ${m.text()}`));
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    const url = r.url();
    if ((url.includes("/api/") || url.includes("/images/")) && r.status() >= 400) {
      problems.push(`${r.status()} ${url}`);
    }
  });
  if (!live) await mockApi(page);
  const shot = async (name: string) => {
    if (shots) await page.screenshot({ path: `${shots}/${name}-${info.project.name}.png` });
  };

  // Fleet
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("turbines");
  await expect(page.getByTestId("fleet-note")).toContainText(/synthetic/i);
  const rows = page.getByTestId("fleet-row");
  await expect(rows.first()).toBeVisible();
  await shot("1-fleet");

  // Inspection: the real photo, with masks and boxes on top
  await rows.first().getByRole("link").first().click();
  await expect(page).toHaveURL(/\/inspections\//);
  const photo = page.getByTestId("photo-viewer");
  const img = photo.locator("img.photo__img");
  await expect(img).toHaveClass(/is-ready/, { timeout: 30_000 });
  expect(await img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0);
  await expect(photo.getByTestId("mask").first()).toBeVisible();
  await expect(photo.getByTestId("box").first()).toBeVisible();
  await shot("2-inspection");

  // Masks and boxes toggle separately
  await page.getByTestId("toggle-masks").uncheck({ force: true });
  await expect(photo.getByTestId("mask")).toHaveCount(0);
  await expect(photo.getByTestId("box").first()).toBeVisible();
  await page.getByTestId("toggle-masks").check({ force: true });
  await expect(photo.getByTestId("mask").first()).toBeVisible();

  // Work order
  await page.getByTestId("wo-link").first().click();
  await expect(page).toHaveURL(/\/work-orders#/);
  await expect(page.getByTestId("work-order").first()).toBeVisible();
  await shot("3-work-orders");

  // The other two screens
  await page.getByRole("link", { name: "Agent trace" }).click();
  await expect(page.getByTestId("trace-step").first()).toBeVisible();
  await shot("4-trace");
  await page.getByRole("link", { name: "Evaluation" }).click();
  await expect(page.getByTestId("kappa-value")).toHaveText("0.12");
  await shot("5-eval");

  expect(problems, problems.join("\n")).toEqual([]);
});

test("a photo that fails to load shows a clear error and no overlay", async ({ page }) => {
  test.skip(live, "needs a controlled failure; covered against the mocked API");
  await mockApi(page);
  await page.route("**/images/*.png", (r) => r.fulfill({ status: 404, body: "no" }));
  await page.goto("/inspections/T03-2018");
  await expect(page.getByTestId("photo-error")).toContainText("Photo unavailable");
  await expect(page.getByTestId("mask")).toHaveCount(0);
  await expect(page.getByTestId("defect-card").first()).toBeVisible();
});
