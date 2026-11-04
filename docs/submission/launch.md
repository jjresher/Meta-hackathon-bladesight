# Launch texts (issue #21)

Ready-to-paste posts for X, LinkedIn and the hackathon Discord. Posting is the human's job; this
file only holds the texts and the plan. **Update, Nov 4:** there is no X post, by decision (#21); the
X text stays here unused.

Rules the texts follow:

- Every number comes from an evidence file, cited in the table below (never in the post itself).
- Models are named as used: **SAM 3.1** and **Muse Spark** (`muse-spark-1.3`) on the Meta Model
  API. The planning half (grading, verification, the agent and its report) also runs on
  **Muse Spark Open** on Baseten (`docs/evidence/open_weights.md`,
  `docs/evidence/open_weights_farm.md`); detection always uses SAM 3.1 via the Model API, so never
  write that the whole pipeline runs on open weights, and never that the open model is better.
- The agent is described only by what the stored runs show: it requests re-inspections for
  defects verification did not confirm, and a tool rule rejects a repair order citing an
  unverified defect. No stored run triggered that rejection, so never claim one did.
- The demo farm is synthetic: real DTU photos of one turbine, grouped into an invented farm.
- The dataset is CC BY-NC (photos CC BY-NC 3.0, annotated tiles CC BY-NC 4.0, `DATA.md`): credit it.

Placeholders to replace before posting:

| Placeholder | What goes there |
|---|---|
| `<demo URL>` | the live URL from `docs/submission/checklist.md` (open it once first: Render Free wakes in about a minute) |
| `<video URL>` | the link of the 3:00 video (#19) |
| `<Meta account>` | the Meta handle to tag (ask in the hackathon Discord `#questions`, issue #21); put it in reply 1/3 (244 characters, room for it), not in the main post (278) |
| `<gallery URL>` | the project's page in the hackathon gallery, once voting opens |

## Numbers used and where they come from

| Number in the posts | Source |
|---|---|
| held-out run on 760 tiles, preregistered, run once | `docs/evidence/eval_heldout.md` |
| image-level damage recall 0.70, 24% false alarms on tiles with no box | `docs/evidence/eval_heldout.md` (0.698 over 368 tiles; 0.240 over 300 tiles) |
| box-level damage precision 0.19, recall 0.16 (IoU 0.3) | `docs/evidence/eval_heldout.md` |
| severity agreement with one non-expert applying the rubric: kappa 0.12, advisory only | `docs/evidence/severity_agreement.md` |
| (not in the posts) Muse Spark Open on Baseten: kappa 0.19 on the same 40 crops, "no worse" | `docs/evidence/open_weights.md` |
| Muse Spark Open on the farm: same severity as Muse Spark on 78 of 98 defects, same verdict on 64 | `docs/evidence/open_weights_farm.md` |
| agent: 6 of 11 work orders are re-inspection requests; repair orders cite only `ok` defects (tool-enforced, 0 rejections in the stored runs) | `docs/evidence/fleet_run.md`, `docs/evidence/open_weights_farm.md` |
| synthetic farm: 12 turbines, 2017 and 2018 inspections, 98 graded defects | `docs/evidence/fleet_run.md` |
| verdicts: 35 ok, 50 needs_review, 13 reinspect | `docs/evidence/fleet_run.md` |
| 11 work orders: 5 repairs (only on verified defects), 6 re-inspections | `docs/evidence/fleet_run.md` |
| detector v2: box F1 0.25 against 0.22, same false alarms, fresh dev set of 300 tiles, not held-out | `docs/evidence/eval_fresh_v2.md` |
| most labelled defects are smaller than about 20x20 pixels | `docs/evidence/spike.md` (73% of truth boxes under 400 px^2 in the spike sample; median 210 px^2) |

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
2/3 Honest numbers, first detector, one preregistered held-out run (760 tiles): 70% of damaged tiles flagged, false alarms on 24% of clean ones. Box precision 0.19, recall 0.16. The demo runs a later detector. Severity agrees only weakly with a human (kappa 0.12): advisory.
```

```text
3/3 A fleet agent ranks turbines, compares 2017 vs 2018 and writes work orders: 11 on the synthetic farm, 5 repairs that cite only verified defects and 6 re-inspections. Data: DTU drone images, CC BY-NC (Shihavuddin & Chen; Foster et al.). Code: https://github.com/jjresher/Meta-hackathon-bladesight
```

Check each with X's counter before posting (links count 23); trim "(Shihavuddin & Chen; Foster et
al.)" from 3/3 if it runs over.

## LinkedIn

```text
Over the last week I built BladeSight, solo, for the Meta Global AI Developer Hackathon (Indie track).

The problem: wind farms collect large numbers of drone photos of blades, and people still review them by hand. BladeSight takes the photos and returns a prioritized repair plan, and it says "I am not sure" instead of guessing.

How it works:
- SAM 3.1 segments each defect with no training (Muse Spark proposes boxes, SAM turns them into masks).
- Size and position are measured from the mask, in pixels: the photos carry no scale, so no invented millimetres.
- Muse Spark grades each defect 1-5 against a written rubric and explains why.
- A second, independent look plus rule checks decides: ok, needs_review or reinspect.
- A fleet agent with tools ranks turbines, compares the 2017 and 2018 inspections and writes work orders. It picks its own tool calls, and when verification cannot confirm a defect it can only request a re-inspection, never a repair (6 of its 11 work orders on the demo farm, covering 19 of the 63 unconfirmed defects); a repair order citing an unverified defect is rejected by the tool itself, not just by the prompt.

What I measured, once, with the first detector, on a preregistered held-out set of 760 tiles nobody tuned on: a damaged tile is flagged 70% of the time, with false alarms on 24% of clean tiles. Box-level scores are low (precision 0.19, recall 0.16), partly because most labelled defects are smaller than about 20x20 pixels. The demo runs a later detector, measured separately on a preregistered fresh dev set of 300 tiles (box F1 0.25 against 0.22, same false alarms); it was never measured on the held-out set. The severity grade agrees only weakly with a non-expert applying the rubric (kappa 0.12), so it is advisory, not a verdict. The planning half (grading, verification, the agent and its report) also runs on Muse Spark Open, Meta's open-weights model, on Baseten; detection (Muse Spark boxes + SAM 3.1 masks) stays on the Meta Model API. On the same 98 defects the two models gave the same severity to 78 and the same verdict to 64.

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
Drone photos in -> SAM 3.1 segments defects (no training) -> Muse Spark grades them against a rubric -> a second look marks each one ok / needs_review / reinspect -> a fleet agent writes repair orders that can only cite verified defects, and asks for re-inspection when it is unsure.
The planning half (grading, verification, agent, report) also runs on Muse Spark Open, Meta's open-weights model, on Baseten; detection (Muse Spark boxes + SAM 3.1 masks) stays on the Meta Model API.
One preregistered held-out run of the first detector on 760 tiles: 70% of damaged tiles flagged, 24% false alarms on clean tiles; the demo runs a later detector, measured only on a fresh dev set; box-level numbers are low and the severity grade is advisory (all in the repo's evidence files).
The demo farm is synthetic (real DTU photos, CC BY-NC, of one turbine). Replay mode, no login:
Demo: <demo URL>  Video: <video URL>  Code: https://github.com/jjresher/Meta-hackathon-bladesight
Feedback welcome, especially from anyone who has inspected blades for real.
```

## Reminder plan (Nov 4 - Nov 16)

| When (COT) | What |
|---|---|
| Nov 4, before submitting | Post the X main post (and the thread), copy its link into the submission form (`docs/submission/checklist.md`) |
| Nov 4, after submitting | Post on LinkedIn and in the hackathon Discord; share in the EAFIT groups |
| Nov 5-8, daily, 15 min | Most Viral window (engagement counts to Nov 8 EOD): answer every reply on the X post; one quote-post a day with a single sourced detail from the table |
| Nov 9 (gallery voting opens) | Repost on X and LinkedIn with the gallery link `<gallery URL>`: "voting is open" |
| Nov 9-16, daily, 15 min | Answer replies and comments; one reminder in a different group or channel per day |
| Nov 15 | Last call post on X and LinkedIn |
| Nov 16 | Thank-you post; no new claims |

Before each repost: open `<demo URL>` once (Render Free sleeps after 15 minutes idle) and keep the
numbers exactly as in the table above.
