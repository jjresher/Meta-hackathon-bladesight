import { expect, test } from "@playwright/test";

/**
 * Smoke test (issue #13 DoD): open the fleet, open one inspection and open the
 * work orders screen, asserting no console errors along the way.
 */
test("open fleet, one inspection and work orders with no console errors", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(err.message));

  // Fleet
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Fleet" })).toBeVisible();
  await expect(page.getByTestId("fleet-row").first()).toBeVisible();

  // Open one inspection via the first fleet row link.
  await page.getByTestId("fleet-row").first().getByRole("link").first().click();
  await expect(page.getByTestId("defect-list")).toBeVisible();

  // Work orders
  await page.getByRole("link", { name: "Work orders" }).click();
  await expect(page.getByTestId("work-order").first()).toBeVisible();

  expect(consoleErrors, `console errors: ${consoleErrors.join("\n")}`).toEqual([]);
});
