# Choosing detection v2 on the dev sample (issue #22)

Command: `BLADESIGHT_MODE=replay uv run python -m bladesight.eval.fresh --dev-table`. Commit `78dc6a82ec80c7c8750fdec90d3c2e8ce8dcd3e6`. The 300-tile seed-7 dev sample of `eval_dev.md` (the tiles v1 was tuned on; 176 with damage boxes, 100 with no box), damage class, IoU 0.3, unweighted. Model answers replayed from the cache: 0 live and 1112 cached calls, 0 USD. The first row reproduces `eval_dev.md` (TP 137, FP 237, FN 482).

Hypothesis (from `eval_heldout.md`): boxes are too large. On this dev sample, for the 207 damage truth boxes that some v1 box overlaps without matching them, the best-overlapping v1 box is a median 9.5 times the truth box's area (88% are larger).

| Variant | TP | FP | FN | Precision | Recall | **F1** | Recall IoU 0.5 | False-alarm rate | Image recall | Touched |
|---|---|---|---|---|---|---|---|---|---|---|
| v1 (frozen #16) | 137 | 237 | 482 | 0.366 | 0.221 | 0.276 | 0.170 | 0.210 | 0.767 | 0.556 |
| v1 merge=nms | 139 | 235 | 480 | 0.372 | 0.225 | 0.280 | 0.176 | 0.210 | 0.767 | 0.538 |
| v1 drop masks > 2000 px | 104 | 169 | 515 | 0.381 | 0.168 | 0.233 | 0.129 | 0.120 | 0.585 | 0.372 |
| split parts | 164 | 372 | 455 | 0.306 | 0.265 | 0.284 | 0.212 | 0.210 | 0.767 | 0.554 |
| split parts, merge=nms | 166 | 370 | 453 | 0.310 | 0.268 | 0.287 | 0.216 | 0.210 | 0.767 | 0.546 |
| split, min 40 px, nms | 166 | 315 | 453 | 0.345 | 0.268 | 0.302 | 0.216 | 0.210 | 0.767 | 0.546 |
| split, min 80 px, nms | 162 | 256 | 457 | 0.388 | 0.262 | 0.312 | 0.210 | 0.210 | 0.756 | 0.535 |
| split, min 120 px, nms | 154 | 232 | 465 | 0.399 | 0.249 | 0.306 | 0.200 | 0.210 | 0.733 | 0.523 |
| split, min 40 px, share 0.1, nms (= v2) | 156 | 237 | 463 | 0.397 | 0.252 | 0.308 | 0.205 | 0.210 | 0.767 | 0.540 |
| split, min 40 px, max 3 parts, nms | 161 | 276 | 458 | 0.368 | 0.260 | 0.305 | 0.208 | 0.210 | 0.767 | 0.541 |
| split after 3 px erosion, min 40 px, nms | 177 | 460 | 442 | 0.278 | 0.286 | 0.282 | 0.208 | 0.210 | 0.767 | 0.522 |
| split, drop parts > 2000 px | 128 | 307 | 491 | 0.294 | 0.207 | 0.243 | 0.165 | 0.160 | 0.636 | 0.414 |

Reading: splitting masks into connected parts lifts recall (scattered concept masks become several boxes), and the fragments it creates are mostly tiny, so a 40 px floor and a share-of-largest-part floor recover precision; larger floors start to cost image-level recall, and an area ceiling or erosion hurts. The differences between the best rows are within noise; v2 was picked as the simplest row near the top that keeps v1's image recall and false-alarm rate.

Quadrant zoom, checked once on 2026-11-03 (23:43-23:55 UTC-5) and not adopted: Muse Spark re-proposed boxes on each 2x-upscaled quadrant of the first 20 labeled tiles of this sample, SAM refined them on the full tile, the concept masks were kept and the v2 post-processing applied. Damage at IoU 0.3 on those 20 tiles: whole-tile proposals TP 12, FP 19, FN 37 (F1 0.300); quadrant proposals TP 15, FP 36, FN 34 (F1 0.300). Same F1 at about 2.5 times the proposal cost (100 live calls, 0.3475 USD from the client's call records), so zoom stayed out of v2. The check ran from an ad-hoc script that is not part of the package (its numbers are recorded only here).
