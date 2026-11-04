# Independent submission audit (Kiro)

Independent review of `main` on 2026-11-04 by an agent with no prior context on the build, for the
Meta Global AI Developer Hackathon submission. Read-only except for this file. Scope: the six
checks requested (claims vs evidence, honesty, `AGENTS.md` rules, open-weights verifiability,
submission readiness, DoD boxes). Findings are classified by the `AGENTS.md` blocking rule: a
**BLOCKER** breaks the demo, breaks a rule in `AGENTS.md`, or supports a claim the evidence cannot
back; everything else is **FOLLOW-UP**.

Method: every number in `README.md`, `docs/submission/video_script.md` and
`docs/submission/launch.md` was traced to the `docs/evidence/*` file it cites and compared; the
repo tree was scanned for tracked images/data, TODOs without an issue, non-English text and
unpinned dependencies; the UI source (`web/src`) was read for overclaims and for how it selects its
data source.

## Verdict

**No BLOCKER found.** The claim set is unusually disciplined: numbers match their evidence,
held-out (v1) and fresh-dev (v2) numbers are kept separate and labelled, the synthetic farm is
labelled everywhere, and the open-weights scope is stated honestly (planning half only, detection
stays on SAM 3.1). The items below are FOLLOW-UPs; the most material is a stale DoD-audit snapshot
(F1) that still shows the pre-v2 farm counts.

---

## BLOCKERS

None.

---

## FOLLOW-UPS

### F1. `dod_audit.md` is frozen at a pre-v2 commit and shows different farm counts than the live demo

