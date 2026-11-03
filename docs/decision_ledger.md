# Decision ledger

Small decisions, data and model findings, spends and scope cuts that do not merit a longer
document. One row each, newest first. See skill `write-decision`.

| Date | Area | Decision / finding | Evidence | Issue |
|---|---|---|---|---|
| 2026-11-03 | api | API contract in one module (`bladesight.contracts`, pydantic, `extra="forbid"`, `SCHEMA_VERSION` 1.0); JSON Schema and one made-up example response per endpoint are generated from code into `web/src/fixtures/` (`poe contract`) and a test fails on drift, so the web UI (built in parallel on `i13-web-ui`) codes against the same shapes. Endpoints under `/api`, tiles at `/images/{tile_id}.png`. Work orders require non-empty `defect_ids` and `evidence` in the schema (the evidence rule of #11). Rejected: hand-written TypeScript types (drift) and OpenAPI-only export (no example payloads). | `docs/api.md`, `tests/test_contracts.py` | #12 |
| 2026-10-29 | data | Use the YOLO-annotated DTU derivative (classes damage, dirt; CC BY-NC 4.0) and never commit data; download by script. Original Mendeley licence not stated on its page, to confirm in #4. | datasetninja.com/yolo-annotated-wind-turbine-surface-damage | #4 |
| 2026-10-29 | meta | All model calls go through one client with retries, disk cache and a spend cap; public demo runs in replay mode. Reason: a participant measured ~25% intermittent Model API failures on Oct 29. | Discord #office-hours, "Intermittent Meta Model API failure" | #2 |
| 2026-10-29 | scope | Project chosen: zero-shot blade inspection agent (Push the Frontier). Rejected: tender-response agent (no domain expert available), wildfire detection (crowded, heavy geospatial pipeline). | docs/plan/implementation_plan.md | - |
