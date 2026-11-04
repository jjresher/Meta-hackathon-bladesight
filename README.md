# BladeSight

**[▶ Video](https://youtu.be/xJRrVH76CBA)** · **[Live demo](https://bladesight.onrender.com)** ·
**[Code](https://github.com/jjresher/Meta-hackathon-bladesight)**

[![BladeSight demo video: click to watch on YouTube](https://img.youtube.com/vi/xJRrVH76CBA/maxresdefault.jpg)](https://youtu.be/xJRrVH76CBA)

Zero-shot wind turbine blade inspection: from drone photos to a **verified, prioritized repair
plan**, built on Meta **SAM 3.1** and **Muse Spark**, with the planning half also running on Meta's
open-weights **Muse Spark Open**.

> Built from scratch during the **Meta Global AI Developer Hackathon** (Oct 27 - Nov 4, 2026),
> Indie Developer track. Everything in this repository was created during the event.

- **Live demo:** <https://bladesight.onrender.com> (replay mode: no login, no key, no model call).
  It runs on a free plan that sleeps when idle. An external job requests it every 10 minutes to keep
  it awake, but a first load can still wait for it to wake (21.5 s measured after 3.5 h idle; Render
  documents about a minute, [`deploy.md`](docs/evidence/deploy.md)).
- **Video (2:55):** <https://youtu.be/xJRrVH76CBA>. There is no GIF in the repository: images and video are never
  committed (data licence and repo rules), so the video is the demo clip.
- Plan, decisions, known gaps: [`docs/plan/implementation_plan.md`](docs/plan/implementation_plan.md),
  [`docs/decision_ledger.md`](docs/decision_ledger.md), [`docs/limitations.md`](docs/limitations.md).

## Try it in 60 seconds

1. Open <https://bladesight.onrender.com>. The first load can take up to about a minute if the free
   instance is asleep.
2. On **Fleet**, click **Turbine 01**, ranked first. It opens the inspection `T01-2018`.
3. On the first tile, open defect card **`d2`** (verified, severity 3), then **`d4`** (needs review:
   the two looks differ by one severity level).
4. **Work orders**: WO-001 repairs `d2`, and WO-006 asks for new photos of `d4` instead of guessing.
5. **Agent trace**: the agent's decisions turn by turn, with the rule behind any rejected call.
6. In the **Run** selector in the header, choose **Muse Spark Open (Baseten)**. Every screen now
   shows the open-weights run.
7. **Evaluation**: detection metrics on dev and held-out, and severity agreement with human labels.

## The problem

Wind turbine blades erode, crack and get struck by lightning. Inspections produce large numbers of drone
photos that people still review by hand, and a missed defect becomes a blade failure, downtime and a
crane rental. BladeSight turns inspection photos into a plan an operations team can act on, and it
says "I am not sure" instead of guessing.

## What it does

1. **SAM 3.1** segments each defect, with no training. Muse Spark proposes boxes for the damage and
   SAM 3.1 turns them into masks with box prompts, plus SAM text concepts
   ([`spike.md`](docs/evidence/spike.md) explains why text alone was not enough).
2. **Measurement** gives relative size, shape and position from the mask (pixels, never
   millimetres: the photos carry no scale).
3. **Muse Spark** grades each defect 1-5 against our own illustrative rubric
   ([`docs/rubric.md`](docs/rubric.md), not an industry standard) and explains why.
4. **Verification** takes a second, independent look and runs rule checks; the result is `ok`,
   `needs_review` or `reinspect`, always with reasons.
5. **A fleet agent** (Muse Spark with seven tools) explains a transparent ranking score
   (verified defects at full weight, `needs_review` defects at a quarter,
   [`rank.py`](src/bladesight/fleet/rank.py)), compares inspections, writes work orders and a report. A repair or
   monitor order can only cite defects with an `ok` verdict: the tool rejects anything else, and
   unverified defects can only become re-inspection requests.

Steps 3-5 run on either Muse Spark (Meta Model API) or Muse Spark Open (open weights on Baseten);
both runs are stored and the demo switches between them.

## What you see in the demo

- **Run selector** (header): "Muse Spark (Model API)" or "Muse Spark Open (Baseten)". It names the
  model behind each stage and every screen follows it (`?provider=` in the URL).
- **Fleet**: the 12 turbines of the synthetic farm, ranked by a deterministic score (verified
  defects at full weight, `needs_review` at a quarter), with status and 2017-vs-2018 trend.
- **Inspection**: the tile with SAM 3.1 masks and boxes, a glyph key for the verdicts, and one card
  per defect (severity, verdict, the second look's reasons, the rationale, and a badge naming the
  model that graded it). The work orders that cite a defect are linked from its card.
- **Work orders** and the agent's **report**: repair orders cite verified defects; re-inspection
  requests cover some of the defects verification could not confirm (19 of 63 in the Muse Spark
  run, [`open_weights_farm.md`](docs/evidence/open_weights_farm.md)).
- **Agent trace**: the agent's decisions turn by turn (its stated reason, the tool call, accepted or
  rejected, and the rule that stopped it if any), what it did on its own, and the 14 rules in force.
- **Compare runs**: the two runs side by side (agreement on severity and verdict, both rankings,
  work-order overlap, what each agent did).
- **Evaluation**: detection metrics on dev and held-out (with the false-alarm rate beside image-level
  recall), the threshold sweep and severity agreement with the human labels.

## Architecture

![Architecture](docs/architecture.svg)

Every model call goes through one client (`src/bladesight/meta`) with retries, a disk cache and a
cumulative spend cap. The API (FastAPI) serves the stored results in `replay/` and
`replay/open-weights/`; the UI is React + Vite + TypeScript; the API contract is one set of pydantic
models ([`docs/api.md`](docs/api.md)) from which the UI's types are generated.

## Results (every number links to its evidence file)

The held-out run (preregistered, run once on 760 tiles of photos nobody tuned on, see "Held-out"
below) is the number to quote for detection; the dev numbers are where the pipeline was developed.
Both measure the first detector (v1). The demo runs a later one (v2), a post-processing change
measured separately, after the held-out run, on a preregistered fresh dev set; v2 was never
measured on the held-out split.

| What | Result | Evidence |
|---|---|---|
| **Held-out** damage detection, box level (IoU 0.3, 760 tiles) | precision 0.19 (95% CI 0.15-0.22), recall 0.16 (0.14-0.19) | [`eval_heldout.md`](docs/evidence/eval_heldout.md) |
| **Held-out** damage, image level | recall 0.70 over 368 damaged tiles, with a 24% false-alarm rate on the 300 tiles that have no box | [`eval_heldout.md`](docs/evidence/eval_heldout.md) |
| **Held-out** dirt | precision 0.05, recall 0.44: weak, not offered as a detector | [`eval_heldout.md`](docs/evidence/eval_heldout.md) |
| Damage detection, box level (IoU 0.3, 300 dev tiles) | precision 0.37 (95% CI 0.31-0.42), recall 0.22 (0.18-0.26) | [`eval_dev.md`](docs/evidence/eval_dev.md) |
| Damage, image level, dev (a damaged 586x371 tile has at least one damage prediction) | recall 0.77, with a 21% false-alarm rate on tiles that have no box | [`eval_dev.md`](docs/evidence/eval_dev.md) |
| Dirt detection, dev | weak (precision 0.05, recall 0.31 over 36 truth boxes): reported as weak, not offered as a detector | [`eval_dev.md`](docs/evidence/eval_dev.md) |
| Detection v2, a later improvement measured on a preregistered fresh dev set after the held-out run (300 dev tiles, 490 damage boxes, photos disjoint from the tuned sample) | damage F1 at IoU 0.3: 0.25 against v1's 0.22 (paired difference +0.026, 95% CI +0.006 to +0.045); false alarms 21% for both on the 100 tiles with no box; precision 0.31, recall 0.21. Dev data, not held-out | [`eval_fresh_v2.md`](docs/evidence/eval_fresh_v2.md) |
| Severity vs a human applying the rubric (40 crops) | quadratic weighted kappa 0.12 (95% interval -0.05 to 0.29), exact agreement 25%: **advisory only** | [`severity_agreement.md`](docs/evidence/severity_agreement.md) |
| Same 40 crops on **Muse Spark Open** | kappa 0.19 (0.01 to 0.38), exact agreement 30%: no worse, not shown to be better | [`open_weights.md`](docs/evidence/open_weights.md) |
| Verification on the synthetic farm (98 defects, detection v2) | 35 `ok`, 50 `needs_review`, 13 `reinspect` | [`fleet_run.md`](docs/evidence/fleet_run.md) |
| Fleet agent run (Muse Spark) | 59 steps, 25 tool calls in 16 model turns, 11 work orders (5 repair on `ok` defects, 6 re-inspections), 0.07 USD | [`fleet_run.md`](docs/evidence/fleet_run.md) |
| Same farm, grading + verification + agent on **Muse Spark Open** | same severity as Muse Spark on 78 of 98 defects, same verdict on 64; 23 tool calls, 9 work orders (2 repair, 1 monitor, 6 re-inspections); 2.11 (cumulative over both grading passes, see [`limitations.md`](docs/limitations.md)) + 0.06 USD | [`open_weights.md`](docs/evidence/open_weights.md), [`open_weights_farm.md`](docs/evidence/open_weights_farm.md) |
| Cost of detection | about 0.0106 USD per tile measured (3.1759 USD for 300 dev tiles); the earlier 0.014 estimate included a blade call the pipeline no longer makes | [`eval_dev.md`](docs/evidence/eval_dev.md), [`detect.md`](docs/evidence/detect.md) |
| Public demo | smoke check OK in 1.9 s; cold start 21.5 s after 3.5 h idle (a second wake took 12.47 s, idle time unknown); no horizontal scroll at 390x844 on all five screens checked | [`deploy.md`](docs/evidence/deploy.md) |

How to read them honestly: the labelled boxes are tiny (in the spike's sample of dev tiles, 73% of
the truth boxes are under 400 px^2, i.e. smaller than 20x20 px, and the median is 210 px^2, about
14.5x14.5 px, [`spike.md`](docs/evidence/spike.md)), so box-level recall is low for any detector;
the dev sample over-represents tiles with boxes, so dev precision is optimistic for a real
inspection; the severity grade agrees only weakly with the human labels, and the labels come from
one person without wind-energy experience applying our rubric, so they measure agreement with the
rubric, not specialist-validated severity. The open-weights comparison is one run per model on 98
defects: agreement between two models, not accuracy. The full list is in
[`docs/limitations.md`](docs/limitations.md). Costs are documented prices times real usage, not
checked against an invoice.

## Why it is agentic

Counted from the stored traces in [`fleet_run.md`](docs/evidence/fleet_run.md):

- The agent decides its own sequence of tool calls over seven tools (rank, read, compare, assess,
  order, re-inspect, report; both stored runs used six and neither called `assess_image`): 25 calls in 16 model turns on Muse Spark, 23 calls in 7 turns on
  Muse Spark Open, each ending with a report it wrote. The prompt gives the rules and a suggested
  workflow; the loop does not fix which tool comes next or which defects to act on.
- It acts on uncertainty instead of hiding it: in both runs 6 of the orders are re-inspection
  requests for defects that verification did not confirm.
- Rules are enforced in code by the tools, not only stated in the prompt: a repair or monitor order
  citing a defect that is not `ok` is rejected (`verified_only`), as are reports citing unknown
  orders or defects (14 rules in `src/bladesight/fleet/rules.py`, tested in
  `tests/test_open_weights.py`). The rejection goes back to the model, which must change its plan.
  Neither stored run triggered a rejection: both agents followed the rules on the first try, so
  the UI lists the rules in force and says that no call was rejected.
- Every step is in the trace with the tool, the arguments, a `decision` summary, the `outcome`,
  the rule that blocked it if any, and the model's own text before the call as `rationale` when it
  wrote one (the Muse Spark run did before 18 of its 25 calls; the Muse Spark Open run wrote none).

## Runs on Meta open weights

The whole planning half of the pipeline (severity, verification, the agent with its tool calls,
and the report) has run end to end on **Muse Spark Open** (`meta-models/muse-spark-open`, Baseten),
stored as a second replay (`replay/open-weights/`) next to the Muse Spark one, on the same stored
detections. Detection (Muse Spark box proposals and SAM 3.1 masks) stays on the Meta Model API:
SAM 3.1 has no open-weights path here. The two runs agree on the severity of 78 of 98 defects and
on the verdict of 64; the open model is more cautious on this farm (25 `ok` against 35)
([`open_weights.md`](docs/evidence/open_weights.md),
[`open_weights_farm.md`](docs/evidence/open_weights_farm.md)). We do not claim either model is
better. In the UI, pick "Muse Spark Open (Baseten)" in the run selector or open **Compare runs**.

The model id actually used on Baseten is exactly **`meta-models/muse-spark-open`**: it is the only
Muse Spark id that `/v1/models` lists for this account (checked on Nov 3). The `-1026` id from the
hackathon guide answers 404 ([`open_weights.md`](docs/evidence/open_weights.md)). To verify:

```bash
# the id Baseten resolves (a free listing, no model call; export BASETEN_API_KEY first)
curl -s https://inference.baseten.co/v1/models -H "Authorization: Api-Key $BASETEN_API_KEY"

# the stored Open run (no key, no model call)
uv run poe serve
curl -s http://127.0.0.1:8000/api/replays                   # which model ran each stage
curl -s "http://127.0.0.1:8000/api/runs?provider=baseten"   # the Open agent trace

# reproduce it live on Baseten (costs and prerequisites: "Live mode" under "Run it")
BLADESIGHT_MODE=live uv run poe fleet regrade --chat-provider baseten \
  --source-dir replay --replay-dir /tmp/bladesight-open --workers 3
BLADESIGHT_MODE=live uv run poe fleet run --chat-provider baseten \
  --replay-dir /tmp/bladesight-open --run-id run-open-check
```

## Models

| Stage | Muse Spark run (`replay/`, default) | Muse Spark Open run (`replay/open-weights/`) |
|---|---|---|
| Box proposals | Muse Spark `muse-spark-1.3`, Meta Model API | the same stored proposals |
| Segmentation | SAM 3.1 `sam-3.1`, Meta Model API | the same stored masks |
| Severity, second look | `muse-spark-1.3` | `meta-models/muse-spark-open`, Baseten |
| Fleet agent and report | `muse-spark-1.3` | `meta-models/muse-spark-open`, Baseten |

`GET /api/replays` returns this table from the stored runs; every assessment, verification, work
order, trace step and report records the model and provider that produced it.

## The demo farm is synthetic

The DTU photos are of **one** Nordtank turbine and carry no real turbine id or inspection year.
The demo farm (12 turbines, 2017 and 2018 inspections of 4 tiles each;
[`fleet_run.md`](docs/evidence/fleet_run.md)) is an invented grouping of real photos, labelled as
such everywhere in the app and the data. Rankings and 2017-vs-2018 trends
illustrate the method; they are not findings about a real farm.

## Run it

### Replay mode (no key, no model call, 0 USD)

Needs [uv](https://docs.astral.sh/uv/) (it installs Python 3.12) and Node.js 22 with npm. Checked
from a fresh clone ([`clean_clone.md`](docs/evidence/clean_clone.md)):

```bash
git clone https://github.com/jjresher/Meta-hackathon-bladesight && cd Meta-hackathon-bladesight
uv sync
uv run python -m bladesight.data.demo     # the demo tiles: streams the 2.8 GB archive, keeps only those
(cd web && npm ci && npm run build)       # the web UI, served by the API at /
uv run poe serve                          # http://127.0.0.1:8000 (UI at /, interactive API docs at /docs)
uv run python -m bladesight.api.smoke http://127.0.0.1:8000   # in a second terminal
```

- Port 8000 taken? `uv run poe serve --port 8010` (extra arguments go to uvicorn).
- The tiles step is the slow one and depends on a third-party host: it reads the archive until all
  96 demo tiles are found. It took about 10 minutes in the first dry run, and in the second it ran
  for 3 hours and timed out with 12 of 96 tiles ([`clean_clone.md`](docs/evidence/clean_clone.md)).
  The rest took under a minute with warm uv and npm caches. You can run it
  in parallel with the rest; until it finishes, images answer 404, the UI shows "Photo unavailable"
  next to the defect data, and the smoke check fails on its image request.
- Without `web/dist` (no web build) `/` answers 404 and the API still lives under `/api` and `/docs`.
  The UI build must exist before `poe serve` starts.
- Both runs are served: `/api/replays` lists them, and `?provider=baseten` on the data endpoints
  (or the UI's run selector) selects the Muse Spark Open run.

```bash
curl -s http://127.0.0.1:8000/api/replays                    # which model ran each stage, per run
curl -s "http://127.0.0.1:8000/api/fleet?provider=baseten"   # ranking from the Open grades
curl -s "http://127.0.0.1:8000/api/runs?provider=baseten"    # the Open agent trace
uv run poe fleet compare --farm-cost 1.778 --open-farm-cost 2.1059  # rewrite open_weights_farm.md from the two replays (free; the flags are the recorded farm costs)
```

For UI development run the API (`uv run poe serve`) and `uv run poe web-dev` (Vite on port 5173
proxies `/api` and `/images`). Checks: `uv run poe check` (lint, format, types, tests; no model
call) and `uv run poe web-check` (typecheck, Vitest, build). Endpoints: [`docs/api.md`](docs/api.md).

### Live mode (spends money)

Follow [`meta-api-check`](.claude/skills/meta-api-check/SKILL.md). Real calls need
`BLADESIGHT_MODE=live` (environment or `.env`); the default mode, `replay`, answers only from the
cache and never calls a model.

```bash
cp .env.example .env   # fill META_API_KEY and META_SPEND_LIMIT_USD; never commit .env
uv run poe data                                # download, split by photo, seal the held-out split
BLADESIGHT_MODE=live uv run poe detect DJI_0382_02_04
BLADESIGHT_MODE=live uv run poe fleet process  # detect, grade and verify the farm (1.78 USD for 96 tiles over the runs behind the store, all stages)
BLADESIGHT_MODE=live uv run poe fleet run      # the agent
```

The 1.78 USD is the cost line of [`fleet_run.md`](docs/evidence/fleet_run.md).

Re-run the planning half on Muse Spark Open (needs `BASETEN_API_KEY` and `BASETEN_SPEND_LIMIT_USD`
in `.env` or the environment; no Meta key is needed because detections are reused; 2.16 USD over the runs behind
the stored replay, and 197 grading calls wait for the 15 requests/minute limit, so at least 13 minutes;
[`open_weights.md`](docs/evidence/open_weights.md)). Write to a new folder so the stored replay
stays as it is. Re-grading reads the farm tiles, so fetch them first
(`uv run python -m bladesight.data.demo`, or `uv run poe data` for the whole dataset):

```bash
BLADESIGHT_MODE=live uv run poe fleet regrade --chat-provider baseten \
  --source-dir replay --replay-dir /tmp/bladesight-open --workers 3
BLADESIGHT_MODE=live uv run poe fleet run --chat-provider baseten \
  --replay-dir /tmp/bladesight-open --run-id run-open-check
```

`BLADESIGHT_CHAT_PROVIDER=baseten` sets the same choice for every command, including
`uv run poe fleet process` (which also needs `META_API_KEY` for detection).

## Held-out

The dataset is split by source photo (seed 20261029); 15% of the photos form a sealed held-out
split whose hashes are in [`eval/heldout_manifest.sha256`](eval/heldout_manifest.sha256). It is read
only by one preregistered run: all 460 labeled held-out tiles plus 300 sampled clean tiles,
weighted so precision and false alarms describe the whole split, with the models, the code state
and the metrics frozen in [`eval/preregistration.md`](eval/preregistration.md). The result is
[`docs/evidence/eval_heldout.md`](docs/evidence/eval_heldout.md): the run was interrupted once by a
server-side 404 and resumed from the cache on the same commit, with no number seen before it
finished; that and a cost correction (8.07 USD in total) are listed under Deviations there and in
the preregistration. Held-out precision and recall are lower than on dev; the two samples are
weighted differently (see each evidence file), so compare them with care.

## Limitations (the main ones)

The full list, each with its issue, is [`docs/limitations.md`](docs/limitations.md).

- Detection is modest at box level (held-out precision 0.19, recall 0.16) and dirt is not a usable
  detector; image-level recall must be read with its false-alarm rate.
- Severity is advisory: kappa 0.12 against one non-specialist applying our own rubric, and no
  defect on the farm was graded above 3 by Muse Spark.
- `ok` means two looks of the same model family agree with enough confidence, not a validated
  grade; the verification thresholds were set on the same synthetic farm.
- The farm is synthetic, sizes are in pixels (no scale), and the position along the blade is
  usually unknown on close-up tiles.
- The open-weights comparison is one run per model; detection is not open weights.
- The public demo runs on a free plan, so a cold start stays possible despite the external
  keep-alive, and it replays stored results; live runs are not exposed publicly.

## Data

Drone inspection photos of the DTU Nordtank wind turbine (Shihavuddin & Chen, 2018, Mendeley Data,
DOI [10.17632/hd96prn3nc.2](https://doi.org/10.17632/hd96prn3nc.2), CC BY-NC 3.0), as annotated
tiles from *YOLO Annotated Wind Turbine Surface Damage* (Foster et al., 2022, CC BY-NC 4.0). No
data is stored in this repository: `uv run poe data` downloads and splits it, and the demo fetches
only its tiles. Sources, citations, the licence note and the sealed held-out split:
[`DATA.md`](DATA.md).

## Built during the hackathon

All code, prompts, rubric, evaluation and documentation here were written during the event. Notable
third-party libraries: FastAPI, pydantic, httpx, NumPy, Pillow, uvicorn (API and pipeline); React,
React Router, Vite, TypeScript, Vitest, Testing Library, Playwright, json-schema-to-typescript (web
UI and its tests); and [`meta-sam-parser`](https://pypi.org/project/meta-sam-parser/) (Meta
Platforms, SAM License) to decode SAM 3.1 output (a dependency, not vendored; its licence text ships
with the package). The web UI's fonts are self-hosted from [Fontsource](https://fontsource.org/)
packages, so the page requests no font from a third party: Figtree (text), Bricolage Grotesque
(headings) and Geist Mono (monospace), all under the SIL Open Font License 1.1. The code was written
with Claude Code
(the first scaffold of the web UI with Kiro, then rebuilt against the real API); the decisions, the
labels and the review are the author's, and every decision, spend and cut is in
[`docs/decision_ledger.md`](docs/decision_ledger.md).

## License

Code: MIT (see [`LICENSE`](LICENSE)). Data: CC BY-NC 4.0 (annotated tiles; source photos CC BY-NC 3.0), see [Data](#data) and [`DATA.md`](DATA.md).
