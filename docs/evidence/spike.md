# Spike (issue #3): SAM 3.1 and Muse Spark on blade tiles

Date: 2026-11-03. Dev split only, fixed seed (`select_tiles`, seed 3: shuffle then take the first
n, so every run uses a prefix of the same order). Real calls through `bladesight.meta` following
`meta-api-check` (steps 1, 2, 3), cumulative cap 0.50 USD. Costs are the documented prices times
real usage, not invoice-checked. Code: `src/bladesight/detect/spike.py`, `spike_boxes.py`,
`spike_grade.py` (commands in each module docstring). Raw outputs were written to the gitignored
`outputs/`; images are not committed (AGENTS.md rule 2), so this file lists tile ids instead of a
gallery. **n is tiny** (14 damaged + 4 clean tiles in the comparison; no confidence intervals):
this is a go/no-go signal, not a result for the README.

## Calls and cost

| Step | Calls (live / cached) | Est. cost USD | Result |
|---|---|---|---|
| 1. SAM text, 1 tile, 5 concepts | 5 / 0 | 0.0125 | OK, real masks |
| 2. SAM text, 4 tiles, 5 concepts | 20 / 0 | 0.0500 | OK; `wind turbine blade` returned nothing on all 5 tiles |
| 3. SAM text, 25 tiles (20 damage + 5 clean), 4 defect concepts | 84 / 16 | 0.2100 | recall below |
| 4. Fallback: Muse Spark boxes + SAM box prompts, 2 then 18 tiles | 32 / 4 | 0.1058 | recall below |
| 5. Muse Spark grades 5 crops (close + context) | 5 / 0 | 0.0173 | valid JSON 5/5 |
| Total of the spike | 146 / 20 | 0.3956 | cumulative spend of all runs: 0.4125 (incl. #2) |

No retries, no 4xx. SAM box prompts (`<0f>1<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..|>,2<...`, up to 16
per request, from Meta's "segmenting with prompts" page) were accepted and returned one mask per box
(`object_id` = prompt id).

Reproduction: tiles are the first n of the seed-3 order (the 18-tile comparison is the first 14
damaged and first 4 clean). The per-method counts come from \`spike.py\` and \`spike_boxes.py\`; the
SAM-text recall on the 18-tile subset, "truth boxes touched", the union row and the box-area
statistics were computed with throwaway scripts that are not versioned (they re-read the cached
raw outputs); #9 turns them into a tested helper. The grading remarks in section 3 are a reading
of 5 replies, not a measurement.

## 1. SAM text concepts alone (20 damaged + 5 clean tiles)

Truth: 67 damage boxes (and 1 dirt box: **dirt cannot be evaluated** with this sample).

| Concept | Masks kept (the 0.3 and 0.5 thresholds gave identical sets) |
|---|---|
| `crack` | 1 |
| `leading edge erosion` | 0 |
| `surface damage` | 7 |
| `dirt` | 1 |

Damage boxes found at IoU 0.1 / 0.3 / 0.5: **9% / 6% / 6%**. Damaged tiles with any damage mask:
**6 of 20**. Clean tiles with a damage mask: 0 of 5. The 0.3 and 0.5 thresholds returned the same masks, so the
0.3/0.5/0.7 sweep only differs at 0.7 (1 mask left). `wind turbine blade` found no blade in 5 of 5
tiles (tiles are 586x371 close-ups; `rotor blade` was not retried on tiles).

## 2. Fallback: Muse Spark proposes boxes (0-1000 grid), SAM refines them (18 tiles)

Same tiles for every method: 14 damaged (45 truth boxes), 4 clean.

| Method | Damaged tiles with a prediction | Clean tiles with a prediction | Truth boxes touched by a prediction | Recall IoU 0.1 / 0.3 |
|---|---|---|---|---|
| SAM text (3 damage concepts) | 5 / 14 | 0 / 4 | - | 11% / 9% |
| Muse Spark boxes | 11 / 14 | 1 / 4 | 11 / 45 | 16% / 7% |
| Muse Spark boxes refined by SAM | 11 / 14 | 1 / 4 | - | 16% / 9% |
| **Union: refined boxes + SAM text** | **12 / 14** | 1 / 4 | 22 / 45 | 20% / 13% |

Per tile (damage only):

| Tile | Truth damage boxes | Text SAM masks (crack / erosion / surface) | Spark proposals (damage) | SAM refined |
|---|---|---|---|---|
| DJI_0273_03_01 | 4 | 1/0/0 | 3 | 3 |
| DJI_0374_04_08 | 3 | 0/0/1 | 1 | 1 |
| DJI_0168_02_05 | 12 | 0/0/1 | 2 | 2 |
| DJI_0422_05_03 | 1 | 0/0/0 | 1 | 1 |
| DJI_0382_02_04 | 5 | 0/0/0 | 4 | 4 |
| DJI_0333_02_09 | 1 | 0/0/0 | 0 | 0 |
| DJI_0764_06_04 | 2 | 0/0/0 | 1 | 1 |
| DJI_0720_04_01 | 2 | 0/0/0 | 2 | 2 |
| DJI_0972_02_05 | 1 | 0/0/1 | 0 | 0 |
| DJI_0438_05_09 | 1 | 0/0/0 | 1 | 1 |
| DJI_0267_01_02 | 1 | 0/0/0 | 1 | 1 |
| DJI_0601_01_03 | 7 | 0/0/0 | 1 | 1 |
| DJI_0589_01_01 | 1 | 0/0/0 | 0 | 0 |
| DJI_0989_05_04 | 4 | 0/0/3 | 2 | 2 |
| DJI_0994_03_04 | none (clean) | 0/0/0 | 1 | 1 |
| DJI_0195_05_08 | none (clean) | 0/0/0 | 0 | 0 |
| DJI_0260_03_02 | none (clean) | 0/0/0 | 0 | 0 |
| DJI_0680_07_02 | none (clean) | 0/0/0 | 0 | 0 |

Why box recall is low for every method: the truth boxes are tiny (median area 210 px^2, 73% under
400 px^2, i.e. about 14x14 px in a 586x371 tile) and a tile has 3 boxes on average, so IoU-matching
each one is much harder than finding the damaged region. Spark's boxes are larger (median 1020
px^2). The evaluation (#9) should therefore report **image-level recall** and a lenient overlap
criterion next to IoU 0.3 and 0.5.

## 3. Muse Spark grading (5 crops of truth boxes, throwaway rubric)

Valid JSON 5/5 on the first try (`defect_type`, `severity` 1-5, one-sentence `rationale`,
`confidence`); types and severities looked plausible (2 dirt/sev 1, 1 surface damage/sev 3, 2
crack/sev 4), confidence 0.45-0.78. This does not measure agreement with a human (that is #10).

## Decision

**GO, with the fallback.** Text concepts alone miss most damaged tiles (6/20 and 5/14). The pipeline
for #5 is: Muse Spark proposes damage and dirt boxes on the tile, SAM 3.1 turns them into masks
with box prompts, and SAM text concepts (`surface damage`, `crack`) are added to the candidates;
overlapping masks are merged. Both Meta models stay at the core. See `docs/decision_ledger.md`.