`docs/submission/dod_audit.md` was "Audited on 2026-11-03 ... against `main` at commit `7c92e77`"
(dod_audit.md L3-4) and it recounts the farm as **33 ok / 50 / 13**, **9 work orders (3 repair, 6
reinspect)**, **60 steps** (dod_audit.md Summary "Numbers recomputed" block; #8 row L-"33 / 50 /
13"; #11 row "9 orders recounted"). The current demo and every public-facing claim now run
detector **v2** and report **35 ok / 50 / 13**, **11 work orders (5 repair, 6 reinspect)**, **59
steps**: see `docs/evidence/fleet_run.md` L13, L23-24 and `README.md` Results table
("Verification on the synthetic farm (98 defects, detection v2) | 35 `ok`, 50 `needs_review`, 13
`reinspect`" and "11 work orders (5 repair on `ok` defects, 6 re-inspections)").
`docs/submission/checklist.md` ("Done (with evidence)") links `dod_audit.md` as current submission
evidence without a note that its farm counts predate the v2 integration.
Not a BLOCKER: the discrepancy is explained by the documented v1->v2 transition
(`docs/limitations.md`, last two entries: "The demo farm and both replays now run detection v2")
and the live-facing numbers are self-consistent. But a judge comparing the two files will see a
contradiction.
**Fix:** add one line at the top of `dod_audit.md` stating it is a snapshot at `7c92e77` (pre-v2),
and that current farm counts are 35/50/13 and 11 orders per `fleet_run.md`; or re-run the audit
against current `main`.

### F2. The checklist still carries unchecked human steps and a stale/superseded PR

`docs/submission/checklist.md` ("What the human must do" and "Before sending (final ticks)") lists
several open items that gate a correct submission: close superseded PR #47 (step 2; also flagged in
dod_audit.md "Other findings"), attach the #5 and #13 screenshots as PR comments (step 3; the two
"screenshots/overlays in the PR" DoD boxes are **not met**, dod_audit.md #5 and #13 rows), record
and link the video (steps 6-9), and the "Before sending" checkboxes are all still unticked. These
are correctly marked **human** and are expected this close to submission; listed here so they are
not forgotten. Not a BLOCKER (no false claim; the work is tracked).

### F3. Example fixture with made-up values ships in the web bundle source

`web/src/fixtures/fleet.json` L3-4 is labelled `"synthetic": true` with
`"note": "EXAMPLE FIXTURE for UI development: made-up values, not results. ..."`. It is imported
only by `web/src/test/mockApi.ts` L4 (test harness), and the live client fetches from `/api/*`
(`web/src/api/client.ts` L21, L45, L72-81), so the deployed UI never shows these made-up numbers.
The label is honest and the file is test-scoped. Not a BLOCKER; noted so no one later wires it into
the app by mistake. **Fix (optional):** none required; the test-only import boundary is the
safeguard.

### F4. UI severity kappa is a hardcoded constant, guarded by a test

`web/src/evidence.ts` L11-14 hardcodes `kappa: 0.12`, `kappaLow: -0.05`, `kappaHigh: 0.29`, which
match `docs/evidence/severity_agreement.md` "Agreement" (0.12, interval -0.05 to 0.29) exactly.
`docs/limitations.md` already discloses this ("The Evaluation page shows the severity kappa ...
from constants in `web/src/evidence.ts`, not from the API ... `web/src/evidence.test.ts` fails if
they stop matching"). Correct and disclosed; FOLLOW-UP only because a future severity re-run must
update both the evidence file and the constant.

---

## Check 1: Claims vs evidence (numbers traced to the cited file)

Every number checked appears, exactly, in the evidence file it cites. Spot-checks:

| Claim (README Results unless noted) | Evidence file | Match |
|---|---|---|
| Held-out damage box: precision 0.19 (0.15-0.22), recall 0.16 (0.14-0.19), IoU 0.3, 760 tiles | `eval_heldout.md` "Box matching": 0.187 (0.152-0.222), 0.164 (0.136-0.194) | yes (rounded down, honest) |
| Held-out image-level: recall 0.70 over 368 tiles, 24% false alarm over 300 | `eval_heldout.md` "Image level": 0.698 over 368; 0.240 over 300 | yes |
| Held-out dirt: precision 0.05, recall 0.44 | `eval_heldout.md`: 0.051, 0.439 | yes |
| Dev damage box: precision 0.37 (0.31-0.42), recall 0.22 (0.18-0.26) | `eval_dev.md`: 0.366 (0.311-0.424), 0.221 (0.180-0.264) | yes |
| Dev image-level recall 0.77, 21% false alarm | `eval_dev.md`: 0.767; 0.210 | yes |
| v2: F1 0.25 vs v1 0.22, paired +0.026 (+0.006 to +0.045), FA 21% both, prec 0.31, recall 0.21 | `eval_fresh_v2.md` "Verdict"/table: 0.250 vs 0.224; +0.026 (+0.006 to +0.045); 0.210; 0.307; 0.210 | yes |
| Severity kappa 0.12 (-0.05 to 0.29), exact 25%, advisory | `severity_agreement.md`: 0.12 (-0.05 to 0.29), 25% | yes |
| Open-weights kappa 0.19 (0.01 to 0.38), exact 30% | `open_weights.md` gold table: 0.19 (0.01 to 0.38), 30% | yes |
| Farm verdicts 35/50/13; severity {1:61,2:12,3:25}; no defect above 3 | `fleet_run.md` "Farm processing" | yes |
| Agent `run-final`: 59 steps, 25 tool calls, 16 turns, 11 orders (5 repair, 6 reinspect), 0.07 USD | `fleet_run.md` "Agent run"/"Agent autonomy" (0.0683) | yes |
| Open farm: same severity 78/98, same verdict 64/98; 23 tool calls, 9 orders (2 repair,1 monitor,6 reinspect); 2.11 + 0.06 USD | `open_weights_farm.md` "Per defect"/"Agent autonomy"/"Cost" (2.1059, 0.0569) | yes |
| Detection cost ~0.014 USD/tile | `detect.md` (also `limitations.md`) | yes |
| Demo: smoke 1.9 s, cold start 21.5 s after 3.5 h idle, 390x844 no scroll on 5 screens | `deploy.md` L29, L43, L48-60 | yes |

**Held-out vs v2 separation (explicitly checked):** every public source states held-out measures
v1 and the demo runs v2, and never quotes a held-out number as if it measured v2. README Results
intro ("Both measure the first detector (v1). The demo runs a later one (v2) ... v2 was never
measured on the held-out split"); `video_script.md` note under the table ("The held-out numbers
(notes 10-11) measure detector v1; the demo runs v2 (note 13). Never quote a held-out number as if
it measured v2"); `launch.md` 2/3 and the LinkedIn text ("The demo runs a later detector ... never
measured on the held-out set"). No mixing found.

**Rounding:** held-out precision 0.187->0.19 and recall 0.164->0.16 are rounded toward the detector
looking *worse* or neutral, not better. No misleading rounding found.

## Check 2: Honesty / overclaim scan

- `grep -rniE 'ground.truth|state of the art|SOTA|world.?class|best.in.class'` over `README.md`,
  `docs/`, `web/src`: no hits. The only `expert` hit is `docs/decision_ledger.md` L43 "no domain
  expert available" (a scoping note, not a claim). Severity is consistently called "advisory" and
  tied to "one non-specialist applying the rubric" (README Results + "How to read them honestly";
  `severity_agreement.md` "What this measures").
- No real turbine id or inspection year presented as real: README "The demo farm is synthetic" and
  `video_script.md` "Rules for the recording" ("never state a real inspection year"). UI labels the
  farm synthetic: `web/src/App.tsx` L63 "Synthetic farm of real DTU photos", `web/src/components/Chips.tsx`
  L63, `web/src/fixtures/fleet.json` L4, and the schema description "synthetic grouping: the DTU
  tiles carry no real year" (`web/src/fixtures/schema.json` L943); test guard
  `web/src/screens/screens.test.tsx` L35 asserts the fleet note matches `/synthetic/i`.
- Open-weights wording does not overclaim: every source says the planning half (severity,
  verification, agent, report) runs on Muse Spark Open and detection stays on SAM 3.1 via the Model
  API, and never that the open model is better (README "Runs on Meta open weights";
  `open_weights.md` "What runs on which model"; `launch.md` rules; `checklist.md` open-weights row).
  This matches what `docs/evidence/open_weights.md` and `open_weights_farm.md` support.

## Check 3: `AGENTS.md` rules

- **Secrets (rule 1):** `.env` is gitignored (`.gitignore`), not tracked; this audit did not open
  it. `git ls-files` shows no `.env`.
- **No data/images (rule 2):** `git ls-files | grep -iE '\.(jpg|jpeg|png|gif|webp|tif|tiff|mp4|mov|zip|tar|gz|pt|pth|onnx|safetensors)$'` -> none. The repo deliberately
  commits no raster images (README "Video (3 minutes)", `limitations.md` "no 30-second demo GIF");
  UI visuals are inline SVG (`docs/architecture.svg` is the one committed SVG).
- **TODO without an issue (DoD):** no `TODO/FIXME/XXX/HACK` in `src/`, `web/src`, `web/tests`,
  `docs/` or the root `*.md` outside the issue-tagged form. All hits are inside
  `web/node_modules/` (third-party, not repo source).
- **English only (rule 7):** no non-English prose found in the repo source (the Spanish handoff is
  chat-only by rule and is not a file).
- **Pinned dependencies (rule 8):** `pyproject.toml` uses exact `==` for every runtime and dev
  dependency; `uv.lock` is committed. `web/package.json` dependencies and devDependencies are all
  exact (no `^`/`~`): e.g. `react` 19.3.1, `vite` 8.3.5, `vitest` 5.1.0, `@playwright/test` 1.64.1;
  `grep -nE '"[~^]' web/package.json` -> none. `web/package-lock.json` is committed.

## Check 4: Open-weights prize ($10k) verifiability

From the repo alone it is clear and verifiable which stages run on Muse Spark Open and how to run
them. `docs/evidence/open_weights.md` "What runs on which model" gives the per-stage table and the
single switch (`--chat-provider baseten` or `BLADESIGHT_CHAT_PROVIDER=baseten`,
`src/bladesight/chat.py`); `README.md` "Live mode" gives the exact commands; the CLI exists
(`src/bladesight/fleet/__main__.py` defines `regrade`, `run`, `compare`).

Shortest sequence a verifier would use (from README "Live mode"), after `cp .env.example .env` and
filling `BASETEN_API_KEY` + `BASETEN_SPEND_LIMIT_USD`:

```bash
uv sync
uv run python -m bladesight.data.demo          # fetch the farm tiles (re-grading reads them)
BLADESIGHT_MODE=live uv run poe fleet regrade --chat-provider baseten \
  --source-dir replay --replay-dir /tmp/bladesight-open --workers 3
BLADESIGHT_MODE=live uv run poe fleet run --chat-provider baseten \
  --replay-dir /tmp/bladesight-open --run-id run-open-check
```

Then inspect the stored run, or in replay mode browse `?provider=baseten` on the API
(`curl -s "http://127.0.0.1:8000/api/runs?provider=baseten"`), both documented in README.

**What is unclear / a verifier should know:**
- Model id: the plan's `-1026` suffix 404s; the account's working id is `meta-models/muse-spark-open`
  resolved from Baseten `/v1/models` (`open_weights.md`). A verifier whose account exposes a
  different id must adjust it.
- Re-grading needs the tiles first (gated on the dataset download, which `clean_clone.md` shows can
  be slow or time out on a cold host), and the 15 req/min Baseten limit makes a full re-grade take
  at least ~14 minutes (README, `open_weights.md`). This is throughput, not a blocker.
- Detection is **not** open weights (SAM 3.1 has no open-weights path here); the committed Open run
  reuses the stored Meta detections. This is stated plainly and is the correct scope for the prize.

## Check 5: Submission readiness (`docs/submission/checklist.md`)

- "Facts for the form" is complete (project, tagline, track, challenge, repo, live URL, models,
  bonus flags with the honest open-weights scope).
- Missing/ambiguous, all **human** and tracked: the video link is a placeholder in README and
  checklist (steps 6-9); the X/`<demo URL>`/`<Meta account>` placeholders in `launch.md` are
  unfilled (expected pre-post); the "Before sending (final ticks)" boxes are unticked; superseded
  PR #47 should be closed (step 2). See F1/F2.
- **Clone path is followable.** README "Run it" clone line (`README.md` L169
  `git clone https://github.com/jjresher/Meta-hackathon-bladesight && cd Meta-hackathon-bladesight`)
  matches the verified fresh-clone run in `docs/evidence/clean_clone.md` L15 (same URL, `da0c7dc`).
  The prerequisites (uv; Node.js 22 with npm) and the `npm ci && npm run build` + `poe serve`
  sequence are the steps that clean_clone.md timed as working. The one honest caveat already in the
  README: the tile download (`bladesight.data.demo`) depends on a third-party host and can take
  ~10 min or time out, during which images 404 and the smoke image check fails.

## Check 6: DoD boxes (issues #1-#23)

`docs/submission/dod_audit.md` already audits #1-#13 and #16 box-by-box against each issue's DoD at
`7c92e77`: 54 checkboxes, 48 met, 3 partial (#3 gallery is id-only by rule 2; #5 "recorded" SAM
responses are reconstructed; #7 "10 examples reviewed by hand" were reviewed by the agent then
superseded by #10's 40 human labels), 3 not met (#3 Friday go/no-go deadline, missed and
unfixable; #5 overlay PNGs not attached to the PR; #13 screenshots not attached to the PR), with #5
and #13 reopened for the human to attach local images as PR comments. These assessments are sound
and the "not met" boxes have stated reasons; no box is ticked without evidence in that set.

Gaps / caveats on the DoD audit itself:
- **Coverage gap:** `dod_audit.md` covers #1-#13 and #16 only. Issues **#14 (deploy), #15
  (open weights), #17 (YOLO baseline), #18-#20 (README/video/submission), #21 (launch), #22
  (detection v2), #23 (client cost fix)** are not in the box-by-box table. Most are evidenced
  elsewhere (`deploy.md`, `open_weights.md`, `eval_fresh_v2.md`, `launch.md`, this checklist), and
  #17 is openly documented as **not built** (optional P2) in `docs/limitations.md` ("The YOLO
  baseline (#17) was not built ... there is no 'labels vs zero-shot' comparison"). No overclaim, but
  there is no single box-by-box DoD check for #14-#23. FOLLOW-UP.
- **Stale counts:** the farm numbers in `dod_audit.md` are the pre-v2 values (F1).

No DoD box was found checked without evidence, and the unchecked ones (`checklist.md` "Before
sending", the reopened #5/#13 image attachments) carry a stated reason.

---

## Summary table

| ID | Finding | Class |
|---|---|---|
| F1 | `dod_audit.md` frozen at `7c92e77` shows pre-v2 farm counts (33/50/13, 9 orders) vs live 35/50/13, 11 orders | FOLLOW-UP |
| F2 | Open human submission steps and superseded PR #47 still pending in the checklist | FOLLOW-UP |
| F3 | Example fixture with made-up values present (test-scoped only; honest label) | FOLLOW-UP |
| F4 | UI severity kappa is a hardcoded, test-guarded constant (matches evidence) | FOLLOW-UP |
| - | DoD box-by-box audit covers #1-#13, #16 only; #14-#23 evidenced elsewhere but not boxed | FOLLOW-UP |

Nothing in this review breaks the demo, breaks an `AGENTS.md` rule, or supports a claim the evidence
cannot back. Per the blocking rule, these are follow-ups, and the submission's numbers are honest
and sourced.
