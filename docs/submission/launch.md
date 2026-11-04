# Launch texts (issue #21)

Ready-to-paste posts for X, LinkedIn and the hackathon Discord. Posting is the human's job; this
file only holds the texts and the plan.

Rules the texts follow:

- Every number comes from an evidence file, cited in the table below (never in the post itself).
- Models are named as used: **SAM 3.1** and **Muse Spark** (`muse-spark-1.3`) on the Meta Model
  API; **Muse Spark Open** on Baseten graded the severity gold set only
  (`docs/evidence/open_weights.md`). Do not write that the whole pipeline runs on open weights
  unless the open-weights PR of Nov 3-4 has merged and its evidence says so (placeholder
  `<OPEN-WEIGHTS: confirm>` below).
- The demo farm is synthetic: real DTU photos of one turbine, grouped into an invented farm.
- The dataset is CC BY-NC (photos CC BY-NC 3.0, annotated tiles CC BY-NC 4.0, `DATA.md`): credit it.

Placeholders to replace before posting:

| Placeholder | What goes there |
|---|---|
| `<demo URL>` | the live URL from `docs/submission/checklist.md` (open it once first: Render Free wakes in about a minute) |
| `<video URL>` | the link of the 3:00 video (#19) |
| `<Meta account>` | the Meta handle to tag (ask in the hackathon Discord `#questions`, issue #21) |
| `<OPEN-WEIGHTS: confirm>` | keep the sentence only if the open-weights PR merged and its evidence backs it; otherwise delete it |

## Numbers used and where they come from

| Number in the posts | Source |
|---|---|
| held-out run on 760 tiles, preregistered, run once | `docs/evidence/eval_heldout.md` |
| image-level damage recall 0.70, 24% false alarms on tiles with no box | `docs/evidence/eval_heldout.md` (0.698 over 368 tiles; 0.240 over 300 tiles) |
| box-level damage precision 0.19, recall 0.16 (IoU 0.3) | `docs/evidence/eval_heldout.md` |
| severity agreement with a human applying the rubric: kappa 0.12, advisory only | `docs/evidence/severity_agreement.md` |
| Muse Spark Open on Baseten: kappa 0.19 on the same 40 crops, "no worse" | `docs/evidence/open_weights.md` |
| synthetic farm: 12 turbines, 2017 and 2018 inspections, 96 graded defects | `docs/evidence/fleet_run.md` |
| verdicts: 33 ok, 50 needs_review, 13 reinspect | `docs/evidence/fleet_run.md` |
| 9 work orders: 3 repairs (only on verified defects), 6 re-inspections | `docs/evidence/fleet_run.md` |
| most labelled defects are smaller than about 14x14 pixels | `docs/evidence/spike.md` (median box 210 px^2, 73% under 400 px^2) |

## X (main post, under 280 characters)

X counts every link as 23 characters and each line break as one; `tests/test_launch.py` checks that every post below stays within 280 on that count.

```text
Built solo for #MetaAIHackathon: BladeSight turns drone photos of wind turbine blades into a verified repair plan. SAM 3.1 segments defects with no training, Muse Spark grades them, a second look flags doubts. Synthetic demo farm.
<demo URL>
<video URL>
```

### Optional thread (3 replies)

```text
1/3 How it works: Muse Spark proposes boxes, SAM 3.1 turns them into masks, size is measured in pixels (no fake millimetres), Muse Spark grades 1-5 against a written rubric, then a second independent look decides: ok, needs_review or reinspect.
```

```text
2/3 Honest numbers from one preregistered held-out run (760 tiles): a damaged tile is flagged 70% of the time, with false alarms on 24% of clean tiles. Box-level precision 0.19, recall 0.16 on tiny boxes. Severity agrees only weakly with a human (kappa 0.12): advisory.
```

```text
3/3 A fleet agent ranks turbines, compares 2017 vs 2018 and writes work orders that can only cite verified defects: 9 on the synthetic farm, 6 of them re-inspections. Data: DTU drone images, CC BY-NC (Shihavuddin & Chen; Foster et al.). Code: https://github.com/jjresher/Meta-hackathon-bladesight
```

Check each with X's counter before posting (links count 23); trim "(Shihavuddin & Chen; Foster et
al.)" from 3/3 if it runs over.

## LinkedIn

```text
This week I built BladeSight, solo, for the Meta Global AI Developer Hackathon (Indie track).

The problem: wind farms collect thousands of drone photos of blades and people still review them by hand. BladeSight takes the photos and returns a prioritized repair plan, and it says "I am not sure" instead of guessing.

How it works:
- SAM 3.1 segments each defect with no training (Muse Spark proposes boxes, SAM turns them into masks).
- Size and position are measured from the mask, in pixels: the photos carry no scale, so no invented millimetres.
- Muse Spark grades each defect 1-5 against a written rubric and explains why.
- A second, independent look plus rule checks decides: ok, needs_review or reinspect.
- A fleet agent with tools ranks turbines, compares the 2017 and 2018 inspections and writes work orders. A repair order can only cite a verified defect; anything uncertain becomes a re-inspection.

What I measured, once, on a preregistered held-out set of 760 tiles nobody tuned on: a damaged tile is flagged 70% of the time, with false alarms on 24% of clean tiles. Box-level scores are low (precision 0.19, recall 0.16), partly because most labelled defects are smaller than about 14x14 pixels. The severity grade agrees only weakly with a human applying the rubric (kappa 0.12), so it is advisory, not a verdict. The same severity check also ran on Muse Spark Open, Meta's open-weights model, on Baseten, and did no worse on those 40 crops. <OPEN-WEIGHTS: confirm>

The demo farm is synthetic: real drone photos of one turbine, grouped into an invented 12-turbine farm so the agent has something to rank. Rankings illustrate the method, not a real farm.

Data: DTU drone inspection images (Shihavuddin and Chen, CC BY-NC 3.0) and the YOLO-annotated tiles (Foster et al., CC BY-NC 4.0). Thanks to both teams.

Demo: <demo URL>
Video: <video URL>
Code: https://github.com/jjresher/Meta-hackathon-bladesight

#MetaAIHackathon #WindEnergy #ComputerVision #AIAgents
```

## Discord (hackathon server)

```text
Hi all, sharing my Indie-track project: **BladeSight**, a zero-shot wind turbine blade inspection agent.
Drone photos in -> SAM 3.1 segments defects (no training) -> Muse Spark grades them against a rubric -> a second look marks each one ok / needs_review / reinspect -> a fleet agent writes work orders that can only cite verified defects.
One preregistered held-out run on 760 tiles: 70% of damaged tiles flagged, 24% false alarms on clean tiles; box-level numbers are low and the severity grade is advisory (all in the repo's evidence files).
The demo farm is synthetic (real DTU photos, CC BY-NC, of one turbine). Replay mode, no login:
Demo: <demo URL>  Video: <video URL>  Code: https://github.com/jjresher/Meta-hackathon-bladesight
Feedback welcome, especially from anyone who has inspected blades for real.
```

## Reminder plan (Nov 4 - Nov 16)

| When (COT) | What |
|---|---|
| Nov 4, before submitting | Post the X main post (and the thread), copy its link into the submission form (`docs/submission/checklist.md`) |
| Nov 4, after submitting | Post on LinkedIn and in the hackathon Discord; share in the EAFIT groups |
| Nov 9 (gallery voting opens) | Repost on X and LinkedIn with the gallery link `<gallery URL>`: "voting is open" |
| Nov 9-16, daily, 15 min | Answer replies and comments; one reminder in a different group or channel per day |
| Nov 15 | Last call post on X and LinkedIn |
| Nov 16 | Thank-you post; no new claims |

Before each repost: open `<demo URL>` once (Render Free sleeps after 15 minutes idle) and keep the
numbers exactly as in the table above.
