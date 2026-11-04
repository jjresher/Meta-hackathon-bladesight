# Detection v1 vs v2 on a fresh dev set (issue #22)

Command: `BLADESIGHT_MODE=live uv run poe eval --split fresh`. Commit `9cfd7bc1ad8516ad0801b6ea13dbcebef45e5411`. Run 2026-11-04T08:44:50+00:00 to 2026-11-04T09:42:25+00:00 (provider `meta`). Preregistration `eval/preregistration_v2.md` sha256 `a05e986f111ba6639af5c7b1f14be912ea4dbb47c3c8eafd3bdf14c9351b55e3`; manifest `eval/fresh_v2_manifest.sha256` sha256 `46ec38864cc90dd9cb7ce2eb7dd6e1e9ce0bf577c48ef187d9afb69d04e62610`.

Tiles: 300 fresh dev tiles (170 with damage boxes, 100 with no box, 490 damage boxes), from source photos that share nothing with the dev sample v2 was tuned on. Unweighted. Each detector ran once.

## Verdict: **v2 wins** (preregistered criterion)

- (a) damage F1 at IoU 0.3: v1 0.224, v2 0.250 -> higher;
- (b) false-alarm rate on tiles with no box: v1 0.210, v2 0.210 -> within +0.05 of v1.

Paired bootstrap of v2 - v1 (same resampled tiles, labeled and clean tiles resampled separately, 1000 resamples, seed 20261029; reported, not part of the criterion): damage F1 at IoU 0.3 +0.026 (95% CI +0.006 to +0.045); false-alarm rate +0.000 (95% CI +0.000 to +0.000). Tiles of one photo are correlated, so the intervals are probably a little too narrow.

## Both detectors on the fresh set

| Metric | v1 | v2 |
|---|---|---|
| Damage precision, IoU 0.3 (95% CI) | 0.286 (0.235-0.342) | 0.307 (0.253-0.364) |
| Damage recall, IoU 0.3 (95% CI) | 0.184 (0.138-0.238) | 0.210 (0.159-0.268) |
| **Damage F1, IoU 0.3** (95% CI) | 0.224 (0.176-0.276) | 0.250 (0.199-0.303) |
| Damage recall, IoU 0.5 | 0.135 | 0.153 |
| Damage F1, IoU 0.5 | 0.164 | 0.182 |
| Dirt F1, IoU 0.3 | 0.082 | 0.073 |
| Image-level damage recall | 0.729 | 0.729 |
| **False-alarm rate, tiles with no box** | 0.210 | 0.210 |
| Truth boxes touched by any prediction | 0.522 | 0.510 |
| Damage counts, IoU 0.3 | TP 90, FP 225, FN 400 | TP 103, FP 232, FN 387 |
| Cost USD (calls) | 3.1667 ({'live': 1098, 'cache': 0}) | 0.0068 ({'live': 1, 'cache': 1097}) |

Full reports (sweep, error gallery): [v1](eval_fresh_v2_v1.md), [v2](eval_fresh_v2_v2.md). Cost: documented prices from the client's call records, not invoice-checked.

## What v1 and v2 are

Same model calls (Muse Spark `detect/v1` proposals, SAM 3.1 box refinement, the `surface damage` and `crack` concepts, no blade call). They differ only in how masks become boxes (`bladesight.detect.pipeline.PostConfig`):

- **v1** (frozen #16 pipeline): masks under 20 px dropped, same-label masks with mask IoU >= 0.5 merged by union, one box per mask (its tight bounding box).
- **v2**: every mask split into its 8-connected parts; parts under 40 px or under 0.1 of the mask's largest part dropped; same-label masks with IoU >= 0.5 suppressed (the lower score is dropped, not unioned); one box per part.

## How v2 was chosen

On the 300-tile seed-7 dev sample only, from cached model answers (0 USD): see [eval_fresh_v2_dev.md](eval_fresh_v2_dev.md).

## Deviations

1. **One Muse Spark call of the v1 pass was not cached, so the v2 pass repeated it live.**
   The v2 pass made 1 live call (0.0068 USD) instead of 0: the Spark proposal for tile
   `DJI_0248_08_02` (6 dataset boxes). The client caches only answers whose status is
   `completed` (`bladesight.meta.client`), so v1's answer for that tile was used but not stored,
   and v2 got a fresh answer (status completed, 1,502 output tokens). On that one tile the two
   detectors therefore post-processed different Spark answers. Check after the run, free (replay
   mode, 0 live calls): re-running v1 and v2 from the cache, where both now see the same answer
   for that tile, gives exactly the metrics above (v1 TP 90, FP 225, FN 400; F1 0.224 vs 0.250;
   false alarms 0.210 vs 0.210), and both detectors predict nothing on that tile either way. The
   verdict does not depend on it.
2. **Run timestamps above are UTC** (03:44:50 to 04:42:25 UTC-5).
3. This Deviations section was added by hand after the run, and blank lines left by the
   generator were collapsed; no number was edited. The generated file had sha256 `260951bbd61c585cbc85122c8022b156b8ee6fd98a6c003cd37113c27f2d3a91`.
4. Cost of the whole experiment (client call records, documented prices): fresh run 3.1667 USD
   (v1) + 0.0068 USD (v2) = 3.1735 USD; plus the quadrant-zoom dev check 0.3475 USD
   (`eval_fresh_v2_dev.md`); 3.5210 USD in total.
