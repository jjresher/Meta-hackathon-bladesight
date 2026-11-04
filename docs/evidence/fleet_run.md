# Fleet run: farm processing and the agent

Synthetic farm: 12 turbines x 2 inspections (2017, 2018) of 4 real DTU dev tiles
each, an invented grouping (`DATA.md`). Pipeline per tile: Muse Spark box proposals
-> SAM 3.1 masks -> measurement -> Muse Spark severity (`assess/v1`, rubric `v1`)
-> second look and rule checks (`verify/v1`). At most 4 detections per tile are
graded. Costs are documented prices times
real usage (not invoice-checked).

## Farm processing

- Inspections: 24; images: 96; defects detected and kept: 96; graded and verified: 96; left ungraded after an error: 0; images with no detection at all: 54.
- Verdicts over 96 graded defects: `ok` 33 (34%), `needs_review` 50 (52%), `reinspect` 13 (14%).
- Severity of all graded defects: {1: 60, 2: 10, 3: 26}; of the verified (`ok`) ones: {1: 17, 3: 16}. No defect was graded above 3.
- Cost of the live runs that produced the store: 1.6300 USD.

Verification thresholds (`verify.THRESHOLDS`: combined confidence 0.30 for `ok`, 0.15 for
`reinspect`) were set on a first 17-defect sample of these dev tiles before this run was
completed (`docs/decision_ledger.md`); the shares above therefore depend on that choice.

## Agent run

- Run `run-final`: status `completed`, model `muse-spark-1.3`, 60 steps (23 tool calls, 13 notes), cost 0.0645 USD; the run replays with no model call when the response cache (`.cache/`, not committed) is present, and the demo reads the stored results.
- Work orders: 9 (3 repair, 0 monitor, 6 re-inspection); every repair order cites only defects with an `ok` verdict (enforced by the tool, tested).
- Report: `report-run-final`.

Trace and orders: `replay/runs/`, `replay/work_orders.json`, `replay/reports/`.

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
| T07-2018 | 5 | 1 | 2 | 1 |
| T08-2017 | 9 | 3 | 3 | 0 |
| T08-2018 | 4 | 1 | 1 | 1 |
| T09-2017 | 4 | 1 | 2 | 0 |
| T09-2018 | 3 | 1 | 1 | 0 |
| T10-2017 | 2 | - | 1 | 1 |
| T10-2018 | 6 | 3 | 3 | 2 |
| T11-2017 | 4 | 3 | 2 | 1 |
| T11-2018 | 0 | - | 0 | 0 |
| T12-2017 | 8 | 3 | 4 | 1 |
| T12-2018 | 4 | 1 | 2 | 1 |
