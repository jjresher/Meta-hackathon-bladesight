# Severity assessment (issue #7): 10 dev defects graded by Muse Spark

Date: 2026-11-03. `uv run python -m bladesight.assess <tiles>` (`src/bladesight/assess/`): the 10
first defects of 5 dev tiles (detections replayed from the #5 cache, measured by `measure/`), each
graded from a close crop and a wider context crop with `assess/prompts/v1.md` and
`docs/rubric.md` v1 (`muse-spark-1.3`, `reasoning.effort=low`, `store=false`, `max_tokens` 1500).
`BLADESIGHT_MODE=live` through `bladesight.meta` (`meta-api-check`): **10 live calls, 25 replayed
(detection), 0 retries, 0.0424 USD** (documented prices, not invoice-checked). The crops and the
JSON are in the gitignored `outputs/assess/` (images are not committed, AGENTS.md rule 2).

**Valid JSON 10/10 on the first try** (no repair retry was needed; the retry path is covered by
tests on the stub). Review below is a first pass by the agent from the crops, not a measurement:
agreement with a human is the job of the gold set (#10).

| Defect | Source | Type | Severity | Confidence | Rationale (shortened) | First-pass review |
|---|---|---|---|---|---|---|
| DJI_0273_03_01/d1 | text `crack` | crack | 2 | 0.25 | faint thin line, overexposed crops | low confidence looks right: a large mask from a text concept, possibly a false alarm (not checked) |
| DJI_0273_03_01/d2 | box | dirt | 1 | 0.30 | tiny dark speck | plausible; crop is very small |
| DJI_0273_03_01/d3 | box | dirt | 1 | 0.35 | tiny dark specks | plausible |
| DJI_0273_03_01/d4 | box | dirt | 1 | 0.35 | tiny dark streak, no paint loss | plausible (small dark marks like these are often boxed as damage in the dataset; not checked for this tile) |
| DJI_0374_04_08/d1 | box | surface_damage | 3 | 0.45 | reddish-brown patch, flaking paint | plausible |
| DJI_0168_02_05/d1 | box | other | 1 | 0.15 | too small and blurry to grade | honest abstention |
| DJI_0168_02_05/d2 | box | leading_edge_erosion | 3 | 0.60 | linear paint loss along the edge, substrate showing | agrees with the context crop (paint loss next to the hub) |
| DJI_0422_05_03/d1 | box | other | 1 | 0.25 | tiny dark smudge | plausible |
| DJI_0422_05_03/d2 | box | surface_damage | 3 | 0.45 | irregular paint loss, substrate exposed | plausible |
| DJI_0382_02_04/d1 | box | other | 1 | 0.25 | extremely blurry spot | the close crop is a 24 px region upscaled to 256 px: genuinely unreadable |

What this shows, and what it does not:

- The grades are coherent with the rubric and the confidence tracks how readable the crop is
  (0.15-0.35 on tiny crops, 0.45-0.60 where a patch is visible). Verification (#8) will route the
  low-confidence ones to `needs_review`.
- Severity never exceeded 3 in these 10 defects, so the serious end of the rubric (4-5) is
  untested here; the spike's probe (`spike.md`, section 3) gave severity 4 on two crack crops
  graded with a throwaway rubric.
- Tiny defects are the weak spot: the close crop enlarges a few pixels, and the model says so.
  A larger minimum close-crop size (`crops.MIN_SIDE`) is the obvious next change; it was not made
  because the spend cap left no budget to re-measure it.
- All 10 measurements had `position: unknown` (no blade was found on these close-up tiles), so the
  "position along the blade" fact in the prompt was never exercised with a real value.
- `crops.crop_png` stretches the region to a 256x256 square, so thin cracks and edge-clipped
  regions are distorted, and the context crop (3x padding) covers most of the 586x371 tile squashed
  to a square. This probably contributes to tiny defects grading as unreadable; padding to a square
  instead of stretching is the next change (not made: no budget to re-measure).
