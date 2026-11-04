# Demo video script (3:00 maximum, English captions)

Record against the deployed URL in replay mode (`docs/submission/checklist.md`), screen capture
plus voice-over. Every claim has its evidence file in brackets; say nothing that is not listed.
Timings add up to 2:55.

| Time | On screen | Voice-over (and captions) |
|---|---|---|
| 0:00-0:08 | Title card: BladeSight. Repo page. | "Everything you are about to see was built this week, for the Meta Global AI Developer Hackathon." (README) |
| 0:08-0:28 | A close-up drone tile of a blade (Inspection viewer, no overlay yet). | "Wind turbine blades erode, crack and get struck by lightning. Inspections produce thousands of drone photos that people still review by hand, and a missed defect becomes downtime and a crane rental. BladeSight turns photos into a prioritized repair plan, and it says when it is not sure." |
| 0:28-0:50 | Inspection viewer: toggle the masks on a tile with 3-4 defects; open a defect card (severity, type, reasons, verdict). | "SAM 3.1 finds the defects with no training: Muse Spark proposes boxes and SAM 3.1 turns them into masks. Each defect is measured in relative size and graded one to five by Muse Spark against a written rubric, with its reasons." (`docs/evidence/spike.md`, `docs/rubric.md`) |
| 0:50-1:15 | A defect card with verdict `needs_review` and one with `ok`; show the verification reasons. | "A second, independent look checks the first. When the two disagree or confidence is low, the verdict is needs review or re-inspect, instead of guessing. On our demo farm, 34 percent of defects are verified, 52 percent need review and 14 percent need new photos." (`docs/evidence/fleet_run.md`) |
| 1:15-1:45 | Fleet screen: the 12 turbines ranked, status chips, the "synthetic farm" label. Open the top turbine. | "The turbines are ranked with a transparent score over verified defects only; a fleet agent, Muse Spark with tools, explains the ranking and compares inspections. This farm is synthetic: twelve turbines built from real photos of one turbine, so the ranking illustrates the method, not a real farm." (`docs/evidence/fleet_run.md`, `DATA.md`) |
| 1:45-2:10 | Work orders and report screen: open WO-001 (repair, evidence lines citing defect ids), then a re-inspection order. | "The agent writes work orders. A repair order can only cite defects whose verdict is ok: the tool rejects the rest, and unverified defects become re-inspection requests. Each order lists its evidence." (`docs/evidence/fleet_run.md`, `tests/test_fleet.py`) |
| 2:10-2:25 | Agent trace screen: scroll the steps (23 tool calls). | "Here is the full trace of the agent run: sixty steps, twenty-three tool calls, six cents." (`docs/evidence/fleet_run.md`) |
| 2:25-2:48 | Evaluation screen: image-level recall, box-level recall and precision, the limits box. | "We measured it. On 300 development tiles the detector finds at least one damage in 77 percent of damaged tiles, with a 21 percent false-alarm rate on tiles with no labelled box. Box-level recall is only 22 percent, partly because the labelled defects are tiny. Severity agrees only weakly with a human applying our rubric, so it is advisory." (`docs/evidence/eval_dev.md`, `docs/evidence/severity_agreement.md`) |
| 2:48-2:55 | Closing card: repo URL, live URL. Add the held-out line only if `docs/evidence/eval_heldout.md` exists. | "BladeSight: zero-shot blade inspection, from drone photos to a verified repair plan, with measured accuracy and honest limits." |

## Rules for the recording

- English captions; under 3:00; no login to view; the link in the submission opens without sign-in.
- Show only the deployed URL in replay mode. No live model call on screen.
- Say "synthetic farm" when the fleet appears. Never present the severity labels as specialist-validated, and
  never state a real inspection year.
- Numbers are the ones in the table above; if any evidence file changes, update the line first.
- Do not claim the open-weights path or the held-out result unless their evidence files exist.
