# Definition-of-Done audit

Audited on 2026-11-03, about 23:40 COT (UTC-5), against `main` at commit
[`7c92e77`](https://github.com/jjresher/Meta-hackathon-bladesight/commit/7c92e77e870c2335ea395adc23edd4de53d008e1).
Scope: every checkbox of the closed issues #1-#13 and #16 (the plan's per-issue DoD in
`docs/plan/implementation_plan.md` section 7, which the issue bodies copy, plus the global DoD in
`AGENTS.md`). Every evidence link below points to that commit (line numbers as of `7c92e77`; this branch removes one ledger row, so ledger lines on `main` shift by one). 0 USD spent: only stub tests,
`git`, `gh` and local file checks.

## Summary

| | Count |
|---|---|
| Checkboxes audited | 54 (14 issues) |
| Met | 48 |
| Partial | 3 (#3 gallery, #5 "recorded" SAM responses, #7 review by hand) |
| Not met | 3 (#3 Friday deadline, #5 overlays in the PR, #13 screenshots in the PR) |
| Issues reopened | #5, #13 (each has an image attachment missing that the human can add from local files) |
| Gaps routed to another agent's area | none: no unmet item needs code in `meta/assess/verify/fleet/api`, `detect/eval` or `web/` |

Checks run for this audit:

- `uv run poe check` in the worktree and in a fresh clone of `main`
  (`git clone` + `uv sync` + `poe check`): ruff, format, pyright, **365 passed**, exit 0.
- Per-issue test files (`pytest -o addopts="" tests/<file>.py`): retry 7, cache 12, spend 12,
  config 21, data 9, detect pipeline 7, measure 13, assess 13, verify 21, eval metrics 11, matching 4,
  gold 11, agreement 7, fleet 14, api 12, heldout 22, forbidden paths 3; all passed.
- Pre-commit in that fresh clone after `uv run poe hooks`: committing `data/x.jpg` failed
  (`check-forbidden-paths`); committing a fake AWS key failed (`gitleaks`); nothing was committed.
- `sha256sum eval/heldout_manifest.sha256` = `890b3e55...5338`, equal to `manifest_sha256` in
  `eval/split_summary.json` and to the value both rebuilds in PR #26 printed.
- `git ls-files`: no image, archive, weight or `data/` path is tracked.
- Numbers recomputed: README results table vs `eval_dev.json`, `eval_heldout.json` (precision,
  recall, intervals, image-level recall, false-alarm rate, dirt): equal after rounding. Severity
  kappa recomputed from `eval/gold/severity.csv` and `eval/gold/model_grades.csv`: quadratic weighted
  0.121, exact 25%, within one 47.5%, model severity 1 on 29 of 40 (doc: 0.12, 25%, 48%, 29).
  Verdicts counted in `replay/inspections/*.json`: 33 ok / 50 needs_review / 13 reinspect
  (`fleet_run.md`: the same). `replay/runs/run-final.json`: 60 steps, completed;
  `replay/work_orders.json`: 9 orders, 3 repair and 6 reinspect.
- CI: every merged PR from #24 on has a green `python` check (and `web` from #44 on); #42 has no
  check because it was merged into the `i13-web-ui-cc` branch, not into `main`; `main` at `7c92e77` is
  green ([run 41770844796](https://github.com/jjresher/Meta-hackathon-bladesight/actions/runs/41770844796)).

How the global DoD row is judged: the sprint rules (ledger, 2026-11-03 "process" row) replaced the
per-PR handoff and human OK with `docs/submission/sprint_log.md`; so "Global DoD met" here means CI
green, tests on the stub, nothing forbidden committed, evidence and ledger/limitations lines present,
and a written auditor verdict of MERGE (or MERGE AFTER FIXES with the fixes applied) in the PR body,
a PR comment or the sprint log. Most PR bodies leave the template's "CI green" box unticked; the
PR checks themselves are the evidence used here.

Other findings (not DoD checkboxes):

- PR #47 (`i16-heldout-results`, open) is **superseded** by #46 and #49: same run, same metrics and
  intervals, but its evidence still carries the uncorrected cost (3.8623 instead of 8.0727 USD), and
  it now conflicts with `main`. The only content it has that `main` lacks is the "How this compares
  with the dev run" paragraph in `eval_heldout.md` (unweighted held-out precision 216 / (216 + 529) =
  0.29). It should be closed by the human, optionally after moving that paragraph over.
- Fixed on this branch: the duplicate spike row in `docs/decision_ledger.md` (the older copy with the
  9-13% recall range), a pointer from the first verification row to the later thresholds
  (0.30 / 0.15), the stale duplicate open-weights line in `docs/limitations.md`, and the #7
  limitation that still said "no human agreement yet".

## #1 Bootstrap repo and agent harness (closed, boxes ticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| fresh clone -> `uv sync && uv run poe check` passes | met | fresh clone of `7c92e77`: 365 passed, exit 0 | re-run for this audit |
| CI green on main | met | [run 41770844796](https://github.com/jjresher/Meta-hackathon-bladesight/actions/runs/41770844796) | |
| committing a `.jpg` under `data/` or a fake key is blocked by pre-commit | met | fresh clone: `check-forbidden-paths` and `gitleaks` both failed the commit; [tests/test_forbidden_paths.py](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_forbidden_paths.py#L13) | re-run for this audit |
| README states "built during the Meta Global AI Developer Hackathon, Oct 27 - Nov 4 2026" | met | [README.md L6-7](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/README.md#L6-L7) | |
| Global DoD met and auditor verdict MERGE | met | [PR #22](https://github.com/jjresher/Meta-hackathon-bladesight/pull/22) body (auditor MERGE); `gh api .../rules/branches/main`: deletion, non_fast_forward, pull_request, required_status_checks | |

## #2 Meta API client (closed, boxes ticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| unit tests for retry, cache hit/miss, cap refusal (stub) | met | [test_meta_retry.py](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_meta_retry.py#L28), [test_meta_cache.py L28](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_meta_cache.py#L28), [test_meta_spend.py L43](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_meta_spend.py#L43) | 7 + 12 + 12 passed |
| one real call each to Muse Spark and SAM 3.1 logged with cost | met | [meta-api-step1.md L20-21](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/meta-api-step1.md#L20-L21) | request ids and USD per call |
| key read from `.env` only, never printed | met | [test_meta_config.py L17-30](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_meta_config.py#L17-L30) | `SecretStr`, `set`/`missing` only |
| Global DoD met and auditor MERGE | met | [PR #24](https://github.com/jjresher/Meta-hackathon-bladesight/pull/24) "Audit" section; CI green | |

## #3 Spike: SAM 3.1 and Muse Spark (closed, boxes were unticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| findings and chosen prompt list in the ledger, with a sample gallery in `docs/evidence/spike.md` | partial | [ledger L22](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/decision_ledger.md#L22), [spike.md](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/spike.md#L9) | findings and prompts (`surface damage`, `crack`; dropped `leading edge erosion`, `wind turbine blade`) are there; the "gallery" is a per-tile table of ids, no images (rule 2 forbids committing them) |
| go/no-go decision written by Fri 12:00 | **not met** | commit `3dc2006`, 2026-11-03 17:53 COT | written four days after Fri Oct 30 12:00; cannot be fixed now |
| cost of the spike logged | met | [spike.md L12-21](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/spike.md#L12-L21) | 0.3956 USD, 146 live calls |
| Global DoD met and auditor MERGE | met | [PR #27](https://github.com/jjresher/Meta-hackathon-bladesight/pull/27) "Audit": MERGE; CI green | |

## #4 Dataset download, split and seal (closed, boxes were unticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| `uv run poe data` reproduces the split and the manifest hash | met | [PR #26](https://github.com/jjresher/Meta-hackathon-bladesight/pull/26) (two builds and the auditor's third gave manifest `890b3e55...5338`); [`__main__.py` L59-64](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/src/bladesight/data/__main__.py#L59-L64) fails on any mismatch; [test_data.py L85](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_data.py#L85), [test_heldout.py L281](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_heldout.py#L281) | not re-run here: a rebuild rewrites the shared `data/` that other agents are using; manifest file hash checked instead |
| no data in git | met | `git ls-files` clean; pre-commit blocked `data/x.jpg` (see #1) | |
| licence and citation in README and `DATA.md` | met | [README.md L114-116](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/README.md#L114-L116), [DATA.md L12-30](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/DATA.md#L12-L30) | the issue text has a stray "### M1 Vertical slice" from the plan |
| Global DoD met and auditor MERGE | met | PR #26 "Audit": MERGE; CI green | |

## #5 Defect and blade detection (closed, **reopened**)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| tests on recorded SAM responses (stub) | partial | [test_detect_pipeline.py](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_detect_pipeline.py#L61) (7 stub tests), [test_meta_real_shapes.py L138-196](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_meta_real_shapes.py#L138-L196) | pipeline tests use synthetic stub masks; SAM wire tests use replies reconstructed from the real ones (raw replies were not kept), not recorded payloads |
| overlay images for 5 dev tiles in the PR | **not met** | [PR #28](https://github.com/jjresher/Meta-hackathon-bladesight/pull/28) has none; [detect.md L8-9](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/detect.md#L8-L9) | the 5 PNGs exist locally in `bladesight-wt/i5/outputs/detect/`; attaching them to a PR comment is the human's call (AGENTS.md rule 2 covers commits, not comment attachments; they are derived from CC BY-NC tiles: keep the attribution) |
| runtime and cost per image recorded | met | [detect.md L11-27](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/detect.md#L11-L27) | about 0.014 USD per tile; 1.3-1.9 s with one live call (fully live runtime not measured) |
| Global DoD met and auditor MERGE | met | PR #28 "Audit": MERGE AFTER FIXES, fix applied; CI green | |

## #6 Measurement and localization (closed, boxes were unticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| unit tests with synthetic masks (known answers) | met | [test_measure.py](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_measure.py#L28) | 13 passed |
| limits written in `docs/limitations.md` | met | [limitations.md L7, L35-37, L42](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/limitations.md#L35-L42) | |
| Global DoD met and auditor MERGE | met | [PR #29](https://github.com/jjresher/Meta-hackathon-bladesight/pull/29) "Audit": MERGE; CI green | |

## #7 Severity assessment with Muse Spark (closed, boxes were unticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| invalid output handled (test with stub) | met | [test_assess.py L79-103](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_assess.py#L79-L103) | retry once, then `AssessError` |
| 10 dev examples reviewed by hand in the PR | partial | [assess.md L12-15](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/assess.md#L12-L15) | 10 gradings reviewed by the agent, not by a person; superseded by the 40 human labels of #10 (kappa 0.12), so not reopened |
| prompt versioned (`assess/prompts/v1.md`) | met | [assess/prompts/v1.md](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/src/bladesight/assess/prompts/v1.md) | |
| Global DoD met and auditor MERGE | met | [PR #30](https://github.com/jjresher/Meta-hackathon-bladesight/pull/30) "Audit": MERGE; CI green | |

## #8 Verification and abstention (closed, boxes ticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| tests for each branch | met | [test_verify.py L59-208](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_verify.py#L59-L208) | ok, needs_review, reinspect, abstain; 21 passed |
| the share of `needs_review` on dev reported | met | [fleet_run.md L13](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/fleet_run.md#L13) | 33 / 50 / 13 of 96, recounted from `replay/` |
| thresholds recorded in the ledger | met | [ledger L13, L17](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/decision_ledger.md#L13-L17); [verify.py L24-32](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/src/bladesight/verify/verify.py#L24-L32) | code has 0.30 / 0.15, the #11 row records the change |
| Global DoD met and auditor MERGE | met | [PR #31](https://github.com/jjresher/Meta-hackathon-bladesight/pull/31), [PR #35](https://github.com/jjresher/Meta-hackathon-bladesight/pull/35) comment: MERGE; CI green | |

## #9 Evaluation harness on the dev split (closed, boxes ticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| metric functions unit-tested on toy boxes | met | [test_eval_metrics.py L48](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_eval_metrics.py#L48), [test_eval_matching.py](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_eval_matching.py#L10) | 11 + 4 passed |
| dev report committed | met | [eval_dev.md](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/eval_dev.md), `eval_dev.json`, `eval_dev_sweep.svg` | numbers match the README |
| cost of the run logged | met | [eval_dev.md L3](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/eval_dev.md#L3) | 3.1759 USD |
| Global DoD met and auditor MERGE | met | [PR #32](https://github.com/jjresher/Meta-hackathon-bladesight/pull/32) body, [PR #36](https://github.com/jjresher/Meta-hackathon-bladesight/pull/36) comment: MERGE; CI green | |

## #10 Severity gold set and agreement (closed, boxes were unticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| labels in `eval/gold/severity.csv` (no images, only ids) | met | [severity.csv](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/eval/gold/severity.csv) | 40 rows, all labelled, ids and boxes only |
| `docs/evidence/severity_agreement.md` | met | [severity_agreement.md L27](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/severity_agreement.md#L27) | kappa recomputed: 0.121 |
| Global DoD met and auditor MERGE | met | [PR #33](https://github.com/jjresher/Meta-hackathon-bladesight/pull/33) comment MERGE; [PR #34](https://github.com/jjresher/Meta-hackathon-bladesight/pull/34) comment MERGE AFTER FIXES, fixed in `bba4255` (on `main`); CI green | |

## #11 Fleet agent (closed, boxes ticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| end-to-end run on the farm produces ranking + work orders + report | met | [fleet_run.md L23](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/fleet_run.md#L23), `replay/work_orders.json`, `replay/reports/latest.json` | 9 orders recounted |
| trace saved and replayable | met | `replay/runs/run-final.json` (60 steps); [test_fleet.py L236](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_fleet.py#L236) | replay needs the gitignored response cache; the demo reads the stored results |
| tests with stub tools for the loop, step limit and evidence rule | met | [test_fleet.py L103, L201, L222](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_fleet.py#L201-L222) | 14 passed |
| Global DoD met and auditor MERGE | met | PR #35 comment: MERGE; CI green | |

## #12 FastAPI backend (closed, boxes ticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| API tests with TestClient on stub data | met | [test_api.py](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_api.py#L40) | 12 passed |
| replay mode works with no API key set | met | [test_api.py L40](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_api.py#L40), [L155](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_api.py#L155) | |
| Global DoD met and auditor MERGE | met | [PR #37](https://github.com/jjresher/Meta-hackathon-bladesight/pull/37) comment: MERGE; CI green | |

## #13 Web UI (closed, **reopened**)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| Playwright smoke: open fleet, open one inspection, open work order | met | [smoke.spec.ts L57](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/web/tests/smoke.spec.ts#L57), [ci.yml L44](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/.github/workflows/ci.yml#L44); `web` check green on [PR #44](https://github.com/jjresher/Meta-hackathon-bladesight/actions/runs/41765807898/job/126363787423) | 1280px and 390px projects ([playwright.config.ts L25-26](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/web/playwright.config.ts#L25-L26)); also run against the public URL (sprint log 22:35) |
| screenshots at 1280px and 390px in the PR | **not met** | [PR #44](https://github.com/jjresher/Meta-hackathon-bladesight/pull/44) "How it was tested" | the 10 PNGs exist in `bladesight-screenshots/` next to the repo but were never attached; attaching them to a PR comment is the human's call (rule 2 covers commits) |
| no console errors | met | [smoke.spec.ts L59-60](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/web/tests/smoke.spec.ts#L59-L60) fails on any console or page error; green in CI | |
| Global DoD met and auditor MERGE | met | PR #44 "Audit": MERGE AFTER FIXES, all three fixed; sprint log 22:20 and 22:45 (#45 MERGE); CI green | |

## #16 Held-out evaluation, single run (closed, boxes were unticked)

| Checkbox | Status | Evidence | Note |
|---|---|---|---|
| `docs/evidence/eval_heldout.md` with numbers and bootstrap confidence intervals | met | [eval_heldout.md](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/eval_heldout.md#L3), `eval_heldout.json` | numbers match the README |
| manifest hash verified before the run | met | [eval/__main__.py L88-89](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/src/bladesight/eval/__main__.py#L88-L89) verifies before any label is read and aborts on mismatch ([test_heldout.py L222](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/tests/test_heldout.py#L222)); [preregistration.md L104-140](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/eval/preregistration.md#L104-L140) records the check in the log and the re-check (2,029 files) | the evidence file itself does not quote the "manifest ok" line; the run could not have written it without passing the check |
| no tuning after the run (any change is listed) | met | [eval_heldout.md L46-53](https://github.com/jjresher/Meta-hackathon-bladesight/blob/7c92e77e870c2335ea395adc23edd4de53d008e1/docs/evidence/eval_heldout.md#L46-L53); `git diff ade7d9c..7c92e77 -- src/bladesight/detect src/bladesight/eval` touches only `eval/agreement.py` (#15, severity, not the held-out path); outside those directories, `meta/config.py` changes only the unused open-weights model id, `data/demo.py` is new and `assess` is not on the detection eval path | the only edit to the evidence (cost field) is listed with the original hashes; the preregistration hash at `ade7d9c` is `cef25034...b3e9` as recorded |
| Global DoD met and auditor MERGE | met | sprint log 22:51 (#46: auditor two text fixes, applied) and 22:59 (#48 MERGE); [PR #46](https://github.com/jjresher/Meta-hackathon-bladesight/pull/46) CI green | PR #47 superseded (see above) |
