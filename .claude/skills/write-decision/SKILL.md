---
name: write-decision
description: Record a decision with trade-offs, a data or model finding, a spend, or a scope cut in docs/decision_ledger.md, and known gaps in docs/limitations.md. Use whenever a choice was made between alternatives, a threshold or prompt version changed, money was spent above $1 in a day, or something was cut or deferred.
---

# Recording decisions

## Ledger line (`docs/decision_ledger.md`)

Newest first, one row each:

| Date | Area | Decision / finding | Evidence | Issue |
|---|---|---|---|---|
| 2026-10-30 | detect | Use concept prompt "surface crack" instead of "crack": recall 0.62 vs 0.41 on 20 dev tiles; "crack" fired on blade seams. | `docs/evidence/spike.md` | #3 |

Rules:
- State the decision, the alternative rejected and why, in one or two sentences.
- Evidence is a file, a command output, a PR or a request id. No evidence, no row.
- Areas: `meta`, `data`, `detect`, `assess`, `verify`, `agent`, `api`, `web`, `eval`, `deploy`,
  `budget`, `scope`, `submission`.

## Limitation line (`docs/limitations.md`)

- `- <what does not work or is not covered> — impact: <who or what it affects> — issue: #<n>`
- Limitations are shown honestly in the README and the Evaluation page. Judges reward candor more
  than they punish known gaps.

## Spends

Log the day's real-model spend when it passes $1, and every run of step 4 of `meta-api-check`:
calls, estimated USD, purpose.
