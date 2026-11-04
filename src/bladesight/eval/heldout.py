"""The single held-out run (issue #16): sampling, manifest check, unseal and reseal.

Everything here happens only for the preregistered run (`eval/preregistration.md`): the labeled
tiles of the held-out split plus a seeded sample of its clean tiles, each clean tile weighted by
(clean tiles in the split / clean tiles sampled) so precision and false alarms per image describe
the whole split. Nothing in this module reads held-out data at import time.
"""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
from pathlib import Path

from ..data import TileLabel
from ..data.build import seal, unseal
from ..meta import MetaSettings

REPO_ROOT = Path(__file__).resolve().parents[3]  # the guards below never depend on the cwd
N_CLEAN = 300
SAMPLE_SEED = 20261104
EVIDENCE = REPO_ROOT / "docs/evidence/eval_heldout.md"
PREREGISTRATION = REPO_ROOT / "eval/preregistration.md"
MANIFEST = REPO_ROOT / "eval/heldout_manifest.sha256"
SPLIT_SUMMARY = REPO_ROOT / "eval/split_summary.json"
# The pipeline the preregistration freezes. In the environment these come from META_* variables,
# so the run refuses to start unless they still have the preregistered values.
FROZEN = {
    "chat_model": "muse-spark-1.3",
    "sam_model": "sam-3.1",
    "reasoning_effort": "low",
    "store": False,
}
GUARDED_PATHS = ("src", "pyproject.toml", "uv.lock", "eval/preregistration.md")
# Tests switch this off to exercise the machinery with the stub on synthetic data. The CLI
# itself has no flag for it.
ENFORCE_FROZEN = True


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


def verify_manifest(
    data_dir: Path, manifest: Path = MANIFEST, summary: Path | None = SPLIT_SUMMARY
) -> int:
    """sha256 of every held-out file against the committed manifest; returns the file count.

    With `summary`, also checks the manifest's own hash and its line count against the committed
    split summary, so an empty or truncated manifest cannot pass.
    """
    text = manifest.read_text(encoding="utf-8")
    lines = text.splitlines()
    if summary is not None and summary.exists():
        recorded = json.loads(summary.read_text(encoding="utf-8"))
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != recorded["manifest_sha256"]:
            raise HeldoutError(f"{manifest} does not match its recorded hash in {summary}")
        if len(lines) != recorded["counts"]["heldout"]["tiles"] + 1:
            raise HeldoutError(f"{manifest} has {len(lines)} lines, not the recorded count")
    count = 0
    for line in lines:
        digest, _, name = line.partition("  ")
        try:
            actual = hashlib.sha256((data_dir / name).read_bytes()).hexdigest()
        except FileNotFoundError:
            raise HeldoutError(f"{name} is listed in {manifest.name} but missing") from None
        if actual != digest:
            raise HeldoutError(f"{name} does not match {manifest.name}: the split changed")
        count += 1
    return count


def check_frozen(settings: MetaSettings) -> None:
    """The models and options of the run must be the preregistered ones."""
    actual = {name: getattr(settings, name) for name in FROZEN}
    if actual != FROZEN:
        raise HeldoutError(f"settings {actual} differ from the preregistered {FROZEN}")


def dirty_files() -> list[str]:
    """Uncommitted changes in the code the preregistration freezes (empty = clean)."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", *GUARDED_PATHS],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return ["(git status failed)"]
    return [line[3:] for line in result.stdout.splitlines()]


def git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT, check=False
    )
    return result.stdout.strip() or "unknown"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight(data_dir: Path) -> str:
    """Checks that must pass before the run; returns the preregistration hash."""
    if EVIDENCE.exists():
        raise HeldoutError(f"{EVIDENCE} exists: the held-out run was already done (once only)")
    if not PREREGISTRATION.exists():
        raise HeldoutError(f"{PREREGISTRATION} must be written and frozen before the run")
    if ENFORCE_FROZEN and (dirty := dirty_files()):
        raise HeldoutError(f"uncommitted changes in frozen code: {dirty}")
    unseal(data_dir / "heldout")
    return sha256_of(PREREGISTRATION)


def reseal(data_dir: Path) -> None:
    seal(data_dir / "heldout")
