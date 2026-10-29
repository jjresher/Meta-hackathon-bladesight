---
name: eval-run
description: Run or change BladeSight's evaluation - detection metrics on the dev split, threshold sweeps, error galleries, severity agreement on the gold set, and the single sealed held-out run (#16) - and write the results as evidence files. Use when touching src/bladesight/eval, eval/, docs/evidence/, or when any number will be quoted in the README, UI or video.
---

# Evaluation protocol

## Splits

- **dev**: everything we look at, tune prompts and thresholds on, and show in error galleries.
- **held-out**: sealed by `eval/heldout_manifest.sha256` (issue #4). Opened **once**, in #16, after
  `eval/preregistration.md` is frozen. `poe eval --split heldout` refuses to run unless
  `ALLOW_HELDOUT=1` is set, and that variable is set only in #16.
- **gold severity set** (`eval/gold/severity.csv`, #10): 40 dev crops labelled by hand with
  `docs/rubric.md`, blind to model output. Ids only, no images.

## Metrics (fixed; changing them is a ledger entry)

- Detection: masks -> boxes, greedy match to labels by IoU. Primary IoU 0.3, also report 0.5.
  Precision, recall, F1 per class (`damage`, `dirt`) and image-level recall (any damage found).
- Threshold sweep: missed defects vs false alarms per image, as a curve (SVG).
- Severity: weighted Cohen's kappa (quadratic) and confusion matrix, model vs human.
- Uncertainty: 95% bootstrap intervals (1,000 resamples by image, fixed seed) for headline numbers.
- Cost and latency per image, from the client's spend log.

## Running

1. Make sure the cache is warm for what you will run; live calls follow `meta-api-check`.
2. `uv run poe eval --split dev [--limit N]` writes `docs/evidence/eval_dev.md` and its SVGs.
3. Every report header records: git commit, prompt versions, thresholds, model ids, split hash,
   number of images, date, cost.
4. Commit the evidence file with the code change that produced it.

## Error analysis

Group false negatives and false positives by cause (thin crack, low contrast, glare, dirt confused
with damage, defect at tile edge, blade not found). Show 3-6 examples per cause in the report using
dataset ids, never committed image files (render them at runtime or in the UI).

## The held-out run (#16 only)

1. Freeze `eval/preregistration.md`: metrics, IoU, thresholds, prompt versions, model ids.
2. Verify the manifest hash. 3. Run once with `ALLOW_HELDOUT=1`. 4. Write
`docs/evidence/eval_heldout.md` including any deviation from the pre-registration.
5. No tuning afterwards; any later change is listed as a deviation.

## Quoting numbers

A number may appear in the README, UI or video only if it is in an evidence file, with the split
and n next to it. "Recall 0.71 (held-out, n=412 defects, 95% CI 0.66-0.75)", never just "71%".
