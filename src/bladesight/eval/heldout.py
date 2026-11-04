"""The single held-out run (issue #16): sampling, manifest check, unseal and reseal.

Everything here happens only for the preregistered run (`eval/preregistration.md`): the labeled
tiles of the held-out split plus a seeded sample of its clean tiles, each clean tile weighted by
(clean tiles in the split / clean tiles sampled) so precision and false alarms per image describe
the whole split. Nothing in this module reads held-out data at import time.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

from ..data import TileLabel
from ..data.build import MANIFEST, seal, unseal

N_CLEAN = 300
SAMPLE_SEED = 20261104
EVIDENCE = Path("docs/evidence/eval_heldout.md")
PREREGISTRATION = Path("eval/preregistration.md")


class HeldoutError(RuntimeError):
    pass


def sample_heldout(tiles: list[TileLabel]) -> tuple[list[TileLabel], dict[str, float]]:
    """All labeled tiles plus `N_CLEAN` clean ones (seeded); returns the tiles and their weights."""
    labeled = sorted((t for t in tiles if t.has_label), key=lambda t: t.tile_id)
    clean = sorted((t for t in tiles if not t.has_label), key=lambda t: t.tile_id)
    rng = random.Random(SAMPLE_SEED)
    rng.shuffle(clean)
    picked = sorted(clean[:N_CLEAN], key=lambda t: t.tile_id)
    weight = len(clean) / len(picked) if picked else 1.0
    weights = {t.tile_id: 1.0 for t in labeled} | {t.tile_id: weight for t in picked}
    return labeled + picked, weights


def verify_manifest(data_dir: Path, manifest: Path = MANIFEST) -> int:
    """sha256 of every held-out file against the committed manifest; returns the file count."""
    count = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, _, name = line.partition("  ")
        path = data_dir / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise HeldoutError(f"{name} does not match {manifest}: the split changed")
        count += 1
    return count


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight(data_dir: Path) -> str:
    """Checks that must pass before the run; returns the preregistration hash."""
    if EVIDENCE.exists():
        raise HeldoutError(f"{EVIDENCE} exists: the held-out run was already done (once only)")
    if not PREREGISTRATION.exists():
        raise HeldoutError(f"{PREREGISTRATION} must be written and frozen before the run")
    unseal(data_dir / "heldout")
    return sha256_of(PREREGISTRATION)


def reseal(data_dir: Path) -> None:
    seal(data_dir / "heldout")
