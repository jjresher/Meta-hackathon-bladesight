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
  ReplaySet,
  Report,
  WorkOrder,
} from "../types";

/** A stored replay the data endpoints can serve (`?provider=`, docs/api.md). */
export type RunProvider = ReplaySet["provider"];

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

/** `?provider=` when a run is chosen; without it the API serves its default replay. */
const q = (provider?: RunProvider): string => (provider ? `?provider=${provider}` : "");

export const api = {
  health: () => get<Health>("/api/health"),
  replays: () => get<ReplaySet[]>("/api/replays"),
  fleet: (provider?: RunProvider) => get<Fleet>(`/api/fleet${q(provider)}`),
  inspection: (id: string, provider?: RunProvider) =>
    get<Inspection>(`/api/inspections/${encodeURIComponent(id)}${q(provider)}`),
  workOrders: (provider?: RunProvider) => get<WorkOrder[]>(`/api/work-orders${q(provider)}`),
  latestReport: (provider?: RunProvider) => get<Report>(`/api/reports/latest${q(provider)}`),
  runs: (provider?: RunProvider) => get<AgentRun[]>(`/api/runs${q(provider)}`),
  run: (id: string, provider?: RunProvider) => get<AgentRun>(`/api/runs/${encodeURIComponent(id)}${q(provider)}`),
  evaluations: () => get<EvalReport[]>("/api/eval"),
};

/** Absolute-or-relative URL of a tile the API streams (`InspectionImage.image_url`). */
export function imageUrl(path: string): string {
  return `${BASE}${path}`;
}
