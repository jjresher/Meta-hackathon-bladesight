# Preregistration: the single held-out evaluation (issue #16)

Written and frozen **before** the held-out run. After the PR that adds this file is merged, no
code, prompt, threshold or metric below changes until the run is done; any later change is listed
under "Deviations" in `docs/evidence/eval_heldout.md`. The run records this file's sha256 and the
git commit it ran on.

## What is evaluated

The detection pipeline `bladesight.detect.pipeline.detect_tile` exactly as merged at the freeze:

1. Muse Spark `muse-spark-1.3` (`reasoning.effort=low`, `store=false`) proposes damage and dirt
   boxes with the prompt in `src/bladesight/detect/propose.py` (`PROMPT`);
2. SAM 3.1 `sam-3.1` refines them with box prompts (up to 16 per request) and also runs the text
   concepts `surface damage` and `crack`;
3. masks under 20 px are dropped and same-label masks with IoU >= 0.5 are merged keeping the
   highest score; the blade concept is **not** called (`with_blade=False`).

Severity grading and verification (`assess/v1`, `verify/v1`, rubric `v1`, the verification
thresholds in `verify.THRESHOLDS`) are frozen at the same commit but are **not** evaluated on the
held-out split: their only quantitative check is agreement with the human gold set on dev crops
(#10). The held-out split makes no claim about severity or abstention quality.

## Data and sampling (no held-out file was read to write this)

- Split: `eval/heldout_manifest.sha256` (manifest sha256 in `eval/split_summary.json`): 2,028
  tiles from 83 source photos, of which 460 have dataset boxes. The manifest hash of every file is
  verified before the run; a mismatch aborts it.
- Sample: **all 460 labeled tiles** plus **300 clean tiles** (tiles with no dataset box) drawn
  with `random.Random(20261104)` from the clean tiles sorted by id (`src/bladesight/eval/heldout.py`). The reason
  is cost: at the dev rate (3.1759 USD for 300 tiles = 0.0106 USD per tile) the full 2,028 tiles would cost about 21.5 USD, too much of the remaining budget; the sampled 760 tiles cost about 8 USD.
- Weights: each sampled clean tile stands for (clean tiles in the split / 300) clean tiles; labeled
  tiles weigh 1. Precision, false positives and false alarms per image are computed with these
  weights, i.e. scaled to the whole held-out split. Recall, image-level recall and the false-alarm
  rate **on clean tiles** are unaffected by the weights. Unweighted counts are also reported.

## Metrics (all computed by `bladesight.eval`, tested on toy boxes)

Primary: damage precision, recall and F1 at IoU >= 0.3, predictions matched one-to-one to dataset
boxes highest score first, with every kept detection counted (no extra score threshold).
Secondary, all reported whether or not they look good:

- the same for IoU 0.5 and for the `dirt` class;
- image-level damage recall (a damaged tile has at least one damage prediction), the damage
  false-alarm rate on clean tiles, and the share of truth boxes touched by any damage prediction;
- the score-threshold sweep (0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9) with weighted false alarms per image;
- 95% intervals: stratified bootstrap over tiles (labeled and clean tiles resampled separately,
  1000 resamples, seed 20261029). Tiles of one photo are correlated, so the intervals are probably
  a little too narrow (stated in the report);
- the error gallery as tile ids by cause (no crops are committed);
- the cost of the run, from the spend log.

Reading the numbers: 73% of the dataset boxes are under 400 px^2, so box-level IoU recall is
expected to be low for any detector; the image-level numbers are the ones that describe usefulness.
No result is hidden or replaced because it is poor.

## Frozen settings and how the run enforces them

The CLI refuses to start (exit 2, nothing unsealed) unless all of these hold, and records them in
`docs/evidence/eval_heldout.md`:

- `META_CHAT_MODEL` = `muse-spark-1.3`, `META_SAM_MODEL` = `sam-3.1`, `META_REASONING_EFFORT` =
  `low`, `META_STORE` = false (the defaults; a different value in `.env` aborts the run);
- no uncommitted change in `src/`, `pyproject.toml`, `uv.lock` or this file (`git status`); the
  recorded commit is `git rev-parse HEAD` of that clean tree;
- `--provider meta` and none of `--stem`, `--cost-usd` or a different `--out`; the evidence path
  and the manifest are resolved from the repository root, not the working directory;
- the manifest file's own hash and line count equal `eval/split_summary.json`, and every
  held-out file matches its hash, all checked before any label is read.

## Procedure

1. `eval/preregistration.md` merged (this file); `docs/evidence/eval_heldout.md` does not exist.
2. `META_SPEND_LIMIT_USD` (cumulative, per provider, summed from `.spend/spend_log.jsonl`) must
   cover the run: 30 USD was set by the human on 2026-11-03 and about 5.5 USD was already spent,
   against a budget of about 8 USD (ceiling 11). If the cap stops the run midway, the limit is
   raised and the same command is repeated: the cache replays every finished call, so it is the
   same run, not a second one.
3. `ALLOW_HELDOUT=1 BLADESIGHT_MODE=live uv run poe eval --split heldout`: checks everything
   above, unseals `data/heldout/` (directory modes only), runs once, reseals it, and only then
   writes the evidence. The CLI refuses another run once the evidence file exists.
4. If the process is killed (the `finally` does not run) the directory stays unsealed:
   `uv run python -m bladesight.eval --reseal-only` restores mode 000, and the incident is
   listed under Deviations.
5. Infrastructure failures (API errors that exhaust the client's retries, the spend cap) are
   resumed as in step 2. A **code bug** found mid-run may be fixed only if the fix does not change
   the result of any tile already completed (the cache guarantees finished calls are not redone);
   the fix and the commit are listed under Deviations. Otherwise the run is reported as failed
   and not repeated.
6. No tuning after the run: a bug found afterwards is reported, fixed in a later PR, and the
   held-out number stays the one produced by the frozen code.

## Budget

About 760 tiles x 0.0106 USD (the dev rate: Spark proposal, SAM box refinement, two SAM text
concepts) = about 8 USD, with 11 USD as a ceiling; the cost is logged in the evidence file from
the spend log.

## Deviations

(None before the run. Filled in `docs/evidence/eval_heldout.md` if any.)
