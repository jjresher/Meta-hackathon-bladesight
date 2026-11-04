# Clean-clone dry run (issues #18, #20)

Nov 4, 2026, 04:10-04:22 COT (UTC-5). A fresh `git clone` of the public repository at `da0c7dc`
(merge of PR #56; the README changes of this PR only add steps, the commands are the same) into
`/tmp/bladesight-clean-20261104-041051`: not a worktree, no symlinks, no `.env`, no `data/`, no
`.cache/`. The README's replay instructions were followed literally. Replay mode only: no key, no
model call, **0 USD**. Machine: Linux x86_64, uv 0.12.19, Node 22.23.2, npm 10.9.8. The uv and npm
package caches of the machine were warm, so `uv sync` and `npm ci` are faster here than on a machine
that has never downloaded the packages.

## Steps, durations and results

| # | Command | Duration | Result |
|---|---|---|---|
| 1 | `git clone https://github.com/jjresher/Meta-hackathon-bladesight` | 1.5 s | `da0c7dc`, no `.env`, no `data/` |
| 2 | `uv sync` | 0.5 s (warm cache) | `.venv` created (178 MB) |
| 3 | `uv run python -m bladesight.data.demo` (run in the background, steps 4-6 meanwhile) | **605 s (10 min 5 s)** | `demo tiles: 96 of 96 fetched` into `data/dev/img/`; it streams the 2.8 GB archive until every tile named by `replay/` is found |
| 4 | `(cd web && npm ci && npm run build)` | 1.2 s + 0.6 s (warm cache) | 0 vulnerabilities; `tsc --noEmit` and `vite build` OK, `web/dist/` written |
| 5 | `uv run poe serve` | - | **failed on this machine**: `[Errno 98] ... ('127.0.0.1', 8000): address already in use` (another process held 8000) |
| 5b | `uv run poe serve --port 8010` | under 2 s to ready | poe appends the extra argument (`uvicorn ... --port 8000 --port 8010`), uvicorn uses the last: serving on 8010 |
| 6 | `curl /api/health`, `curl /api/replays`, `curl /` | instant | `{"status":"ok","mode":"replay",...}`; two replays (`meta` default with `run-final`, `baseten` with `run-open-weights`, 24 inspections each, stage-by-stage models); `/` 200 `text/html` |
| 6b | `curl "/api/fleet?provider=baseten"`, `curl "/api/runs?provider=baseten"` | instant | the Open ranking (T02 first) and the `run-open-weights` trace |
| 7 | `uv run python -m bladesight.api.smoke http://127.0.0.1:8010` **before** step 3 finished | 0.3 s | `FAIL /images/DJI_0681_06_09.png: HTTP 404`, exit 1: the smoke check fetches one tile |
| 7b | the same, after step 3 | under 0.1 s | `OK`, exit 0; `/images/DJI_0681_06_09.png` 200 `image/png` |
| 8 | `cd web && SMOKE_BASE_URL=http://127.0.0.1:8010 npx playwright test` | 2.1 s | 2 passed (fleet -> inspection -> work order at 1280 and 390 px, no console or network errors), 2 skipped by design (they need a mocked image failure); Chromium was already in the machine's Playwright cache |
| 9 | `uv run poe fleet compare --farm-cost 1.63 --open-farm-cost 1.7406` | 0.5 s | rewrote `docs/evidence/open_weights_farm.md` byte for byte: `git status` clean afterwards |
| 10 | `uv run poe check` | 14.7 s | ruff, format, pyright 0 errors, **397 passed** |

Time from `git clone` to the UI at `/` with the API answering, without the tiles: under a minute.
With the photos: about 10 minutes, all of it the tile download (step 3), which runs in parallel.

## Second clean clone, on `b3984b9` (Nov 4, after detection v2 merged)

Fresh `git clone` from GitHub into `/tmp`, no `.env`, warm uv and npm caches.

| Step | Time | Result |
|---|---|---|
| clone, `uv sync`, `npm ci`, web build | 14 s | build OK |
| `uv run poe check` | not timed | **411 passed** |
| `uv run python -m bladesight.data.demo` | **10,869 s (3 h 1 min)** | **failed**: `The read operation timed out`, 12 of 96 tiles on disk |
| `uv run poe serve --port 8023` | - | `/`, `/api/eval`, `/compare`, `/api/work-orders?provider=baseten` answered 200; 11 Meta work orders |
| `uv run python -m bladesight.api.smoke` | 0.1 s | **failed**: `/images/DJI_0681_06_09.png` 404, the expected result without that tile |

So the app reached the UI in replay mode without the photos, but this run did **not** get all the
photos: the archive host (`assets.supervisely.com`) delivered 0.36 MB/s to this machine in a 20 s
check at 10:13 COT, against the about 4 MB/s noted in `docs/limitations.md` for the original
download. One slow day on one network. Render's speed is not measured directly: GitHub's deployment
status shows `b3984b9` deployed in about 3 minutes, which suggests its fetch was much faster
(inferred, not observed). The same day the public demo served 96 of 96 tiles
with HTTP 200, from an image built earlier. Because of this run the Docker build is now strict
(`--strict`): a missing tile fails the build and, per https://render.com/docs/deploys, the running
instance continues (documented, not yet observed here).

## What the README was missing (fixed in this PR)

- The prerequisites (uv; Node.js 22 with npm) and the `git clone` line.
- How to use another port when 8000 is taken (`uv run poe serve --port 8010`).
- That the tile step takes about 10 minutes and can run in parallel, and that the smoke check fails
  on its image request until the tiles are there.
- That the UI build must exist before `poe serve` starts (already in `docs/limitations.md`, #12).
- Running the smoke check in a second terminal (the server stays in the foreground).

Not fixed (outside this PR): `python -m bladesight.api.smoke --help` is read as a URL and prints
four failures instead of the usage line. Every `uv run` also printed a warning that the shell's
`VIRTUAL_ENV` (a pyenv interpreter of this machine) does not match `.venv`; it is harmless and comes
from the shell, not the repository.
