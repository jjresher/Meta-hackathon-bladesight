# API contract

The models live in `src/bladesight/contracts.py` (pydantic, `extra="forbid"`). The JSON Schema
and one example response per endpoint are generated from code into `web/src/fixtures/`:

```bash
uv run poe contract   # rewrite web/src/fixtures/*.json from the models
```

`tests/test_contracts.py` fails if the committed fixtures drift from the code. The fixtures are
**made-up values for UI development**, never results: do not quote them.

`schema.json` is exported in serialization mode: it describes what the API sends, so fields with
defaults are marked required.

Schema version: `SCHEMA_VERSION` (currently `1.0`), also returned by `/api/health`.

## Endpoints (issue #12)

| Method and path | Response | Fixture |
|---|---|---|
| `GET /api/health` | `Health` | `health.json` |
| `GET /api/fleet` | `Fleet` (turbines ranked, `rank` 1 = most urgent) | `fleet.json` |
| `GET /api/inspections/{inspection_id}` | `Inspection` (images, defects with measurement, assessment, verification) | `inspection_T03-2018.json` |
| `GET /api/work-orders` | `WorkOrder[]` | `work_orders.json` |
| `GET /api/reports/latest` | `Report` (Markdown body) | `report_latest.json` |
| `GET /api/runs` | `AgentRun[]` | `runs.json` |
| `GET /api/runs/{run_id}` | `AgentRun` (full trace, `AgentStep[]`) | `run_run-example-001.json` |
| `GET /api/eval` | `EvalReport[]` (dev, and held-out once #16 ran) | `eval.json` |
| `GET /images/{tile_id}.png` | PNG tile (served from `data/`, never committed) | - |

Errors use FastAPI's default `{"detail": "..."}` with 404 for unknown ids.

## Conventions

- Ids: `T03` turbine, `T03-2018` inspection, `T03-2018/DJI_0702_04_05` image,
  `T03-2018/DJI_0702_04_05/d1` defect, `WO-001` work order, `run-...` agent run.
- Pixels: image coordinates, origin top-left; `outline` and `blade_outline` are lists of closed
  polygons (one per mask part, `[x, y]` pairs) for SVG overlays. Sizes are relative (pixels,
  share of blade), never mm.
- `Inspection.summary.year` is a **synthetic grouping**: the DTU tiles carry no real year
  (`DATA.md`). The UI must label the fleet "synthetic farm of real DTU photos" (`Fleet.note`).
- `Verification.verdict`: `ok`, `needs_review` (a human should look), `reinspect` (take new
  photos). Every verdict carries `reasons`. A `WorkOrder` always cites `defect_ids` and
  `evidence` (non-empty, enforced by the schema).
- `EvalReport.evidence_path` points to the `docs/evidence/` file behind the numbers.
- Image and defect ids contain `/`: in UI routes use `encodeURIComponent`; any future API route
  taking them needs a `{id:path}` parameter.
- The fixtures are for development only: the deployed web build must load data from the API, never
  bundle `web/src/fixtures/` as a fallback (they are made-up values, `AGENTS.md` rule 5).
