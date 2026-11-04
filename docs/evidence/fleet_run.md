# Fleet run: farm processing and the agent

Synthetic farm: 12 turbines x 2 inspections (2017, 2018) of 4 real DTU dev tiles
each, an invented grouping (`DATA.md`). Pipeline per tile: Muse Spark box proposals
-> SAM 3.1 masks -> measurement -> Muse Spark severity (`assess/v1`, rubric `v1`)
-> second look and rule checks (`verify/v1`). At most 4 detections per tile are
graded. Costs are documented prices times
real usage (not invoice-checked).

## Farm processing

- Inspections: 24; images: 96; defects detected and kept: 98; graded and verified: 98; left ungraded after an error: 0; images with no detection at all: 55.
- Verdicts over 98 graded defects: `ok` 35 (36%), `needs_review` 50 (51%), `reinspect` 13 (13%).
- Severity of all graded defects: {1: 61, 2: 12, 3: 25}; of the verified (`ok`) ones: {1: 18, 3: 17}. No defect was graded above 3.
- Cost of the live runs that produced the store: 1.7780 USD.

Verification thresholds (`verify.THRESHOLDS`: combined confidence 0.30 for `ok`, 0.15 for
`reinspect`) were set on a first 17-defect sample of these dev tiles before this run was
completed (`docs/decision_ledger.md`); the shares above therefore depend on that choice.

## Agent run

- Run `run-final`: status `completed`, model `muse-spark-1.3`, 59 steps (25 tool calls, 8 notes), cost 0.0683 USD; the run replays with no model call when the response cache (`.cache/`, not committed) is present, and the demo reads the stored results.
- Work orders: 11 (5 repair, 0 monitor, 6 re-inspection); every repair order cites only defects with an `ok` verdict (enforced by the tool, tested).
- Report: `report-run-final`.

Trace and orders: `replay/runs/`, `replay/work_orders.json`, `replay/reports/`.

## Agent autonomy

Counted from the stored traces (`fleet/compare.py`). A rejection is a tool call the
tool refused, with the rule it enforced (`fleet/rules.py`, stable ids); the agent
reads the refusal and decides what to do next. The rationale is the model's own text
in the same turn before the call (null when it wrote none); nothing is filled in.
Both runs recorded these fields as they ran (`fleet backfill` changes nothing).
The Muse Spark Open run grades its own re-graded farm (`replay/open-weights/`),
so the two agents saw different verdicts: compare behaviour, not order lists.

| | `run-final` (muse-spark-1.3) | `run-open-weights` (meta-models/muse-spark-open) |
|---|---|---|
| Status | `completed` | `completed` |
| Steps in the trace | 59 | 47 |
| Model turns | 16 | 7 |
| Tool calls | 25 | 23 |
| Tool calls by tool | `compare_inspections` 6, `create_work_order` 5, `get_inspection` 6, `list_turbines` 1, `request_reinspection` 6, `write_report` 1 | `compare_inspections` 6, `create_work_order` 3, `get_inspection` 6, `list_turbines` 1, `request_reinspection` 6, `write_report` 1 |
| Tool calls with the model's own text before them | 18 | 0 |
| Calls rejected by a tool rule | 0 | 0 |
| Rejections by rule | none | none |
| Work orders | 11 | 9 |
| Work orders by kind | `reinspect` 6, `repair` 5 | `monitor` 1, `reinspect` 6, `repair` 2 |
| Agent cost (USD) | 0.0683 | 0.0569 |

## Per inspection

| Inspection | Defects | Max verified severity | Needs review | Reinspect |
|---|---|---|---|---|
| T01-2017 | 4 | 3 | 0 | 2 |
| T01-2018 | 8 | 3 | 5 | 1 |
| T02-2017 | 5 | 1 | 4 | 0 |
| T02-2018 | 5 | 3 | 4 | 0 |
| T03-2017 | 3 | - | 3 | 0 |
| T03-2018 | 3 | 1 | 1 | 0 |
| T04-2017 | 0 | - | 0 | 0 |
| T04-2018 | 1 | - | 1 | 0 |
| T05-2017 | 1 | - | 1 | 0 |
| T05-2018 | 8 | 1 | 4 | 2 |
| T06-2017 | 2 | - | 2 | 0 |
| T06-2018 | 3 | 1 | 2 | 0 |
| T07-2017 | 4 | 3 | 2 | 0 |
| T07-2018 | 4 | 3 | 1 | 0 |
| T08-2017 | 9 | 3 | 4 | 0 |
| T08-2018 | 4 | 1 | 1 | 0 |
| T09-2017 | 4 | 1 | 2 | 0 |
| T09-2018 | 3 | 1 | 1 | 0 |
| T10-2017 | 4 | - | 2 | 2 |
| T10-2018 | 6 | 3 | 3 | 2 |
| T11-2017 | 5 | 3 | 1 | 3 |
| T11-2018 | 0 | - | 0 | 0 |
| T12-2017 | 8 | 3 | 4 | 1 |
| T12-2018 | 4 | 3 | 2 | 0 |
