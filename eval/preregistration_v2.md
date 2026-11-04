# Preregistration: detection v1 vs v2 on a fresh dev set (issue #22)

Written and committed **before** any v2 code exists and before either detector runs on the fresh
set. The held-out result of #16 (`docs/evidence/eval_heldout.md`) stays the official v1 result;
this experiment does not touch the held-out split and makes no held-out claim about v2.

## Question

On the held-out split, predicted damage boxes overlap half of the truth boxes but match few of
them: 0.504 of the 1,314 truth boxes are touched by some damage prediction while box recall at
IoU 0.3 is 0.164, and the 131 `fn_overlap_too_low` tiles coincide with the `fp_unmatched` ones
(`docs/evidence/eval_heldout.md`). The hypothesis is that v1's boxes are too large for the
~14x14 px dataset boxes. v2 changes only how masks become boxes (see "What v2 may change").

## The fresh set (built by `uv run python -m bladesight.eval.fresh --write`)

- Source: the dev split (`data/dev`, 11,442 tiles from 475 photos). Nothing under `data/heldout/`
  was read to build it.
- Excluded source photos (`DJI_xxxx`), 300 in total, so no fresh tile shares a photo with:
  the 300-tile seed-7 dev sample of `docs/evidence/eval_dev.md` (200 photos); the #3 spike
  (`detect.spike.select_tiles`, seed 3, first 25 damaged + 25 clean tiles: 47 photos); the gold
  severity set `eval/gold/severity.csv` (40 photos); the synthetic farm `replay/layout.json`
  (88 photos); and any `DJI_xxxx` written in a git-tracked text file at commit `7c92e77`
  (191 photos; catches photos shown in evidence, tests or the UI). The sets overlap.
- Remaining pool: 4,086 dev tiles from 197 photos, 749 of them labeled.
- Draw: `runner.sample_tiles` with **seed 20261122**: two thirds labeled tiles, one third clean
  (no box), like the dev sample. Result: **300 tiles** (200 labeled, 170 with damage boxes,
  100 clean), 490 damage boxes, 141 source photos.
- Manifest: `eval/fresh_v2_manifest.sha256` (one `sha256  tile_id` line per tile file
  `data/dev/img/<tile_id>.png`), sha256 of the manifest file
  **`46ec38864cc90dd9cb7ce2eb7dd6e1e9ce0bf577c48ef187d9afb69d04e62610`**. The run verifies every
  file against it before evaluating and aborts on a mismatch.

## Reference: v1 on the held-out split (quoted from `docs/evidence/eval_heldout.md`)

| Metric (damage, held-out, 760 tiles weighted) | v1 |
|---|---|
| Precision at IoU 0.3 | 0.187 (95% CI 0.152-0.222) |
| Recall at IoU 0.3 | 0.164 (95% CI 0.136-0.194) |
| F1 at IoU 0.3 | 0.175 |
| Recall at IoU 0.5 | 0.134 |
| Image-level recall | 0.698 over 368 tiles |
| False-alarm rate on tiles with no box | 0.240 over 300 tiles |
| Truth boxes touched by any prediction | 0.504 of 1,314 |

These are a reference only; the comparison below is v1 vs v2 on the same fresh tiles.

## What v2 may change

Development happens **only** on the 300 seed-7 dev tiles and their cached model answers. v2 may
change the post-processing that turns SAM masks into boxes (tight mask boxes, connected
components, size filters, merge rules) and, only if a cheap dev check shows it helps, add
zoomed re-proposals. Models, prompts and the metrics stay as in v1 unless the v2 description
recorded before the run says otherwise. v1 stays runnable unchanged (`--detector v1`, the default).

Before the fresh run, an addendum to this file records the exact v2 definition and the commit
both runs use (the code is frozen at that commit; the run refuses uncommitted changes in `src/`).

## Metrics (computed by `bladesight.eval`, unchanged from v1)

For each detector on the 300 fresh tiles (unweighted): damage precision, recall and F1 at IoU 0.3
(primary) and 0.5, one-to-one greedy matching highest score first, every kept detection counted;
dirt the same; image-level damage recall; damage false-alarm rate on the 100 clean tiles (share of
clean tiles with at least one damage prediction); share of truth boxes touched by any damage
prediction; the threshold sweep; the error gallery; cost from the call records.

