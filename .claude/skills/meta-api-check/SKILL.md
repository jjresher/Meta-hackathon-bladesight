---
name: meta-api-check
description: Spend Meta Model API (Muse Spark, SAM 3.1) or Baseten (Muse Spark Open) credits safely during development - free checks first, then one call, a few, one small batch - with a hard cap, retries and cache through bladesight.meta, proof that the model really answered, and the cost of each step. Use before any development call that spends money; not for the final held-out run (#16), which follows eval/preregistration.md.
---

# Checking against a real model during development

The budget is $150 of Meta credits with a card on file (charges continue after the credits run
out), plus partner credits if granted. The Model API also fails intermittently (about 25% of calls
in one participant's measurement on Oct 29), so every call goes through `bladesight.meta`, which
retries, caches and enforces a spend cap. Tests and CI use the stub (0 USD).

## 0. Before the first call

- The human asked for the check or approved it. Say what will run and roughly what it costs.
- Never open, print or copy `.env` (AGENTS.md rule 1). Load it into the process only, e.g.
  `uv run --env-file .env python -m ...`. Print `set` or `missing` for each key, never a value.
- Set a hard cap far below the budget for the process: `META_SPEND_LIMIT_USD=0.10` (or lower).
- Use dev images only. Never anything under `data/heldout/` (AGENTS.md rule 3).
- Check whether the cache already has the answer (`--cache-only` dry run). A cache hit is free.

## 1. Climb one step at a time; stop at the first surprise

| Step | What | Calls |
|---|---|---|
| 0 | Configuration only: key set, model id, endpoint reachable (no generation) | 0 |
| 1 | One call with the smallest input that exercises the change | 1 |
| 2 | The few inputs the change is about (e.g. 3-5 dev tiles) | 2-5 |
| 3 | One small batch (e.g. 20 dev tiles) through the CLI | ~20-60 |
| 4 | A broader dev run (e.g. the whole dev eval subset): only when asked, estimated first, logged in `docs/decision_ledger.md` | hundreds |

Go up a step only when the one below is clean. Never run the held-out split here.

## 2. Prove the model answered

- Check the response came from the network, not the cache or the stub (`source=live` in the log).
- Check the payload is real: a SAM mask with non-zero area, a Muse Spark JSON that validates
  against its pydantic contract, the expected model id in the response metadata.
- If retries happened, report how many and the error codes.

## 3. Report

End every check with a short table in the PR or the chat:

| Step | Calls (live / cached / retried) | Est. cost USD | Result |
|---|---|---|---|

Add the running total of the day to `docs/decision_ledger.md` when it exceeds $1.

## When something is off

- 401/403: the key or its permissions; stop and tell the human (key creation is flaky for some
  participants; they may need to ask in `#office-hours`).
- Repeated 5xx/timeouts after retries: stop, record request ids, try later; do not loop.
- Invalid JSON from Muse Spark: one repair retry is allowed by design; more means the prompt needs
  work, not more calls.
- Spend cap reached: stop. Raising the cap is the human's decision.
