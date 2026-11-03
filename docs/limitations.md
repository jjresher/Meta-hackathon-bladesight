# Known limitations

What does not work or is not covered, its impact, and the issue that owns it. Shown honestly in
the README and the Evaluation page. See skill `write-decision`.

- The fleet is synthetic: real DTU photos of one Nordtank turbine grouped into 12 turbines for the demo — impact: rankings illustrate the method, not a real farm — issue: #11
- Sizes are relative (pixels and share of blade area), not millimetres: tiles carry no scale — impact: severity relies on relative size and appearance — issue: #6
- Severity has no public ground truth; it is graded against our own illustrative rubric and checked on a small hand-labelled set — issue: #7, #10
- The git/gh restrictions on agents are only partly enforced: the `deny` rules in `.claude/settings.json` are prefix patterns, so flags after the branch name, `git -C <dir> push`, `--amend`, `git config user.*`, `gh api -X ...` and similar are not matched. The rest is enforced by instruction (`AGENTS.md` rule 9) and by GitHub branch protection on `main`, which only the human can configure — impact: an agent could break a rule by accident; the human merges every PR — issue: #1
- The inspection year of a tile is unknown (no tags in the YOLO derivative, `DJI_xxxx` names in the original): the 2017/2018 inspections in the demo are a synthetic grouping of real photos, and the "2017 vs 2018" comparison illustrates the method, not real degradation — issue: #4, #11
- Split groups are DJI frame numbers: if one number was used in both inspection years, both photos share a group (more conservative, never a leak) — issue: #4
- Neighbouring photos (`DJI_000N`, `DJI_000N+1`) are probably near-duplicate views of the same blade area but are grouped only by exact photo number, so near-duplicates can fall on both sides of the dev/held-out split — impact: held-out metrics may be slightly optimistic — issue: #4, #16
- The dataset download URL is a signed Dataset Ninja link that may expire; the fallback (Kaggle) needs credentials. A failed build leaves `data/heldout/` unsealed (the seal runs last), a `.part` file already at full size gets HTTP 416, and every rebuild deletes `data/dev/` — impact: none on the replay demo; re-run `poe data` and re-check the mode of `data/heldout` after a failed build — issue: #4
