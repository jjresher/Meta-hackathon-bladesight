# Demo video script (3:00 maximum, English captions)

Issue #19. Record against the deployed URL in replay mode (https://bladesight.onrender.com, see
`docs/submission/checklist.md`): screen capture plus voice-over, browser window at 1280x720. Wake
the URL first (Render Free: up to about a minute on the first request). Timings add up to **2:55**;
the voice-over is about 400 words, about 140 words a minute. Every number spoken has its source in
the last column, and the numbered notes under the table give the exact line; say nothing that is
not listed.

Hero tile: inspection **T01-2018**, first tile **DJI_0681_06_09** (four defects: two verified
cracks, `d2` and `d7`, in repair order WO-001; two that need review, `d4` and `d6`, in re-inspection
request WO-004). URL: `/inspections/T01-2018`.

| Time | On screen | Voice-over (and captions) | Source |
|---|---|---|---|
| 0:00-0:08 | Title card "BladeSight", then the repo page. | "Everything you are about to see was built this week, solo, for the Meta Global AI Developer Hackathon." | README "Built during the hackathon" |
| 0:08-0:25 | Fleet screen, slow scroll; the "synthetic farm" note visible. | "Wind turbine blades erode and crack. Inspections produce thousands of drone photos that people still review by hand. BladeSight turns those photos into a prioritized repair plan, and it says when it is not sure." | README "The problem" |
| 0:25-0:52 | Inspection T01-2018, hero tile: masks and boxes on, the glyph key under the tile. Hover card `d2` (its mask lights up), open it: crack, severity 3, verified, the model badge "Muse Spark (Model API)". Then open `d4`: needs review, its reason. | "Muse Spark proposes boxes and SAM 3.1 turns them into masks, with no training. Each defect is measured in pixels, never fake millimetres, and graded one to five by Muse Spark against a written rubric, with its reasons. Then a second, independent look decides: verified, needs review, or re-inspect. The badge says which model graded it." | [1], [2] |
| 0:52-1:10 | Still on the inspection: the panel's verdict tally; then the Fleet screen with the 12 ranked turbines. | "Across the demo farm, 33 of 96 defects are verified, 50 need review and 13 need new photos. The farm is synthetic: real photos of one turbine, grouped into twelve, so the ranking shows the method, not a real farm." | [3], [4] |
| 1:10-1:30 | Work orders: WO-001 (repair, cites `d2` and `d7`), then WO-004 (re-inspection, cites `d4` and `d6` of the same tile). | "A fleet agent with seven tools writes the work orders. Nine on this farm: three repairs that cite only verified defects, and six re-inspection requests. On this tile, the two verified cracks get a repair; the two it is unsure about get new photos, not a guess." | [5] |
| 1:30-2:03 | Agent trace, "Decisions" view: scroll turn 4 (create_work_order, its "Why" line, accepted) and turn 7 (request_reinspection). Then "What the agent did on its own", then "Rules that could stop it" with "No call was rejected by a rule in this run." | "This is the agent's own trace, turn by turn: why it acted, the tool it chose, and whether the call was accepted. It chose 23 tool calls in 14 turns, for about six cents. The rules are enforced in code by the tools: a repair order that cites an unverified defect is rejected and sent back to the model. In this run no call was rejected; the agent followed the rules on the first try." | [6], [7] |
| 2:03-2:28 | Run selector: switch to "Muse Spark Open (Baseten)". Back to the hero tile: `d7` is now needs review, badge "Muse Spark Open (Baseten)". Then Compare runs: the agreement panel and the two rankings. | "The grading, the second look and the agent also ran on Muse Spark Open, Meta's open-weights model, on the same detections; detection stays on SAM 3.1. The open model is more cautious: this crack now needs review. The two runs agree on the severity of 74 of 96 defects and on the verdict of 63. We do not claim either is better." | [8], [9] |
| 2:28-2:50 | Evaluation screen, held-out split: image-level recall with the false-alarm rate beside it, box-level numbers, the severity kappa. | "We measured it once, on a preregistered held-out set of 760 tiles: it flags 70 percent of damaged tiles, with false alarms on 24 percent of clean ones. Box-level precision and recall are low, 0.19 and 0.16, because most labelled defects are tiny. Severity agrees only weakly with a human, so it is advisory." | [10], [11], [12] |
| 2:50-2:55 | Closing card: live URL and repo URL. | "BladeSight: from drone photos to a verified repair plan, with honest numbers." | - |

Sources (every spoken number):

1. Pipeline (Muse Spark boxes, SAM 3.1 masks, no training): `docs/evidence/spike.md` "Decision";
   rubric: `docs/rubric.md`.
2. Hero tile verdicts and models: `replay/inspections/T01-2018.json` (Muse Spark run: `d2`, `d7`
   crack, severity 3, `ok`; `d4`, `d6` `needs_review`).
3. "33 of 96 verified, 50 need review, 13 need new photos": `docs/evidence/fleet_run.md`, "Farm
   processing", verdicts line.
4. "Twelve turbines, synthetic": `docs/evidence/fleet_run.md` first paragraph, `DATA.md`.
5. "Seven tools", "nine work orders: three repairs, six re-inspections": `docs/evidence/fleet_run.md`
   "Agent run" and "Agent autonomy" (tool calls by tool); WO-001 and WO-004 in
   `replay/work_orders.json`.
6. "23 tool calls in 14 turns, about six cents" (0.0645 USD): `docs/evidence/fleet_run.md`, "Agent
   autonomy" table, `run-final` column.
7. "No call was rejected": same table, "Calls rejected by a tool rule: 0"; the rule is
   `verified_only` in `src/bladesight/fleet/rules.py`.
8. Open weights scope (planning half on Muse Spark Open, detection on SAM 3.1):
   `docs/evidence/open_weights.md` "What runs on which model". "More cautious" (22 `ok` against 33)
   and the hero crack `d7` moving to `needs_review`: `docs/evidence/open_weights_farm.md` verdict
   counts, `replay/open-weights/inspections/T01-2018.json`.
9. "74 of 96 severity, 63 verdict": `docs/evidence/open_weights_farm.md`, "Per defect".
10. "760 tiles, preregistered, once", "70 percent of damaged tiles" (0.698 over 368), "24 percent of
    clean ones" (0.240 over 300): `docs/evidence/eval_heldout.md`, "Image level".
11. "0.19 and 0.16" (damage, IoU 0.3): `docs/evidence/eval_heldout.md`, "Box matching". "Most
    labelled defects are tiny": `docs/evidence/spike.md` (73% of truth boxes under 400 px^2, i.e.
    20x20 px, median 210 px^2, in the spike sample).
12. "Agrees only weakly, advisory" (kappa 0.12): `docs/evidence/severity_agreement.md`.

## Rules for the recording

- English captions; 3:00 or less; the link in the submission opens without sign-in.
- Show only the deployed URL in replay mode. No live model call on screen.
- Say "synthetic farm" when the fleet appears. Never present the severity labels as
  specialist-validated, and never state a real inspection year.
- Numbers are the ones in the table above; if any evidence file changes, update the line first.
  If the detection v2 result (#22) is merged and replaces the detector, re-check notes 10-11 against
  the evidence of record before recording.
- Open weights: say that the grading, the second look and the agent with its report ran on Muse
  Spark Open; never say the whole pipeline (detection is SAM 3.1 on the Model API) and never that
  the open model is better.
- The agent: never say a rule rejection happened; say the rules are enforced by the tools and that
  no stored run triggered one.
- If time runs short, cut the "What the agent did on its own" panel first, then the rankings on
  Compare runs; keep the numbers line of the Evaluation scene.
