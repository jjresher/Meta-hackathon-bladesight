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
7. **Language:** code, comments, docs, commits, PRs and UI are in **English**. The one exception
   is the handoff report given to the human in chat (see Git workflow), which is in Spanish and is
   never written to a file.
8. **Pin dependencies exactly** (`uv add --bounds exact`, `npm install --save-exact`).
9. Agents may make local commits, push them and open PRs, only from a branch named
   `i<issue>-<slug>` created from `main` (`git switch -c` is fine), never on `main`. Push only that
   branch to origin (`git push -u origin <branch>`); never force-push (no `-f`, no `--force`, no
   `--force-with-lease`), never push to `main`, never push tags. An agent opens a PR (`gh pr create`,
   using `.github/pull_request_template.md`) only after the human has read the handoff report and
   said OK. Agents never merge, close, approve or review PRs, never delete branches, and never
   change GitHub settings: the human merges every PR. Commits use the human's git identity from the
   existing git config; agents never change `user.name` or `user.email`, never use `--author`,
   never use `--no-verify`, and never `--amend` commits already pushed. Make small logical
   Conventional Commits as the work progresses, each with an issue reference. Staging with
   `git add` is allowed. Do not change the commit attribution settings or trailers; leave Claude
   Code's defaults as they are.
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
- The human read the handoff report (see Git workflow) and said OK before the PR was opened; the
  human reviews and merges every PR.
- No TODO without an issue number, e.g. `# TODO(#9): report IoU 0.5 as well`.

## Git workflow

- Branch from `main`: `i<issue>-<short-slug>` (e.g. `i5-sam-detection`). One issue per PR.
- Conventional commits in English: `feat(detect): merge overlapping SAM masks`.
- Open PRs with `.github/pull_request_template.md`, only after the handoff below (rule 9).
- **Blocking rule:** a review finding blocks a merge only if it breaks the demo, breaks a rule in
  this file, or supports a claim we cannot back. Everything else becomes a line in
  `docs/limitations.md` or a new P2 issue.

### Handoff before every PR

When an issue's work is done, in this order:

1. Run `uv run poe check`.
2. Run the `auditor` agent on the branch diff against the issue's DoD (skill `issue-audit`).
3. **STOP** and give the human a handoff report **in Spanish, in chat only** (do not write it to a
   file) with these sections: What was done; DoD status item by item with evidence; What is
   missing; What could be improved; Auditor findings (blocking vs follow-up); Real spend this
   session in USD; Verdict (ready for PR / not ready).
4. End the report with the branch name, the list of commits on it, and the PR title and body
   (English, following `.github/pull_request_template.md`) you propose to use.

Never say "ready" if any DoD item or blocking finding is open. Local commits may be made at any
point (rule 9); only the push and the PR wait for the human's OK. After the
OK: push the branch, open the PR with that title and body, and give the human the PR link. The
human reviews and merges it.

Final step, after opening the PR: wait for CI (`gh pr checks`), then tick the "CI green" box of the
Definition of Done in the PR description and tell the human the result (with the CI run link). If
`gh pr edit` fails (a Projects-classic GraphQL error), edit the body through the REST API
(`gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>`). If CI fails, fix what is yours
to fix on the same branch, push, and report. Never merge, approve or review the PR.

## Skills and agents

| Name | Kind | When |
|---|---|---|
| `meta-api-check` | skill | before any development call to the Meta Model API or Baseten |
| `eval-run` | skill | running or changing the evaluation, writing evidence |
| `issue-audit` | skill | auditing a PR against its issue, or the daily plan check |
| `write-decision` | skill | recording a decision, a finding or a spend |
| `auditor` | agent | independent review of a PR before merge (no prior context) |
