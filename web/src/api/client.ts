/**
 * Typed API client for the BladeSight UI (issue #13).
 *
 * The client has a mock mode that reads from the hand-written placeholders in
 * `web/src/mocks/`. When the backend agent commits generated fixtures, switch
 * the data source with a SINGLE line: replace the `mockDataset` import below
 * with a loader for `web/src/fixtures/*.json` (see DATA_SOURCE comment).
 */

import { mockDataset } from "../mocks/fleet";
import type {
  AgentStep,
  EvalReport,
  FleetDataset,
  Inspection,
  Report,
  Turbine,
  WorkOrder,
} from "../types";

// ============================================================================
// ONE-LINE DATA SOURCE SWITCH
// ----------------------------------------------------------------------------
// Today the client serves the mock placeholders. To switch to the backend
// agent's generated fixtures, change ONLY this line to, e.g.:
//     import DATA_SOURCE from "../fixtures/dataset.json" with { type: "json" };
// (the fixtures JSON conforms to the `FleetDataset` type in ../types.ts).
const DATA_SOURCE: FleetDataset = mockDataset;
// ============================================================================

export class NotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NotFoundError";
  }
}

/** A tiny typed client over a `FleetDataset`. */
export class ApiClient {
  private readonly data: FleetDataset;

  constructor(data: FleetDataset = DATA_SOURCE) {
    this.data = data;
  }

  /** Farm-level provenance label for honest UI copy. */
  getFarmLabel(): string {
    return this.data.farmLabel;
  }

  /** Turbines ranked by priority (already sorted by the data source). */
  async getFleet(): Promise<Turbine[]> {
    return [...this.data.turbines].sort((a, b) => a.rank - b.rank);
  }

  /** One inspection by id, or throws NotFoundError. */
  async getInspection(id: string): Promise<Inspection> {
    const found = this.data.inspections.find((i) => i.id === id);
    if (!found) {
      throw new NotFoundError(`Inspection not found: ${id}`);
    }
    return found;
  }

  /** All inspections for one turbine, newest year first. */
  async getInspectionsForTurbine(turbineId: string): Promise<Inspection[]> {
    return this.data.inspections
      .filter((i) => i.turbineId === turbineId)
      .sort((a, b) => b.year - a.year);
  }

  /** The written fleet report with its work orders. */
  async getReport(): Promise<Report> {
    return this.data.report;
  }

  /** Work orders, in priority order (as stored in the report). */
  async getWorkOrders(): Promise<WorkOrder[]> {
    return this.data.report.workOrders;
  }

  /** The agent trace for the latest run, in step order. */
  async getAgentTrace(): Promise<AgentStep[]> {
    return [...this.data.agentTrace].sort((a, b) => a.index - b.index);
  }

  /** The evaluation report (metrics, threshold curve, limitations). */
  async getEvalReport(): Promise<EvalReport> {
    return this.data.evalReport;
  }
}

/** Shared default client used by the screens. */
export const api = new ApiClient();
