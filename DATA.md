# Data

BladeSight is evaluated on drone inspection photos of wind turbine blades. **No image, label or
archive is stored in this repository**: `uv run poe data` downloads and builds everything under
`data/` (gitignored, and blocked by the pre-commit hook).

## Sources and licences

| | Original photos | Annotated tiles (what we download) |
|---|---|---|
| Name | DTU - Drone inspection images of wind turbine | YOLO Annotated Wind Turbine Surface Damage |
| Authors | ASM Shihavuddin, Xiao Chen (2018) | Ashley Foster, Oscar Best, Mario Gianni, Asiya Khan, Kerry Collins, Sanjay Sharma, ASM Shihavuddin, Xiao Chen (2022) |
| Where | Mendeley Data, DOI [10.17632/hd96prn3nc.2](https://data.mendeley.com/datasets/hd96prn3nc/2) | [Kaggle](https://www.kaggle.com/datasets/ajifoster3/yolo-annotated-wind-turbines-586x371); downloaded from the [Dataset Ninja](https://datasetninja.com/yolo-annotated-wind-turbine-surface-damage) (Supervisely) export |
| Licence | **CC BY-NC 3.0** (Mendeley API, `data_licence`) | **CC BY-NC 4.0** |
| Content | Photos of the same Nordtank turbine (DTU, Roskilde) from the 2017 and 2018 inspections | ~13.5k tiles of 586x371 px cut from those photos, boxes for **damage** and **dirt** |

**Licence discrepancy.** The original photos are CC BY-NC 3.0 and the annotated derivative is
CC BY-NC 4.0. Both are attribution, non-commercial licences; BladeSight is a non-commercial
hackathon project, credits both works here and in the README, and redistributes neither.

Please cite both:

```bibtex
@dataset{shihavuddin2018dtu,
  author = {Shihavuddin, ASM and Chen, Xiao},
  title  = {DTU - Drone inspection images of wind turbine},
  year   = {2018},
  publisher = {Mendeley Data},
  version = {2},
  doi    = {10.17632/hd96prn3nc.2}
}
@dataset{foster2022yolo,
  author = {Foster, Ashley and Best, Oscar and Gianni, Mario and Khan, Asiya and Collins, Kerry
            and Sharma, Sanjay and Shihavuddin, ASM and Chen, Xiao},
  title  = {YOLO Annotated Wind Turbine Surface Damage},
  year   = {2022},
  url    = {https://www.kaggle.com/datasets/ajifoster3/yolo-annotated-wind-turbines-586x371}
}
```

## Build

```bash
uv run poe data   # download (2.8 GB, resumable), convert, split, seal, verify the manifest
```

1. **Download** the Dataset Ninja tar into `data/raw/` with httpx (resumes a partial `.part`
   file), check its size and sha256 (`ARCHIVE_SHA256` in `src/bladesight/data/build.py`).
2. **Convert** each Supervisely annotation to one internal `TileLabel` (`bladesight.data.models`):
   tile id, source photo, row and column of the tile in that photo, size, and boxes
   (`damage`/`dirt`, tile pixels as given by the annotators). Archive members are validated by
   name before anything is written (no path traversal, regular files only, size limits).
3. **Split** by **source photo** (`DJI_0004_01_04` belongs to photo `DJI_0004`), so tiles of one
   photo never fall on both sides, stratified by whether the photo has any damage box: 15% of the
   photos in each stratum go to held-out, seed `20261029`. The build fails if held-out has fewer
   than 300 labeled tiles.
4. **Seal**: held-out files are hashed from the archive bytes while they are written (the build
   never reads `data/heldout/`), listed in `eval/heldout_manifest.sha256` (`sha256sum` format,
   paths relative to `data/`), then `data/heldout/` is set to mode 000. Code refuses to load it
   unless `ALLOW_HELDOUT=1`, which only the single preregistered run of issue #16 sets.
5. **Verify**: every later `poe data` must reproduce the committed manifest byte for byte.

Layout after the build:

```
data/raw/<archive>.tar
data/dev/labels.jsonl       one TileLabel per line
data/dev/img/<tile>.png
data/heldout/               sealed (chmod 000) until #16
```

## What is committed

- `eval/heldout_manifest.sha256`: sha256 and file name of every held-out tile, plus
  `heldout/labels.jsonl`. File names and hashes only, no content.
- `eval/split_summary.json`: seed, archive hash, manifest hash and counts per split.

Never committed: images, labels, archives, crops, model weights (`AGENTS.md` rule 2).

## Known gaps

- **Year is unknown.** Neither the YOLO derivative nor the original DTU file names (`DJI_xxxx`)
  say whether a tile comes from the 2017 or the 2018 inspection, so `year` is `null`. The
  2017/2018 inspections of the demo fleet (#11) are a synthetic grouping of real photos.
- If a `DJI_xxxx` number was used in both years, both photos share one group; this can only make
  the split more conservative (more tiles held together), never leak across splits.
- Severity is not labelled in either dataset (see `docs/rubric.md` and #10).
