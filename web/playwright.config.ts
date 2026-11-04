import { defineConfig, devices } from "@playwright/test";

// Smoke test (issue #13 DoD). Two modes:
//  - default: builds the UI, serves it with `vite preview` and answers /api and /images from the
//    made-up fixtures (CI has no API and no photos);
//  - SMOKE_BASE_URL=<url>: runs the same flow against a real deployment (local API serving the
//    build, or the public Render URL) with real data and real photos.
const baseURL = process.env.SMOKE_BASE_URL ?? "http://127.0.0.1:4173";

export default defineConfig({
  testDir: "./tests",
  reporter: "list",
  retries: process.env.SMOKE_BASE_URL ? 1 : 0,
  timeout: process.env.SMOKE_BASE_URL ? 120_000 : 30_000,
  use: { baseURL, trace: "retain-on-failure" },
  webServer: process.env.SMOKE_BASE_URL
    ? undefined
    : {
        command: "npm run build && npm run preview -- --port 4173 --strictPort",
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
  projects: [
    { name: "desktop-1280", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
    { name: "mobile-390", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, hasTouch: true } },
  ],
});
