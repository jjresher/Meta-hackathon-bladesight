# BladeSight

Zero-shot wind turbine blade inspection: from drone photos to a verified, prioritized repair plan,
built on Meta **SAM 3.1** and **Muse Spark**.

> Built from scratch during the **Meta Global AI Developer Hackathon** (Oct 27 - Nov 4, 2026),
> Indie Developer track. Everything in this repository was created during the event.

Status: in development. Plan and issues: [`docs/plan/implementation_plan.md`](docs/plan/implementation_plan.md).

## Quick start (development)

```bash
uv sync
uv run poe hooks      # once per clone
uv run poe check      # lint, format, types, tests
cp .env.example .env  # then fill in your keys; never commit .env
```

## Data

Drone inspection images of wind turbine blades from DTU (Shihavuddin & Chen, 2018,
DOI 10.17632/hd96prn3nc.2); the annotated derivative is licensed CC BY-NC 4.0. No data is stored
in this repository; it is downloaded by script (see `DATA.md`, issue #4).

## License

Code: MIT (see `LICENSE`). Data: see above.
