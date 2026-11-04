/**
 * Typed client for the BladeSight API (docs/api.md). Same-origin by default (the API serves the
 * built UI); `VITE_API_BASE` points a dev build at another origin. There is no offline or
 * fixture fallback here: the fixtures in `src/fixtures/` are made-up values and only tests
 * import them.
 */
import type {
  AgentRun,
  EvalReport,
  Fleet,
  Health,
  Inspection,
  Report,
  WorkOrder,
} from "../types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

/** The schema version this UI was generated against (see `src/fixtures/schema.json`). */
export const SCHEMA_VERSION = "1.0";

export class ApiError extends Error {
  readonly status: number | null;
  readonly path: string;

  constructor(message: string, status: number | null, path: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.path = path;
  }

  get notFound(): boolean {
    return this.status === 404;
  }
}

async function get<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError("The API is not reachable.", null, path);
  }
  if (!response.ok) {
    let detail = response.statusText || `HTTP ${response.status}`;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // keep the status text
    }
    throw new ApiError(detail, response.status, path);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("The API answered with something that is not JSON.", response.status, path);
  }
}

export const api = {
  health: () => get<Health>("/api/health"),
  fleet: () => get<Fleet>("/api/fleet"),
  inspection: (id: string) => get<Inspection>(`/api/inspections/${encodeURIComponent(id)}`),
  workOrders: () => get<WorkOrder[]>("/api/work-orders"),
  latestReport: () => get<Report>("/api/reports/latest"),
  runs: () => get<AgentRun[]>("/api/runs"),
  run: (id: string) => get<AgentRun>(`/api/runs/${encodeURIComponent(id)}`),
  evaluations: () => get<EvalReport[]>("/api/eval"),
};

/** Absolute-or-relative URL of a tile the API streams (`InspectionImage.image_url`). */
export function imageUrl(path: string): string {
  return `${BASE}${path}`;
}
