---
name: issue-audit
description: Audit work in BladeSight - either one issue's PR against its Definition of Done (PR mode) or the whole plan against the schedule at the end of the day (day mode). Use when the human asks to audit, review or check an issue, a PR, the day's progress, or before merging.
---

# Auditing

## PR mode (before every merge)

1. Identify the issue number and branch. Run `uv run poe check` first; fix failures before
   auditing (an audit of red code is wasted).
2. Launch the `auditor` agent (`.claude/agents/auditor.md`) with: the issue number, the branch,
   and nothing else. It must start without the implementer's context; do not summarize the work
   for it.
3. Give the human the auditor's report verbatim, then a short plan: which blocking findings you
   will fix now, and where each follow-up goes (`docs/limitations.md` line or new P2 issue).
4. After fixes, re-run `poe check`. Re-run the auditor only if a blocking finding needed a
   non-trivial change.
5. Paste the final report (or a link to it) in the PR description under "Audit".

Blocking rule: a finding blocks only if it breaks the demo, breaks a rule in `AGENTS.md`, or
supports a claim we cannot back.

## Day mode (end of each day, about 10 minutes)

Produce this report for the human:

```
## Day check — <date>

Done today: #.. #..
In progress: #.. (what is left)
Schedule (docs/plan/implementation_plan.md, section 6): on track | behind by <issues>
Spend: today $.. / total $.. (from the spend log and ledger)
Risks that changed: ..
Cut order applied: none | <issue> cut or reduced, because ..
Tomorrow first: #.. then #..
```

Then:
- If behind, propose the next cut from the plan's cut order; apply it only when the human agrees,
  and record it in `docs/decision_ledger.md`.
- Check that every merged PR has its evidence file and ledger lines; list anything missing.
- Check GitHub issues match reality (`gh issue list --state all`); propose closes or updates.
