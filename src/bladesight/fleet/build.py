"""A synthetic farm of real DTU photos: 12 turbines x 2 inspections (2017, 2018) of dev tiles.

The DTU tiles carry no real turbine id or year (DATA.md), so this grouping is invented and always
labelled so: it exists to show the method on a fleet. Seeded; tiles are never reused.
"""

from __future__ import annotations

import random
from typing import Any

from ..data import TileLabel

SEED = 20261031
N_TURBINES = 12
YEARS = (2017, 2018)
IMAGES_PER_INSPECTION = 4
DAMAGE_SHARES = (0.0, 0.25, 0.5, 0.75)  # share of damaged tiles per inspection, drawn per cell
NOTE = (
    "Synthetic farm: 12 turbines and their 2017 and 2018 inspections are an invented grouping of "
    "real DTU photos of a single Nordtank turbine (the photos carry no real turbine or year)."
)


def inspection_id(turbine: str, year: int) -> str:
    return f"{turbine}-{year}"


def build_layout(
    tiles: list[TileLabel],
    seed: int = SEED,
    n_turbines: int = N_TURBINES,
    per_inspection: int = IMAGES_PER_INSPECTION,
) -> dict[str, Any]:
    """`{"turbines": {"T01": {"2017": [tile ids], "2018": [...]}}}`, reproducible from the seed."""
    rng = random.Random(seed)
    damaged = sorted((t for t in tiles if t.has_damage), key=lambda t: t.tile_id)
    clean = sorted((t for t in tiles if not t.has_label), key=lambda t: t.tile_id)
    rng.shuffle(damaged)
    rng.shuffle(clean)
    need = n_turbines * len(YEARS) * per_inspection
    if len(damaged) + len(clean) < need:
        raise ValueError("not enough tiles for the farm")
    turbines: dict[str, dict[str, list[str]]] = {}
    for n in range(1, n_turbines + 1):
        tid = f"T{n:02d}"
        turbines[tid] = {}
        for year in YEARS:
            share = rng.choice(DAMAGE_SHARES)
            n_damaged = min(round(per_inspection * share), len(damaged))
            picked = [damaged.pop().tile_id for _ in range(n_damaged)]
            picked += [clean.pop().tile_id for _ in range(per_inspection - n_damaged)]
            rng.shuffle(picked)
            turbines[tid][str(year)] = picked
    return {"synthetic": True, "note": NOTE, "seed": seed, "turbines": turbines}
