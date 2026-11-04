# Submission checklist (issue #20)

All times COT (UTC-5). Official deadline: **Wed Nov 4, 9:00 PM COT** (9:00 PM ET). Our code freeze:
**13:00**. Our send target: **18:00**. Tick a box only with the evidence beside it. Items marked
**human** need the author (accounts, recording, posting, the form).

## Facts for the form

| Field | Value |
|---|---|
| Project | BladeSight: zero-shot wind turbine blade inspection agent |
| Tagline | From drone photos to a verified, prioritized repair plan, with SAM 3.1 and Muse Spark |
| Track | Indie Developer (solo) |
| Challenge | Push the Frontier (energy) |
| Contributors | Juan José (jjresher), solo |
| Repo (public, MIT) | https://github.com/jjresher/Meta-hackathon-bladesight |
| Live URL | https://bladesight.onrender.com (replay mode, no login; Render Free plan, auto-deploy on commit to `main`). Cold start 21.5 s after 3.5 h idle, smoke OK in 1.9 s, 390x844 phone viewport passed on five screens ([`deploy.md`](../evidence/deploy.md)). Open it once and wait before recording or sharing |
| Video | **human:** link of the 3:00 video ([`video_script.md`](video_script.md)), public or unlisted, opens without login |
| X post | **human:** link of the post with #MetaAIHackathon (texts in [`launch.md`](launch.md), issue #21) |
| Models used | Muse Spark `muse-spark-1.3` and SAM 3.1 `sam-3.1` (Meta Model API); Muse Spark Open `meta-models/muse-spark-open` (Baseten) for severity, verification, the agent and the report in the second run |
| Bonus: Best Agentic Use-Case | **yes**: fleet agent choosing its own calls over seven tools, rules enforced by the tools, re-inspection instead of repair for unverified defects, full trace in the UI ([`fleet_run.md`](../evidence/fleet_run.md), README "Why it is agentic"). Say plainly that no stored run triggered a rule rejection |
| Bonus: Build on Meta Open Weight Models | **yes, scoped**: the whole planning half (severity, second look, agent with tool calls, report) ran end to end on Muse Spark Open and is the second run in the live demo (run selector, Compare runs); detection stays on SAM 3.1 via the Model API, which has no open-weights path ([`open_weights.md`](../evidence/open_weights.md), [`open_weights_farm.md`](../evidence/open_weights_farm.md)). Never claim the whole pipeline runs on open weights or that the open model is better |
| Bonus: Most Viral / Community Vote | via the X post and the gallery (#21); nothing to flag in the form beyond the post link |
| Bonus: Best Creative Build | not targeted |
| Data | DTU drone images (CC BY-NC 3.0) and the YOLO-annotated derivative (CC BY-NC 4.0), [`DATA.md`](../../DATA.md) |
| Short description (form) | Drone photos of wind turbine blades go in; a verified, prioritized repair plan comes out. Muse Spark proposes damage boxes and SAM 3.1 segments them with no training; Muse Spark grades each defect against a written rubric; a second look marks it ok, needs review or re-inspect; a fleet agent with tools ranks a synthetic 12-turbine farm and writes work orders that can only cite verified defects. The planning half also runs on Muse Spark Open. Detection was measured once on a preregistered held-out split. |

## Done (with evidence)

- [x] Repo is public; `LICENSE` is MIT; data attribution in `DATA.md` and the README
- [x] Held-out: `eval/preregistration.md` merged before `docs/evidence/eval_heldout.md` existed
      (PR #46, [`dod_audit.md`](dod_audit.md) section #16)
- [x] Every number in the README links to an evidence file (README "Results" table, rechecked for
      #18 against `docs/evidence/` and recounted from `replay/`)
- [x] Fresh-clone dry run in replay mode, timed: [`clean_clone.md`](../evidence/clean_clone.md)
- [x] Deployed URL: `python -m bladesight.api.smoke <url>` passes and the cold start is noted
      (Nov 4, 03:43: OK in 1.9 s; cold start 21.5 s, [`deploy.md`](../evidence/deploy.md))
- [x] Phone-sized check (390x844 emulation) on five screens, same file
- [x] Open-weights run in the live demo (run selector, `/compare`), PRs #55 and #56
- [x] Launch texts written with their sources ([`launch.md`](launch.md), PR #51)
- [x] DoD audit of the closed issues ([`dod_audit.md`](dod_audit.md), PR #53)
- [x] `main` green in CI at `da0c7dc` (merge of PR #56)

## What the human must do, in order

Estimates are wall-clock. Steps 1-8 fit before the 13:00 freeze; the video is the long pole.

| # | When (target) | Step | Estimate |
|---|---|---|---|
| 1 | by 08:00 | Review and merge the README / checklist / video-script PR (#18, #19, #20). Merge the detection v2 work (#22) only if its result is in and audited; then add its row to the README results table, linked to its evidence file. | 20 min |
| 2 | by 08:15 | Close stale PR #47 (superseded by #46 and #49; optionally move its "How this compares with the dev run" paragraph first, see [`dod_audit.md`](dod_audit.md)). | 5 min |
| 3 | by 08:30 | Attach screenshots as PR comments (not commits): the 5 overlay PNGs from `bladesight-wt/i5/outputs/detect/` on PR #28 (issue #5 DoD), and the 1280 and 390 px screenshots from `bladesight-screenshots/` on PR #44 (issue #13 DoD); tick those boxes and close #13. Keep the CC BY-NC attribution in the comment. | 15 min |
| 4 | by 08:45 | Open https://bladesight.onrender.com on a real phone (wake it first, allow up to a minute): fleet, an inspection, a work order, the run selector. Tick "public URL works from a phone" on #14 and close it. | 10 min |
| 5 | by 09:00 | Check the keep-alive: `gh run list --workflow keepalive.yml` should show scheduled runs about every 10 minutes (only one manual run was listed at 04:16). If none, wake the URL by hand before recording. | 5 min |
| 6 | 09:00-11:30 | Record the video (#19) from [`video_script.md`](video_script.md) against the live URL: wake it, 1280x720 browser window, replay mode only; edit to 3:00 or less, English captions. | 2 h 30 |
| 7 | 11:30-12:00 | Upload (YouTube or Vimeo, public or unlisted); check the length and that it opens in an incognito window. Tick the #19 DoD boxes. | 30 min |
| 8 | before 13:00 | Code freeze: last merge to `main`, CI green (`gh run list --branch main`), Render redeployed, smoke passes (`uv run python -m bladesight.api.smoke https://bladesight.onrender.com`). | 15 min |
| 9 | 13:00-13:20 | Put the video link in the README (replace the "link is added at submission" line) and in this table; small docs PR, merge. | 20 min |
| 10 | 13:20-14:00 | X post (#21): ask in Discord `#questions` which Meta account to tag (if still unanswered, post without it); replace `<demo URL>`, `<video URL>`, `<Meta account>` in the [`launch.md`](launch.md) texts, check the X counter, post, copy the link. | 40 min |
| 11 | 14:00-15:00 | Fill the submission form from "Facts for the form": track, challenge, repo, live URL, video, X post, contributors, bonus flags (agentic yes; open weights yes, scoped as written). | 1 h |
| 12 | before sending | Incognito check of every link in the form: repo, README renders with the diagram, live URL (wake it), video, X post. | 15 min |
| 13 | by 18:00 | Send. Keep the confirmation (screenshot). Tick the #20 DoD and close #18, #19, #20 when their boxes are met. | 10 min |
| 14 | after sending | LinkedIn and Discord posts, EAFIT groups; Most Viral window to Nov 8; gallery vote push from Nov 9 (reminder plan in [`launch.md`](launch.md)). | 30 min |

Buffer: 18:00 to the 21:00 deadline. If the recording runs late, skip the X thread replies and send
the form with the main post only.

## Before sending (final ticks)

- [ ] `main` is green in CI and the last merge is the one you want judged (`gh run list --branch main`)
- [ ] `README.md` shows the live URL and the video link
- [ ] `uv run poe secrets-scan` passes: no secret, data, image or held-out file in git
- [ ] `docs/limitations.md` is current; severity labels described only as one non-specialist applying the rubric
- [ ] **human** The live URL opens on a real phone (#14)
- [ ] **human** Video and live URL open from an incognito window (no login)
- [ ] **human** Contributors (solo), track Indie, bonus flags as in the table above
- [ ] **human** Confirmation received after submitting (screenshot kept)

## Render (issue #14), what to do in the dashboard

`render.yaml` needs **no environment variable** (replay mode has no secret): New > Blueprint >
this repo > apply. Plan `free`: the instance sleeps after about 15 minutes idle and takes up to about
a minute to wake (21.5 s measured), so open the URL once and wait before recording or sharing it
(`docs/limitations.md`). After each deploy run the smoke script against the URL. Never set
`META_API_KEY`, `BASETEN_API_KEY` or `BLADESIGHT_ADMIN_KEY` on the public service.
