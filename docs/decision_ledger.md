# Decision ledger

Small decisions, data and model findings, spends and scope cuts that do not merit a longer
document. One row each, newest first. See skill `write-decision`.

| Date | Area | Decision / finding | Evidence | Issue |
|---|---|---|---|---|
| 2026-10-29 | data | Use the YOLO-annotated DTU derivative (classes damage, dirt; CC BY-NC 4.0) and never commit data; download by script. Original Mendeley licence not stated on its page, to confirm in #4. | datasetninja.com/yolo-annotated-wind-turbine-surface-damage | #4 |
| 2026-10-29 | meta | All model calls go through one client with retries, disk cache and a spend cap; public demo runs in replay mode. Reason: a participant measured ~25% intermittent Model API failures on Oct 29. | Discord #office-hours, "Intermittent Meta Model API failure" | #2 |
| 2026-10-29 | scope | Project chosen: zero-shot blade inspection agent (Push the Frontier). Rejected: tender-response agent (no domain expert available), wildfire detection (crowded, heavy geospatial pipeline). | docs/plan/implementation_plan.md | - |
