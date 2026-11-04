# Submission checklist (issue #20)

Deadline: **Wed Nov 4, 9:00 PM COT** (target send 6:00 PM COT). Tick a box only with the evidence
beside it. Items marked **human** need the author (accounts, links, the X post).

## Facts for the form

| Field | Value |
|---|---|
| Project | BladeSight: zero-shot wind turbine blade inspection agent |
| Track | Indie Developer (solo) |
| Challenge | Push the Frontier (energy) |
| Repo (public) | https://github.com/jjresher/Meta-hackathon-bladesight |
| Live URL | **human:** the Render URL after the deploy (`render.yaml`), checked from a phone |
| Video | **human:** link of the 3:00 video (`docs/submission/video_script.md`) |
| X post | **human:** link of the post with #MetaAIHackathon (issue #21) |
| Bonus: Best Agentic Use-Case | yes: fleet agent with tools, verification and abstention (`docs/evidence/fleet_run.md`) |
| Bonus: Build on Meta Open Weight Models | **partial**: Muse Spark Open on Baseten grades the severity gold set (`docs/evidence/open_weights.md`, no worse than the API on 40 crops); the agent, the report and the UI badge were not built: claim only that, or do not flag it |
| Bonus: Most Viral / Community Vote | via the X post and the gallery (#21), not claimed here |
| Models used | Muse Spark `muse-spark-1.3`, SAM 3.1 `sam-3.1` (Meta Model API) |
| Data | DTU drone images (CC BY-NC 3.0) and the YOLO-annotated derivative (CC BY-NC 4.0), `DATA.md` |

## Before sending

- [ ] `main` is green in CI and the last merge is the one you want judged (`gh run list --branch main`)
- [ ] `README.md` shows the live URL and the video link (replace the pointer to this file)
- [ ] Every number in the README links to an evidence file (`docs/evidence/`): grep the README
- [ ] `docs/limitations.md` is current; the severity labels are described only as one non-specialist applying the rubric (see `docs/evidence/severity_agreement.md`)
- [ ] No secret, data, image or held-out file in git: `uv run poe secrets-scan`
- [ ] Held-out: `eval/preregistration.md` merged **before** `docs/evidence/eval_heldout.md` exists
- [ ] Repo is public and the licence file is present (MIT code; data attribution in `DATA.md`)
- [ ] **human** Fresh-clone dry run: `git clone`, `uv sync`, `uv run poe check`, `uv run poe serve`,
      `python -m bladesight.api.smoke http://127.0.0.1:8000`
- [ ] **human** Deployed URL: `python -m bladesight.api.smoke <url>` passes; opens from a phone;
      note the cold-start time in `docs/submission/sprint_log.md`
- [ ] **human** Video link and live URL open from an incognito window (no login)
- [ ] **human** Contributors listed (solo), track Indie, bonus flags as in the table above
- [ ] **human** Confirmation received after submitting (screenshot kept)

## Render (issue #14), what to do in the dashboard

`render.yaml` needs **no environment variable** (replay mode has no secret): New > Blueprint >
this repo > apply. Plan `starter` so it does not sleep. After the first deploy run the smoke script
against the URL. Never set `META_API_KEY` or `BLADESIGHT_ADMIN_KEY` on the public service.

## After sending

- [ ] Post the X clip (30-45 s vertical, #MetaAIHackathon) and add the link to the submission (#21)
- [ ] Share in Discord, LinkedIn and EAFIT groups; vote push from Nov 9 (#21)
