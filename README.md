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

Drone inspection photos of the DTU Nordtank wind turbine (Shihavuddin & Chen, 2018, Mendeley Data,
DOI [10.17632/hd96prn3nc.2](https://doi.org/10.17632/hd96prn3nc.2), CC BY-NC 3.0), as annotated
tiles from *YOLO Annotated Wind Turbine Surface Damage* (Foster et al., 2022, CC BY-NC 4.0). No
data is stored in this repository: `uv run poe data` downloads and splits it. Sources, citations,
the licence note and the sealed held-out split: [`DATA.md`](DATA.md).

## License

Code: MIT (see `LICENSE`). Data: see above.
