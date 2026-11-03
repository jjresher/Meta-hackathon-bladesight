# Detection (issue #5): five dev tiles through `uv run poe detect`

Date: 2026-11-03. Pipeline: `src/bladesight/detect/pipeline.py` (Muse Spark box proposals -> SAM 3.1
box prompts, plus SAM text `surface damage` and `crack`, plus the `wind turbine blade` concept;
tiny masks dropped, overlapping masks of one label merged, masks off the blade dropped only when a
blade was found). Dev tiles, `BLADESIGHT_MODE=live`, through `bladesight.meta` (the 4 other calls
per tile were replayed from the cache written by the #3 spike). Costs are documented prices times
real usage, not invoice-checked. Overlay PNGs were written to the gitignored `outputs/detect/`
(images are not committed, AGENTS.md rule 2); one was checked by eye.

| Tile | Spark proposals | Defects kept | Sources | Blade | Live calls | Cost USD | Seconds |
|---|---|---|---|---|---|---|---|
| DJI_0273_03_01 | 3 | 4 (damage) | 3 box prompt, 1 text | not found | 1 | 0.0025 | 1.3 |
| DJI_0374_04_08 | 1 | 1 (damage) | 1 box prompt | not found | 1 | 0.0025 | 1.4 |
| DJI_0168_02_05 | 2 | 2 (damage) | 2 box prompt | not found | 1 | 0.0025 | 1.8 |
| DJI_0422_05_03 | 2 | 2 (1 dirt, 1 damage) | 2 box prompt | not found | 1 | 0.0025 | 1.4 |
| DJI_0382_02_04 | 4 | 4 (damage) | 4 box prompt | not found | 2 | 0.0050 | 1.9 |

- **Cost per image** (all calls live, from the #3 spike prices): Muse Spark box proposal and SAM
  box refinement about 0.0074 USD, two SAM text concepts 0.0050, blade concept 0.0025: **about
  0.015 USD per tile**. Dev evaluation on 300 tiles is therefore about 4.5 USD for detection alone.
- **Runtime**: 1.3 to 1.9 s per tile in the table, with one live call and four replayed from the
  cache; a fully cold run (five sequential calls) was not timed.
- The blade concept found no blade on any of these 5 tiles (0/10 with the spike's 5), so the blade
  filter did not act; blade-relative measures (#6) fall back to the tile.
- Observed on DJI_0382_02_04 (checked by eye): the four masks sit along a paint crack line next to
  a bolted fixture, which is what the dataset annotators boxed in similar tiles. DJI_0273_03_01's
  `d1` (a 1327 px mask from the `crack` concept, score 0.58) looks like a false alarm: not
  measured, left for #8 and #9.
