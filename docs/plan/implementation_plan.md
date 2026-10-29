# Implementation plan: wind turbine blade inspection agent

Working name: **BladeSight** (rename freely before the repo is created).
Solo entry, **Indie Developer** track, Meta Global AI Developer Hackathon.
Author: Juan José (jjresher). Time budget: 6+ hours a day, Thu Oct 29 to Wed Nov 4, 2026.

All times are Colombia time (COT, UTC-5). The official deadline is **Wed Nov 4, 9:00 PM ET**,
which is 9:00 PM COT (US clocks change on Nov 1). Our own target is **Wed Nov 4, 3:00 PM COT**.

## 1. Problem and pitch

Wind turbine blades erode, crack and get struck by lightning. Inspections produce thousands of
drone photos that people still review by hand, and a missed defect becomes a blade failure,
weeks of downtime and a crane rental. BladeSight turns a wind farm's inspection photos into a
**prioritized repair plan**:

1. **SAM 3.1** finds and segments each defect from a text concept ("crack", "leading edge
   erosion", ...) and segments the blade itself, with no training.
2. **Measurement** turns masks into size and position along the blade (root, mid, tip).
3. **Muse Spark** (vision) judges each defect against a written severity rubric and explains why.
4. **Verification**: a second look checks the first; when they disagree or confidence is low the
   system says "needs human review" or "re-inspect" instead of guessing.
5. **A fleet agent** plans across the whole farm with tools: compares 2017 vs 2018 inspections,
   ranks turbines, writes work orders and the inspection report, and asks for re-inspection
   where the evidence is weak.

One-line pitch: *"Zero-shot blade inspection: from drone photos to a verified repair plan, with
measured accuracy."*

Challenge fit: **Push the Frontier** (energy; "give a machine a new capability"; "understand and
control a physical system").

## 2. Judging and prize strategy

| Criterion (weight) | How we score |
|---|---|
| Impact (30%) | Clear user (wind farm O&M teams), clear cost of a miss, global problem |
| Use of Meta AI tooling (25%) | SAM 3.1 concept segmentation doing real work + Muse Spark vision reasoning + agentic tool use + open-weights path |
| Technical depth (20%) | Measured precision/recall on a sealed held-out split, threshold curve, error analysis, verification layer |
| Demo (25%) | Photo -> defects light up -> severity with reasons -> farm ranking -> work order, in under 3 minutes, live URL |

| Bonus prize | Plan | Issue |
|---|---|---|
| Best Agentic Use-Case ($5k) | Fleet agent with tools, verification and abstention, visible trace | #11, #8, #13 |
| Best Build on Meta Open Weight Models ($10k) | Severity and report steps also run on **Muse Spark Open** via Baseten (`meta-models/muse-spark-open-1026`), compared with the API | #15 |
| Most Viral ($20k) | Clip of the demo on X with #MetaAIHackathon, post link submitted; engagement counts to Nov 8 EOD | #21 |
| Community Vote ($10k) | Gallery votes from Nov 9; share in Discord, LinkedIn, EAFIT and personal networks | #21 |
| Best Creative Build ($5k) | **Not targeted**: requires Muse Image or Muse Wonder as the core of a creative project; forcing it would hurt focus | - |

## 3. Facts and constraints that shape the plan

- Models: `muse-spark-1.2` / `muse-spark-1.3` (Model API), SAM 3.1 (Model API, other teams
  already use it), `muse-voice-transcribe-1.0` (not needed). Open weights on Baseten:
  `meta-models/muse-spark-open-1026` (OpenAI-compatible API).
- **The Model API fails intermittently** (a participant measured ~25% failed calls on Oct 29).
  Every call goes through one client with retries, backoff, timeouts and a disk cache. The public
  demo runs in **replay mode** from cached results so it never depends on a live call.
- Some participants cannot create API keys: create the key on day 1 and report early if blocked.
- Budget: $150 Meta credits, card on file (charges if credits run out). Hard spend cap per process
  and a spend log; every development call follows the `meta-api-check` skill.
- Data: DTU drone inspection images of a Nordtank turbine (2017 and 2018). The annotated version
  (YOLO boxes, classes **damage** and **dirt**, ~13k tiles of 586x371, ~2.9k labeled) is
  **CC BY-NC 4.0**. Never commit data: a download script plus attribution. The labels have no
  severity, so severity is evaluated on a small hand-labeled gold set (#10).
- Rules: public repo created during the event; demo shows only work built this week; 3-minute
  video; anti-project list does not apply (not medical, not RAG, not generic image analyzer:
  this is a verified agent with measured detection).
- Live sessions worth attending: Fri Oct 30 11:00 COT (Fireworks, open models). Office hours in
  `#office-hours`: 9:00-10:00 COT on Oct 30, 10:00-11:00 COT Nov 2-4. Nov 3 is the last full day
  for submission questions.

## 4. Architecture

```
data/ (gitignored)            DTU tiles + labels  ->  dev split | sealed held-out split (manifest)
src/bladesight/
  meta/       client: Muse Spark (chat + vision + tools), SAM 3.1, retries, cache, spend cap, stub
  detect/     SAM 3.1 concept prompts -> defect masks + blade mask, post-processing
  measure/    mask -> area ratio, bbox, position along blade (root/mid/tip)
  assess/     Muse Spark severity vs docs/rubric.md -> Assessment (pydantic)
  verify/     second look + rules -> confidence, needs_review, reinspect
  fleet/      synthetic farm (turbines T01..T12, inspections 2017/2018) + agent tools + loop
  eval/       matching, metrics, threshold sweep, error gallery, report writers
  api/        FastAPI: /fleet /inspections /runs /reports /eval /health, replay mode
web/          React + Vite + TS: Fleet, Inspection viewer, Work orders, Agent trace, Evaluation
docs/         plan, rubric, decision ledger, limitations, evidence, submission
```

Contracts (pydantic, one place): `Defect`, `Measurement`, `Assessment`, `Verification`,
`Turbine`, `Inspection`, `WorkOrder`, `AgentStep`, `EvalReport`.

Fallback if SAM 3.1 text prompts miss defects (decided in #3): Muse Spark proposes boxes, SAM 3.1
refines them into masks from box prompts. Meta models stay at the core either way.

## 5. Milestones

| Milestone | When (COT) | Issues | Exit criterion |
|---|---|---|---|
| M0 Foundations | Thu Oct 29 | #1-#4 | CI green, API key works, cached client, data split sealed, SAM go/no-go recorded |
| M1 Vertical slice | Fri Oct 30 - Sat Oct 31 | #5-#9 | One CLI command: image -> defects -> measures -> severity -> verification; dev metrics written |
| M2 Agent + product | Sun Nov 1 - Mon Nov 2 | #10-#14 | Fleet agent end to end, UI live on a public Render URL in replay mode |
| M3 Evidence + polish | Mon Nov 2 - Tue Nov 3 | #15-#18 | Held-out run done once, README and limitations final; **code freeze end of Tue Nov 3** |
| M4 Submission | Wed Nov 4 | #19-#21 | Video, submission sent by 3:00 PM COT, X post live |

**Capacity check.** Estimates assume Claude Code writes most of the code and you steer, review
and test. P0 issues add up to about 50 hours of wall-clock work, P1/P2 to about 10 more; six
days at 6-7 hours give roughly 40. P0 alone is tight, so: run Claude Code on one issue while you
test or label for another, keep P1/P2 strictly behind P0, and expect to apply part of the cut
order. That is planned, not a failure.

**Cut order if behind:** #17 -> #15 -> #10 -> trace and evaluation pages polish (#13 part) ->
live (non-replay) runs in the public demo (#12 part).
**Never cut:** #1, #2, #4, #5, #7, #8, #11, #12, #13 (core screens), #14, #16, #18, #19, #20.

## 6. Schedule

| Day | Target |
|---|---|
| Thu Oct 29 (today) | #1 bootstrap, #2 client, #4 data; start #3 spike |
| Fri Oct 30 | #3 go/no-go by 12:00; #5 detection; #6 measurement |
| Sat Oct 31 | #7 severity, #8 verification, #9 dev evaluation; vertical slice demo by EOD |
| Sun Nov 1 | #11 fleet agent; #12 API |
| Mon Nov 2 | #13 UI; #14 Render staging; #10 gold set labeling (about 1 hour of your time); #15 if Baseten credits arrived |
| Tue Nov 3 | #16 held-out run (morning, once); #18 docs; #19 video script; **freeze EOD** |
| Wed Nov 4 | #19 record and edit; #20 dry run and submit by 15:00; #21 X post |
| Nov 5-8 | #21 engagement push (Most Viral window closes Nov 8 EOD) |
| Nov 9-16 | #21 community vote push |

## 7. Issues

Labels: `P0` `P1` `P2` · `type:feat|eval|infra|docs|demo|growth` ·
`area:meta|data|detect|assess|agent|api|web|eval` · `prize:agentic|prize:open-weights|prize:viral|prize:community`.
Milestones M0-M4 as above. Every issue also has to meet the **global DoD** (section 8).

### M0 Foundations

**#1 Bootstrap repo and agent harness** · P0 · infra · M0 · ~2h
Set up the repo so every later issue is fast and safe.
- uv (Python 3.12), ruff, pyright, pytest, poethepoet tasks (`check`, `fmt`, `eval`, `serve`, `web-*`).
- `AGENTS.md` (canonical) + `CLAUDE.md` importing it; `.claude/settings.json` denying `.env`,
  `data/heldout/**`, force-push and `--no-verify`.
- `.claude/agents/auditor.md`, skills `meta-api-check`, `eval-run`, `issue-audit`, `write-decision`.
- PR template with DoD, issue template, GitHub Actions CI (`poe check`), pre-commit (gitleaks,
  forbidden paths: data, images, `.env`).
- `docs/decision_ledger.md`, `docs/limitations.md`, `.env.example` (names only).
DoD: [ ] fresh clone -> `uv sync && uv run poe check` passes · [ ] CI green on main ·
[ ] committing a `.jpg` under `data/` or a fake key is blocked by pre-commit · [ ] README stub
states "built during the Meta Global AI Developer Hackathon, Oct 27 - Nov 4 2026".

**#2 Meta API client with retries, cache and spend cap** · P0 · feat · area:meta · M0 · ~3h · deps #1
- One client for Muse Spark (text, image input, tool calls) and SAM 3.1.
- Retries with exponential backoff and jitter on 5xx/timeouts; per-call timeout.
- Disk cache keyed by sha256 of (endpoint, model, payload); `--no-cache` flag.
- Spend log (tokens or calls, estimated USD) and hard cap per process (`META_SPEND_LIMIT_USD`).
- `StubProvider` returning recorded fixtures so tests and CI spend 0 USD.
DoD: [ ] unit tests for retry, cache hit/miss, cap refusal (stub) · [ ] one real call each to Muse
Spark and SAM 3.1 logged with cost (step 1 of `meta-api-check`) · [ ] key read from `.env` only,
never printed.

**#3 Spike: SAM 3.1 and Muse Spark on blade images (go/no-go)** · P0 · eval · area:detect · M0 · ~3h · deps #2, #4
Biggest technical risk; answer it before building on it.
- 20 dev tiles with damage + 5 clean. Try concept prompts (crack, erosion, lightning damage,
  surface damage, dirt, wind turbine blade) and score thresholds.
- Muse Spark: can it describe and grade a defect crop? Does it return reliable JSON?
- Measure rough recall on the 20 tiles. Decide: text prompts only, or fallback (Spark boxes ->
  SAM box prompts).
DoD: [ ] findings and the chosen prompt list in `docs/decision_ledger.md` with a sample gallery in
`docs/evidence/spike.md` · [ ] go/no-go decision written by Fri 12:00 · [ ] cost of the spike logged.

**#4 Dataset download, split and seal** · P0 · infra · area:data · M0 · ~2h · deps #1
- Script downloads the annotated DTU set (Dataset Ninja or Kaggle) into `data/` (gitignored).
- Convert labels to one internal format; keep image-level metadata (year when available).
- Fixed-seed split, stratified by has-damage: dev (~85%) and held-out (~15%, min 300 labeled tiles).
- `eval/heldout_manifest.sha256` committed; held-out never read before #16.
- `DATA.md`: source, licence (CC BY-NC 4.0), citation (Shihavuddin & Chen, 2018, DOI
  10.17632/hd96prn3nc.2), what is and is not committed.
DoD: [ ] `uv run poe data` reproduces the split and the manifest hash · [ ] no data in git ·
[ ] licence and citation in README and `DATA.md`.

### M1 Vertical slice

**#5 Defect and blade detection with SAM 3.1** · P0 · feat · area:detect · M1 · ~4h · deps #3
- Concept prompts from #3 -> masks, boxes, scores; blade mask for context.
- Post-processing: merge overlaps, drop tiny masks, keep masks inside the blade.
- `Defect` contract; cached; CLI `poe detect <image>` writes an overlay PNG.
DoD: [ ] tests on recorded SAM responses (stub) · [ ] overlay images for 5 dev tiles in the PR ·
[ ] runtime and cost per image recorded.

**#6 Measurement and localization** · P0 · feat · area:detect · M1 · ~2h · deps #5
- Area ratio vs blade, bbox, elongation (crack vs patch), position along blade (root/mid/tip) from
  the blade mask's principal axis; documented as relative (pixels), not millimetres.
DoD: [ ] unit tests with synthetic masks (known answers) · [ ] limits written in `docs/limitations.md`.

**#7 Severity assessment with Muse Spark** · P0 · feat · area:assess · M1 · ~3h · deps #5, #6
- `docs/rubric.md`: severity 1-5 with observable criteria, labelled as our illustrative rubric,
  not an industry standard.
- Prompt with crop + context crop + measurements -> `Assessment` (type, severity, rationale,
  confidence) validated by pydantic; retry once on invalid JSON.
DoD: [ ] invalid output handled (test with stub) · [ ] 10 dev examples reviewed by hand in the PR ·
[ ] prompt versioned (`assess/prompts/v1.md`).

**#8 Verification and abstention** · P0 · feat · area:assess · prize:agentic · M1 · ~3h · deps #7
- Second look (different crop scale or prompt) + rule checks (severity vs measured size, defect
  outside blade) -> agreement score.
- Thresholds -> `ok`, `needs_review`, `reinspect`; every verdict carries its reasons.
DoD: [ ] tests for each branch · [ ] the share of `needs_review` on dev reported · [ ] thresholds
recorded in the ledger.

**#9 Evaluation harness on the dev split** · P0 · eval · area:eval · M1 · ~4h · deps #4, #5
- Mask -> box, match to labels at IoU >= 0.3 (also report 0.5); precision, recall, F1 for
  damage and dirt, image-level recall (any damage found).
- Threshold sweep curve (missed defects vs false alarms), error gallery (FN/FP crops by cause).
- `poe eval --split dev` writes `docs/evidence/eval_dev.md` + SVG; refuses `--split heldout`
  unless `ALLOW_HELDOUT=1` (only #16).
DoD: [ ] metric functions unit-tested on toy boxes · [ ] dev report committed · [ ] cost of the
run logged.

### M2 Agent and product

**#10 Severity gold set and agreement** · P1 · eval · area:eval · M2 · ~2h (1h of hand labeling) · deps #7
- 40 dev crops labelled by hand with `docs/rubric.md` (you), blind to the model.
- Weighted kappa and confusion matrix, Muse Spark vs human; same later for Muse Spark Open (#15).
DoD: [ ] labels in `eval/gold/severity.csv` (no images, only ids) · [ ] `docs/evidence/severity_agreement.md`.

**#11 Fleet agent** · P0 · feat · area:agent · prize:agentic · M2 · ~5h · deps #8
- Synthetic farm: 12 turbines, each with 2017 and 2018 inspections built from dataset tiles
  (`fleet/build.py`, seeded, documented as synthetic grouping of real photos).
- Tools: `list_turbines`, `get_inspection`, `compare_inspections`, `assess_image`,
  `create_work_order`, `request_reinspection`, `write_report`.
- Muse Spark tool-calling loop with a step limit, budget cap and full trace (`AgentStep`).
- Rules: a work order cites defect ids and evidence; no claim without a verified assessment;
  low confidence -> re-inspection, never a guess.
DoD: [ ] end-to-end run on the farm produces ranking + work orders + report · [ ] trace saved and
replayable · [ ] tests with stub tools for the loop, step limit and evidence rule.

**#12 FastAPI backend** · P0 · feat · area:api · M2 · ~3h · deps #11
- `/health`, `/fleet`, `/inspections/{id}`, `/reports/latest`, `/eval`, `/runs` (agent trace).
- **Replay mode** (default in production) serves cached results; live mode limited by a key and
  the spend cap. Serves `web/dist` at `/`.
DoD: [ ] API tests with TestClient on stub data · [ ] replay mode works with no API key set.

**#13 Web UI** · P0 · feat · area:web · M2 · ~6h · deps #12
- Screens: **Fleet** (turbines ranked, status chips), **Inspection viewer** (image with toggleable
  masks, defect cards with severity and reasons), **Work orders / report**, **Agent trace**
  (P1), **Evaluation** (metrics, curve, limitations) (P1).
- English UI, responsive down to 390px, accessible contrast, honest labels ("synthetic farm of
  real DTU photos").
DoD: [ ] Playwright smoke: open fleet, open one inspection, open work order · [ ] screenshots at
1280px and 390px in the PR · [ ] no console errors.

**#14 Deploy to Render** · P0 · infra · area:api · M2 · ~2h · deps #12, #13
- Dockerfile (API + built web), `render.yaml`, env vars set in the dashboard, replay mode on,
  spend cap on, health check. Plan for Nov 5-16 judging: paid instance so it does not sleep.
DoD: [ ] public URL works from a phone · [ ] cold start time noted · [ ] smoke script passes
against the URL.

### M3 Evidence and polish

**#15 Open-weights path on Baseten** · P1 · feat · area:assess · prize:open-weights · M3 · ~3h · deps #7, #10
- Provider switch: `assess` and `write_report` on `meta-models/muse-spark-open-1026` (Baseten,
  OpenAI-compatible). Compare agreement (gold set) and cost vs the Model API.
DoD: [ ] one command reruns the gold set on open weights · [ ] comparison table in
`docs/evidence/open_weights.md` · [ ] UI shows which model produced each assessment.

**#16 Held-out evaluation, single run** · P0 · eval · area:eval · M3 · ~2h · deps #9, #8
- Before the run, write `eval/preregistration.md`: metrics, IoU, thresholds, prompt versions,
  frozen. Then run once on held-out; report deviations.
DoD: [ ] `docs/evidence/eval_heldout.md` with numbers and confidence intervals (bootstrap) ·
[ ] manifest hash verified before the run · [ ] no tuning after the run (any change is listed).

**#17 YOLO baseline (optional)** · P2 · eval · area:eval · M3 · ~3h · deps #4
- YOLOv8n trained on dev labels, evaluated on held-out with the same harness; compare with SAM
  zero-shot ("labels needed vs zero labels").
DoD: [ ] numbers in `docs/evidence/baseline_yolo.md` · [ ] training script reproducible.

**#18 README, architecture and limitations** · P0 · docs · M3 · ~3h · deps #16
- Problem, 30-second demo GIF, live URL, architecture diagram, how to run (replay and live),
  results table, what was built during the hackathon, limitations, data attribution, licence.
DoD: [ ] a fresh clone following the README reaches the UI in replay mode · [ ] every number in
the README links to an evidence file.

### M4 Submission

**#19 Demo video (3 minutes)** · P0 · demo · M4 · ~4h · deps #14, #16
- `docs/submission/video_script.md`: opens with the "built this week" line; problem (20s), live
  walkthrough (2m), numbers + open weights + agent trace (30s), close (10s).
- Record against the live URL in replay mode; English captions; under 3:00.
DoD: [ ] link opens without login · [ ] length <= 3:00 · [ ] every claim in it is backed by an
evidence file.

**#20 Submission and dry run** · P0 · demo · M4 · ~1h · deps #18, #19
- `docs/submission/checklist.md`: public repo, video link, contributors, Indie track, bonus flags
  (agentic, open weights), X post link, live URL. Fresh-clone dry run. Submit by 15:00 COT.
DoD: [ ] confirmation received · [ ] links re-tested from an incognito window.

**#21 Launch and community** · P1 · growth · prize:viral · prize:community · M4 · ~2h + daily 15 min to Nov 16
- 30-45s vertical clip, post on X with #MetaAIHackathon (ask in `#questions` which Meta account to
  tag), submit the post link; share in Discord, LinkedIn, EAFIT groups; vote push Nov 9-16.
DoD: [ ] post live before submission · [ ] post link in the submission · [ ] reminder plan written.

## 8. Global Definition of Done (every issue)

- [ ] `uv run poe check` passes locally and CI is green (and `poe web-check` for web changes).
- [ ] New behavior has tests on the stub; bug fixes include a regression test; tests spend 0 USD.
- [ ] No secrets, data, images or held-out files committed; held-out untouched before #16.
- [ ] Real model calls followed `meta-api-check`; their cost is in the PR.
- [ ] Every number claimed in docs, UI or video links to an evidence file.
- [ ] Decisions with trade-offs: one line in `docs/decision_ledger.md`; known gaps in
      `docs/limitations.md` with the issue number.
- [ ] The PR was audited by the `auditor` agent and its blocking findings are resolved.
- [ ] Code, docs, commits and UI in English. Conventional commits.

## 9. Workflow and audit

- One issue = one branch `i<n>-<slug>` = one PR, using the PR template (`Closes #n`).
- Before opening the PR: `poe check`, then ask Claude Code to run the **auditor** agent on the
  diff. It starts with no context, reads the issue's DoD, `AGENTS.md` and the diff, and returns
  findings split into **blocking** and **follow-up**.
- **Blocking rule** (learned from Verdict): a finding blocks only if it breaks the demo, breaks a
  rule in `AGENTS.md`, or supports a claim we cannot back. Everything else becomes a line in
  `docs/limitations.md` or a new P2 issue.
- You review and merge (solo: the auditor's review stands in for a teammate's).
- **Daily check (10 min, end of day)**: plan vs schedule, spend so far, cut order applied if
  behind, ledger updated. Claude Code can run it with the `issue-audit` skill in "day" mode.

## 10. Risks

| Risk | Mitigation |
|---|---|
| SAM 3.1 misses thin cracks | #3 go/no-go with fallback (Spark boxes -> SAM boxes); report it honestly in limitations |
| API flakiness or key problems | Retries + cache + replay mode; create key day 1; report in `#office-hours` early |
| Credits run out | Cache everything, spend cap, small dev subsets; card charges beyond credits |
| Scope creep, solo | Cut order, freeze Tue EOD, daily check |
| Licence (NC) | Non-commercial hackathon use with attribution; no data in repo; note in `DATA.md` |
| Severity has no ground truth | Own rubric labelled illustrative + hand gold set + agreement metric |
| Demo breaks live | Replay mode default; video recorded from the deployed URL |

## 11. Open questions

1. Which Meta account to tag on X (asked in `#questions` by others, unanswered as of Oct 29).
2. Whether the Model API exposes SAM 3.1 text prompts, box prompts or both (answered by #3).
3. Licence of the original Mendeley release (the annotated derivative is CC BY-NC 4.0).
