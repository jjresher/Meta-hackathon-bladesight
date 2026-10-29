# AGENTS.md

Canonical instructions for every coding agent (Claude Code, Codex, others) and for humans working
in this repository. `CLAUDE.md` imports this file; do not duplicate its content elsewhere.

## Project

**BladeSight**: a zero-shot wind turbine blade inspection agent, built solo for the Meta Global AI
Developer Hackathon (Indie track, Oct 27 - Nov 4 2026). Drone photos of blades go in; a verified,
prioritized repair plan comes out.

1. **SAM 3.1** segments defects and the blade from text concepts, with no training.
2. **Measurement** turns masks into relative size and position along the blade.
3. **Muse Spark** (vision) grades each defect against `docs/rubric.md` and explains why.
4. **Verification** takes a second look; low confidence becomes `needs_review` or `reinspect`.
5. **A fleet agent** with tools ranks turbines, compares 2017 vs 2018 inspections, writes work
   orders and the report.

Full plan, issues and Definition of Done: `docs/plan/implementation_plan.md`.
Decisions: `docs/decision_ledger.md`. Known gaps: `docs/limitations.md`.

## Non-negotiable rules

1. **Never read, print, copy or commit secrets.** Keys live only in `.env` (gitignored). Never
   open `.env`; reference variables by name and print `set` or `missing`, never a value.
2. **Never commit data.** No images, videos, `data/`, archives or model weights. The dataset is
   downloaded by a script (`DATA.md`). Pre-commit enforces this; never use `--no-verify`.
3. **Never read the sealed held-out split** (`data/heldout/**`) before issue #16. Only its sha256
   manifest is versioned. Tuning on held-out data invalidates the evaluation.
4. **Every real model call spends money and can fail.** Go through `bladesight.meta` (retries,
   cache, spend cap). Follow the `meta-api-check` skill for development calls. Tests and CI use the
   stub and spend 0 USD.
5. **No claim without evidence.** Every number in the README, UI or video links to a file in
   `docs/evidence/`. The agent never states a defect or a work order without a verified assessment.
6. **Built during the hackathon only.** No code copied from earlier projects (including the EAFIT
   Grid patents work). Third-party libraries are fine; note notable ones in the README.
7. **Language:** code, comments, docs, commits, PRs and UI are in **English**.
8. **Pin dependencies exactly** (`uv add --bounds exact`, `npm install --save-exact`).
9. Do not commit, push, open PRs, merge or change GitHub settings unless the human asked for it.
10. The dataset licence is **CC BY-NC 4.0**: keep attribution in `DATA.md` and the README.

## Commands

Python 3.12 managed by uv. Tasks run through poethepoet: `uv run poe <task>`.

| Command | Purpose |
|---|---|
| `uv sync` | create or update `.venv` from `uv.lock` |
| `uv run poe hooks` | install the pre-commit hooks (once per clone) |
| `uv run poe check` | **Definition-of-Done gate**: ruff lint + format check + pyright + pytest |
| `uv run poe fmt` | auto-format and auto-fix |
| `uv run poe secrets-scan` | run every pre-commit hook on the whole repo |

Later issues add `data`, `detect`, `eval`, `serve`, `web-*` tasks; keep this table current.

## Repository map

```
AGENTS.md / CLAUDE.md   agent instructions (this file is canonical)
.claude/                settings (deny rules), agents/auditor.md, skills/
.github/                PR and issue templates, CI
docs/plan/              implementation plan (issues, DoD, schedule, cut order)
docs/                   rubric, decision ledger, limitations, evidence/, submission/
src/bladesight/         Python package: meta/ detect/ measure/ assess/ verify/ fleet/ eval/ api/
web/                    React + Vite + TypeScript UI (issue #13)
tests/                  pytest suite (stub provider only)
scripts/                repo tooling and hooks
```

## Definition of Done (every change)

- `uv run poe check` passes locally and CI is green (plus web checks for `web/` changes).
- New behavior has tests on the stub; bug fixes include a regression test.
- No secrets, data or held-out files committed.
- Real model calls followed `meta-api-check`; their cost is written in the PR.
- Every claimed number links to `docs/evidence/`.
- Trade-offs: one line in `docs/decision_ledger.md` (skill `write-decision`); known gaps in
  `docs/limitations.md` with the issue number.
- The PR was reviewed by the `auditor` agent and its blocking findings are resolved.
- No TODO without an issue number, e.g. `# TODO(#9): report IoU 0.5 as well`.

## Git workflow

- Branch from `main`: `i<issue>-<short-slug>` (e.g. `i5-sam-detection`). One issue per PR.
- Conventional commits in English: `feat(detect): merge overlapping SAM masks`.
- Open PRs with `.github/pull_request_template.md`. Never force-push `main`.
- Before opening a PR, run the `auditor` agent on the diff (skill `issue-audit`).
- **Blocking rule:** a review finding blocks a merge only if it breaks the demo, breaks a rule in
  this file, or supports a claim we cannot back. Everything else becomes a line in
  `docs/limitations.md` or a new P2 issue.

## Skills and agents

| Name | Kind | When |
|---|---|---|
| `meta-api-check` | skill | before any development call to the Meta Model API or Baseten |
| `eval-run` | skill | running or changing the evaluation, writing evidence |
| `issue-audit` | skill | auditing a PR against its issue, or the daily plan check |
| `write-decision` | skill | recording a decision, a finding or a spend |
| `auditor` | agent | independent review of a PR before merge (no prior context) |
