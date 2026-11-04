# Deploy evidence (issue #14)

Public URL: https://bladesight.onrender.com (Render **Free** plan, `render.yaml`, auto-deploy on
commit to `main`, replay mode, no secret on the service). All times are COT (UTC-5). No model call,
0 USD.

## Cold start

Render's documented Free-plan behaviour (https://render.com/docs/free, read on Nov 3): a Free web
service "spins down" after 15 minutes without inbound traffic (HTTP requests or WebSocket
messages), spin-up "takes about one minute", and each workspace gets 750 Free instance hours per
calendar month (spun-down time does not count; past 750 hours every Free service is suspended until
the next month).

Timed with `curl -s -o /dev/null -w '%{time_total} %{http_code}'` from Medellín (Cloudflare edge
`BOG`). "Idle" is the time since the last request from this session and since the last deploy of
`main`; requests from other people cannot be excluded.

| When | Idle before the first request | Request | Total | HTTP |
|---|---|---|---|---|
| Nov 3, 23:31:18 | about 25 min since the 23:05 deploy (my first request of the session) | `/api/health` | 0.32 s | 200 |
| Nov 3, 23:31:18 | warm | `/` | 0.27 s | 200 |
| Nov 4, 00:10:19 | 20.3 min after the 23:49:59 deploy of `91ee832`, no merge in between | `/api/health` | 0.35 s | 200 |
| Nov 4, 00:10:19 | warm | `/` | 0.28 s | 200 |
| **Nov 4, 03:42:52** | **3 h 32 min** (last request from this session 00:10:19; last merge and deploy 23:49) | **`/api/health`** | **21.49 s** (connect 0.17 s, time to first byte 21.49 s) | **200** |
| Nov 4, 03:43:14 | warm, right after | `/` | 0.31 s | 200 |
| Nov 4, 03:43:14 | warm | `/api/health` | 0.48 s | 200 |

Reading: after a long idle the first request waited **about 21.5 s** for the instance to wake,
then answered 200; warm requests take 0.3-0.5 s. Two earlier probes at 20-25 minutes idle found the
instance still awake, so the spin-down did not happen exactly at 15 minutes in those cases (or
other traffic kept it awake: it cannot be told apart). One cold sample only: the wake-up time can
vary (Render documents "about one minute"), so a cold smoke check or a cold visit should allow for
up to a minute.

## Smoke check against the public URL

`uv run python -m bladesight.api.smoke https://bladesight.onrender.com` at Nov 4, 03:43:20 (warm,
six seconds after the cold request above): health, fleet, one inspection, one image and the home
page.

```text
OK in 1.9s
```

Exit code 0.

## Phone viewport (390 x 844)

Playwright 1.64.1 (Chromium, `isMobile`, touch, device scale factor 3) against the public URL at
Nov 4, 03:43:22, real API and real photos, no mocks, no screenshots kept. Flow: fleet -> first
turbine -> inspection -> its work order -> agent trace -> evaluation. Run time 3.2 s.

| Screen | Path | Horizontal scroll (scrollWidth / clientWidth) | Elements checked visible and inside the 390 px width |
|---|---|---|---|
| Fleet | `/` | none (390 / 390) | page heading, "synthetic" farm note, first turbine row, navigation |
| Inspection | `/inspections/T01-2018` | none (390 / 390) | photo viewer, loaded photo (natural width 586 px), a SAM mask, a box, a defect card, the masks toggle |
| Work orders | `/work-orders#WO-001` | none (390 / 390) | the work order |
| Agent trace | `/runs` | none (390 / 390) | a trace step |
| Evaluation | `/eval` | none (390 / 390) | the severity kappa value |

No element extended past the viewport on any screen; no console error, page error or HTTP status
>= 400 during the run. This is a phone-sized browser emulation, not a physical phone: opening the
URL on a real phone stays a human check in `docs/submission/checklist.md`.

## Keep-alive

**Update, Nov 4:** the keep-alive is now an external job on cron-job.org that requests the demo
every 10 minutes. It is configured outside this repository, so its run history is not recorded
here. The GitHub Actions workflow below stays in place as a second pinger; after the note below it
had its first scheduled run (18:51Z, success). The rest of this section is the record of that
workflow up to 10:27 COT, and "not keeping the demo warm" describes that workflow, not the external
job. A cold start remains possible either way.

The first schedule (`*/10 * * * *`, merged 08:50Z on Nov 4) produced no scheduled run in its first
2.5 hours; only the manual run was green. GitHub's status page listed Actions as degraded from
09:50Z, as part of an incident on Pull Requests, Git Operations and Issues, so that explains at most
the later part of the gap. The cron then moved off the top of the hour, which GitHub's docs call a
high-load time. A request at 06:28 COT during that gap found the instance asleep and took 12.47 s
(`curl -w`, HTTP 200; the idle time before it is unknown).

As of 10:27 COT on Nov 4 the workflow still had 0 runs with `event=schedule`, almost 4 hours after
the cron moved, with the workflow `active` and GitHub's status page at "All Systems Operational".
The incident therefore does not explain it and the cause is unknown: **the keep-alive is not
keeping the demo warm**, and only the manual run is evidence that the job itself works.

The `keep-alive` workflow (`.github/workflows/keepalive.yml`) GETs `/api/health` every
10 minutes (`7,17,27,37,47,57 * * * *`) and on demand (`workflow_dispatch`), with a 90 s timeout per
try, up to
5 tries 15 s apart (a cold wake fits), and fails the run on anything but HTTP 200 with
`"status":"ok"`. Permissions: `contents: read` only. Limits: scheduled workflows run only from the
default branch; GitHub may delay or drop scheduled runs
under load, so a cold start remains possible; one service awake all month uses at most 744 of the
750 Free instance hours, which fits only while it is the workspace's only always-on Free service.
