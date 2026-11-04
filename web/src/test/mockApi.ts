import { vi } from "vitest";

import evalReports from "../fixtures/eval.json";
import fleet from "../fixtures/fleet.json";
import health from "../fixtures/health.json";
import inspection from "../fixtures/inspection_T03-2018.json";
import report from "../fixtures/report_latest.json";
import run from "../fixtures/run_run-example-001.json";
import runs from "../fixtures/runs.json";
import workOrders from "../fixtures/work_orders.json";

type Handler = () => { status?: number; body: unknown };
export type Overrides = Record<string, Handler>;

const routes: Record<string, Handler> = {
  "/api/health": () => ({ body: health }),
  "/api/fleet": () => ({ body: fleet }),
  "/api/inspections/T03-2018": () => ({ body: inspection }),
  "/api/work-orders": () => ({ body: workOrders }),
  "/api/reports/latest": () => ({ body: report }),
  "/api/runs": () => ({ body: runs }),
  "/api/runs/run-example-001": () => ({ body: run }),
  "/api/eval": () => ({ body: evalReports }),
};

/**
 * Stands in for the API with the made-up fixtures of `src/fixtures/` (tests only: the production
 * bundle never imports them). Unknown paths answer 404 with FastAPI's `{"detail": ...}` shape.
 */
export function stubApi(overrides: Overrides = {}) {
  const table = { ...routes, ...overrides };
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), "http://test").pathname;
    const handler = table[path];
    const { status = 200, body } = handler ? handler() : { status: 404, body: { detail: "not found" } };
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