Uncertainty: stratified bootstrap over tiles (labeled and clean tiles resampled separately, 1,000
resamples, seed 20261029) of each metric and, **paired** (the same resampled tiles for both
detectors), of the differences v2 - v1 in damage F1 at IoU 0.3 and in the false-alarm rate. Tiles
of one photo are correlated, so the intervals are probably a little too narrow.

## Success criterion (fixed now)

**v2 wins if and only if** (a) its damage F1 at IoU 0.3 on the fresh set is higher than v1's,
**and** (b) its false-alarm rate on the fresh set's clean tiles is not more than 5 percentage
points above v1's (v2 - v1 <= 0.05). Otherwise v2 loses. The bootstrap intervals of the
differences are reported but do not enter the criterion. A loss is reported as a negative result
in `docs/evidence/eval_fresh_v2.md` and the pipeline default stays v1.

## Procedure

1. This file and the manifest are committed and pushed before any fresh-set run.
2. v2 is chosen on the dev sample only; the addendum (v2 definition + frozen commit) is committed.
3. `BLADESIGHT_MODE=live uv run poe eval --split fresh` runs v1 and v2 **once each** on the fresh
   tiles from that clean commit (uncached calls are real; v2 reuses v1's Spark and SAM answers
   wherever its calls are the same). It writes `docs/evidence/eval_fresh_v2.{md,json}` with both
   metric sets, the paired differences, the verdict, the cost, the commit and the run timestamp,
   and refuses a second run once that evidence exists.
4. Infrastructure failures (API errors after retries, the spend cap) are resumed with the same
   command from the cache, as in #16; that is the same run. No tuning after the run.

## Budget

v1 on 300 tiles at the dev rate (0.0106 USD per tile, 3.18 USD for 300) is about 3.2-4.2 USD;
v2 adds 0 USD if it only changes post-processing. Cap for this experiment: 8 USD in total.

## Addendum before the run (2026-11-04): v2 as frozen

Written after choosing v2 on the dev sample and before either detector ran on any fresh tile.
Nothing above changed.

- **v2** = `bladesight.detect.pipeline.V2` = `PostConfig(split_components=True, min_area_px=40,
  min_part_share=0.1, merge="nms")`: the same model calls as v1 (Spark proposals, SAM box
  refinement, the two SAM text concepts, no blade call); each mask is split into its
  8-connected parts, parts under 40 px or under 0.1 of the mask's largest part are dropped, and
  same-label masks with mask IoU >= 0.5 are suppressed (the higher score is kept, not unioned).
  One box per part. v1 is `PostConfig()` (unchanged, still the default).
- Chosen from the dev variant table `docs/evidence/eval_fresh_v2_dev.md` (seed-7 dev sample,
  cached answers, 0 USD): v1 F1 0.276 -> v2 F1 0.308 at IoU 0.3 on dev, same image recall
  (0.767) and false-alarm rate (0.210). Quadrant zoom was checked on 20 dev tiles (0.3475 USD),
  gave the same F1 and was not adopted, so v2 adds no model call and its fresh pass should be
  served entirely from the cache v1's pass fills (0 USD).
- **Frozen commit**: the commit that adds this addendum. The run refuses uncommitted changes in
  `src/`, `pyproject.toml`, `uv.lock`, this file and the manifest, and records
  `git rev-parse HEAD` in `docs/evidence/eval_fresh_v2.md`.
- Command: `BLADESIGHT_MODE=live uv run poe eval --split fresh` (v1 pass, then v2 pass, in one
  process); it refuses a second run once `docs/evidence/eval_fresh_v2.md` exists unless
  `ALLOW_FRESH_RERUN=1` is set, which would be listed as a deviation.

## Deviations

Added after the run (2026-11-04); nothing above changed. One: on one tile (`DJI_0248_08_02`)
v1's Muse Spark answer was not cacheable (status not `completed`), so the v2 pass called it again
live and the two detectors saw different answers there; a free replay with the same answer for
both gives identical metrics and the same verdict. Details in `docs/evidence/eval_fresh_v2.md`.
