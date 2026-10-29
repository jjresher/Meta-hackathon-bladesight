## What and why

Closes #<!-- issue -->

<!-- One or two sentences: what changes and why. -->

## How it was tested

<!-- Commands you ran and what you observed. -->

## Real model calls

<!-- `meta-api-check` table, or "none". -->

| Step | Calls (live / cached / retried) | Est. cost USD | Result |
|---|---|---|---|

## Definition of Done

- [ ] Issue DoD met (every checkbox in the issue)
- [ ] `uv run poe check` passes locally; CI green (and web checks if `web/` changed)
- [ ] New behavior has tests on the stub; bug fixes include a regression test
- [ ] No secrets, data, images or held-out files; held-out untouched (unless this is #16)
- [ ] Every number claimed links to `docs/evidence/`
- [ ] Decisions in `docs/decision_ledger.md`; gaps in `docs/limitations.md`
- [ ] Code, docs, commits and UI in English

## Audit

<!-- Paste the `auditor` agent's final report (skill `issue-audit`). Verdict: MERGE / MERGE AFTER FIXES. -->

## Follow-ups

<!-- Anything not done, with destination (limitations line or new issue number). -->
