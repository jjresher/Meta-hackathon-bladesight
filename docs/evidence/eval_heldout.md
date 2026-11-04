# Detection evaluation (heldout)

Command: `uv run poe eval --split heldout`. Split: `heldout`. Tiles: 760 (368 with damage boxes, 300 with no box at all). Cost: 8.0727 USD for the whole run (documented prices, not invoice-checked; corrected, see Deviations).

Preregistered sample of the held-out split: all 460 labeled tiles plus 300 of its 1568 clean tiles (seed 20261104); each clean tile weighs 5.23, so precision, false positives and false alarms per image are scaled to the whole split. Recall and image-level rates are not affected. Unweighted damage counts at IoU 0.3: TP 216, FP 529, FN 1098. Preregistration sha256 cef25034242668ce81e7e27252e64330efc53bd81498f664fa47017439b4f3e9. Code commit ade7d9cc469a845ca671b56e50d3750321faee6b (no uncommitted changes in src/, pyproject.toml, uv.lock or the preregistration). Models muse-spark-1.3 and sam-3.1, reasoning effort low, store false (checked against the preregistered values before the run).

## Box matching (IoU 0.3 primary, 0.5 also reported)

| Class | TP | FP | FN | Precision (95% CI) | Recall (95% CI) | F1 | Recall IoU 0.5 |
|---|---|---|---|---|---|---|---|
| damage | 216.0 | 939.0 | 1098.0 | 0.187 (0.152-0.222) | 0.164 (0.136-0.194) | 0.175 | 0.134 |
| dirt | 47.0 | 879.2 | 60.0 | 0.051 (0.036-0.067) | 0.439 (0.345-0.526) | 0.091 | 0.318 |

Intervals: bootstrap over tiles (1000 resamples, seed 20261029); tiles of one photo are correlated, so the intervals are probably a little too narrow. Precision is reported as 0 when there are no predictions.

## Image level and lenient overlap (damage)

- Image-level recall (a damaged tile has at least one damage prediction): **0.698** over 368 tiles.
- False-alarm rate on tiles with no box at all: **0.240** over 300 tiles.
- Truth boxes touched by any damage prediction (any overlap): **0.504** of 1314.

## Threshold sweep (damage, IoU 0.3)

| Score threshold | Recall | Precision | False alarms per image |
|---|---|---|---|
| 0 | 0.164 | 0.187 | 0.463 |
| 0.3 | 0.163 | 0.198 | 0.427 |
| 0.5 | 0.161 | 0.220 | 0.368 |
| 0.6 | 0.141 | 0.266 | 0.252 |
| 0.7 | 0.104 | 0.360 | 0.120 |
| 0.8 | 0.053 | 0.410 | 0.049 |
| 0.9 | 0.010 | 0.214 | 0.024 |

![Damage recall vs false alarms](eval_heldout_sweep.svg)

## Error gallery (tile ids, damage; crops are never committed)

- `fn_no_prediction` (111): DJI_0006_02_04, DJI_0006_02_05, DJI_0006_04_05, DJI_0015_03_03, DJI_0016_03_03, DJI_0018_02_04, DJI_0025_04_03, DJI_0025_04_06, DJI_0026_02_03, DJI_0026_02_04, DJI_0026_03_02, DJI_0026_04_06 ...
- `fn_prediction_elsewhere` (87): DJI_0025_04_07, DJI_0039_04_05, DJI_0039_05_06, DJI_0040_05_05, DJI_0040_05_06, DJI_0089_02_03, DJI_0094_01_03, DJI_0099_01_02, DJI_0110_01_04, DJI_0112_01_04, DJI_0116_07_05, DJI_0116_07_07 ...
- `fn_overlap_too_low` (131): DJI_0006_02_06, DJI_0006_03_05, DJI_0012_03_05, DJI_0015_03_04, DJI_0016_03_04, DJI_0018_03_04, DJI_0020_03_04, DJI_0025_03_02, DJI_0025_03_03, DJI_0026_03_03, DJI_0039_04_04, DJI_0040_04_04 ...
- `fp_clean_tile` (72): DJI_0012_02_07, DJI_0012_02_08, DJI_0015_03_05, DJI_0016_02_03, DJI_0016_06_03, DJI_0018_02_05, DJI_0018_02_07, DJI_0020_03_05, DJI_0020_06_04, DJI_0025_06_03, DJI_0040_08_05, DJI_0100_05_06 ...
- `fp_unmatched` (224): DJI_0006_02_06, DJI_0006_03_05, DJI_0012_03_05, DJI_0015_03_04, DJI_0016_03_04, DJI_0018_03_04, DJI_0020_03_04, DJI_0025_03_02, DJI_0025_03_03, DJI_0025_04_07, DJI_0026_03_03, DJI_0039_04_04 ...

Prompt versions: {'propose': 'detect/v1', 'assess': 'assess/v1', 'verify': 'verify/v1'}. IoU levels computed: [0.1, 0.3, 0.5].

## Deviations

1. **Interrupted once, resumed from the cache (2026-11-03).** The first segment ended at 21:46:16
   (UTC-5) with `model_not_found` (HTTP 404) from the Muse Spark endpoint, the same models that had
   answered 1,381 calls before (358 Muse Spark, 1,023 SAM) and answered every call after. The same command was repeated at
   21:46:45 on the same commit with nothing changed, as `eval/preregistration.md` step 5 allows; the
   cache replayed the finished calls (no real call repeated). No number was computed, written or seen
   before the run completed. Details: "Deviations" in `eval/preregistration.md`.
2. **The cost above is corrected.** The tool wrote 3.8623 USD in the first version of this file and
   in `eval_heldout.json`, because it sums the call records of the restarted process only. The spend
   log (`.spend/spend_log.jsonl`, Spark and SAM calls between 20:28 and 22:51) gives 4.2073 USD for
   the first segment and 3.8654 USD for the second: 8.0727 USD in total. The second segment includes
   two minimal probe calls (one Muse Spark chat, one SAM segment, about 0.0031 USD) made at
   21:46:34-35 to check that the models answered before restarting; the tool's 3.8623 USD is what
   the restarted process itself spent. The 112 Muse Spark Open calls of issue #15 in the same
   window are not counted (within the preregistered
   "about 8 USD, ceiling 11"). Only the `cost_usd` field of the JSON and the cost sentence of this
   file were edited; no metric was touched. The generated versions had sha256
   `277e90736eaf26a7f14573c67d53a8f7fb9adc0f403704f0bdf86d4b29c55ce1` (json) and `7d498f382143b6b7b39849b8c26010d2e3d4c7cd025c5f4bf171ca6861500c6a` (md).
