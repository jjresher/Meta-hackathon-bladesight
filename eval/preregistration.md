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
  with `random.Random(20261104)` from the clean tiles sorted by id (`eval/heldout.py`). The reason
  is cost: the full split would cost about 25-30 USD in detection alone, over the budget.
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

## Procedure

1. `eval/preregistration.md` merged (this file); `docs/evidence/eval_heldout.md` does not exist.
2. `ALLOW_HELDOUT=1 BLADESIGHT_MODE=live uv run poe eval --split heldout`: checks the manifest,
   unseals `data/heldout/` (directory modes only), runs once, reseals it. The CLI refuses a second
   run once the evidence file exists.
3. Infrastructure failures (API errors that exhaust the client's retries) are re-run from where
   they stopped: completed calls come from the cache, so this is the same run, not a second one.
   Any such event is written under "Deviations".
4. No tuning after the run: a bug found afterwards is reported, fixed in a later PR, and the
   held-out number stays the one produced by the frozen code.

## Budget

About 760 tiles x about 0.012 USD (Spark proposal, SAM box refinement, two SAM text concepts) =
about 9-11 USD, inside the 30 USD cap; the cost is logged in the evidence file.

## Deviations

(None before the run. Filled in `docs/evidence/eval_heldout.md` if any.)
