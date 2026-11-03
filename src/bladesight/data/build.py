"""Download the DTU YOLO-annotated tiles, convert labels, split by source photo and seal held-out.

The held-out files are hashed while they are written (from the archive bytes), so building the
manifest never reads `data/heldout/`. After the build `data/heldout/` is chmod 000 (sealed).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import stat
import tarfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .models import Box, Split, TileLabel
from .splits import DATA_DIR

# Dataset Ninja (Supervisely) export of "YOLO Annotated Wind Turbine Surface Damage" (Foster et
# al., 2022), itself made from DTU's drone images (Shihavuddin & Chen, 2018). See DATA.md.
ARCHIVE_URL = (
    "https://assets.supervisely.com/remote/eyJsaW5rIjogInMzOi8vc3VwZXJ2aXNlbHktZGF0YXNldHMvMTEx"
    "MF9ZT0xPIEFubm90YXRlZCBXaW5kIFR1cmJpbmUgU3VyZmFjZSBEYW1hZ2UveW9sby1hbm5vdGF0ZWQtd2luZC10dXJ"
    "iaW5lLXN1cmZhY2UtZGFtYWdlLURhdGFzZXROaW5qYS50YXIiLCAic2lnIjogIjdsNFFEWXRxVFM3TStlWVlHaks5c1"
    "EwMkh2NE5hTG5vSHVGSWgwVDVkbVE9In0="
)
ARCHIVE_NAME = "yolo-annotated-wind-turbine-surface-damage-DatasetNinja.tar"
ARCHIVE_BYTES = 2_833_489_920
ARCHIVE_SHA256 = "fd68128874320cde1f26381ab1e71f34457a10b65bd8efd748e2302ec173d029"

SEED = 20261029
HELDOUT_FRACTION = 0.15
MIN_HELDOUT_LABELED = 300
MANIFEST = Path("eval/heldout_manifest.sha256")
SUMMARY = Path("eval/split_summary.json")

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_ANN_BYTES = 1024 * 1024
CLASSES = {"damage", "dirt"}


class DataBuildError(RuntimeError):
    pass


# --- download ---------------------------------------------------------------------------------


def download(
    dest: Path, url: str = ARCHIVE_URL, expected_bytes: int = ARCHIVE_BYTES, chunk: int = 1 << 20
) -> Path:
    """Stream the archive to `dest`, resuming a partial `.part` file. Idempotent."""
    if dest.exists() and dest.stat().st_size == expected_bytes:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    start = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={start}-"} if start else {}
    with httpx.stream(
        "GET", url, headers=headers, follow_redirects=True, timeout=httpx.Timeout(60.0)
    ) as response:
        if response.status_code not in (200, 206):
            raise DataBuildError(f"download failed: HTTP {response.status_code}")
        mode = "ab" if response.status_code == 206 else "wb"
        with part.open(mode) as handle:
            for block in response.iter_bytes(chunk):
                handle.write(block)
    if part.stat().st_size != expected_bytes:
        raise DataBuildError(
            f"download incomplete: {part.stat().st_size} of {expected_bytes} bytes; "
            "re-run to resume"
        )
    part.replace(dest)
    return dest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


# --- conversion -------------------------------------------------------------------------------


def convert_annotation(tile_id: str, ann: dict[str, Any]) -> TileLabel:
    """One Supervisely annotation JSON -> `TileLabel` (rectangles only, classes damage/dirt)."""
    photo, row, col = TileLabel.parse_tile_id(tile_id)
    boxes: list[Box] = []
    for obj in ann.get("objects", []):
        label = obj.get("classTitle")
        if label not in CLASSES:
            raise DataBuildError(f"{tile_id}: unknown class {label!r}")
        if obj.get("geometryType") != "rectangle":
            raise DataBuildError(f"{tile_id}: unexpected geometry {obj.get('geometryType')!r}")
        (x1, y1), (x2, y2) = obj["points"]["exterior"]
        boxes.append(
            Box(
                label=label,
                x1=min(x1, x2),
                y1=min(y1, y2),
                x2=max(x1, x2),
                y2=max(y1, y2),
            )
        )
    size = ann["size"]
    return TileLabel(
        tile_id=tile_id,
        source_photo=photo,
        row=row,
        col=col,
        width=int(size["width"]),
        height=int(size["height"]),
        boxes=boxes,
    )


def _member_tile(member: tarfile.TarInfo) -> tuple[str, str] | None:
    """('ann'|'img', tile_id) for a safe, expected member; None for files we ignore."""
    parts = member.name.removeprefix("./").split("/")
    if len(parts) != 3 or parts[0] != "ds" or parts[1] not in ("ann", "img"):
        return None
    if not member.isreg():
        raise DataBuildError(f"unexpected non-regular member {member.name!r}")
    kind, filename = parts[1], parts[2]
    suffix = ".png.json" if kind == "ann" else ".png"
    if not filename.endswith(suffix):
        raise DataBuildError(f"unexpected file {member.name!r}")
    tile_id = filename.removesuffix(suffix)
    TileLabel.parse_tile_id(tile_id)  # also rejects "..", slashes and anything unexpected
    limit = MAX_ANN_BYTES if kind == "ann" else MAX_IMAGE_BYTES
    if member.size > limit:
        raise DataBuildError(f"{member.name!r} is larger than {limit} bytes")
    return kind, tile_id


def read_labels(archive: tarfile.TarFile) -> tuple[list[TileLabel], dict[str, tarfile.TarInfo]]:
    labels: dict[str, TileLabel] = {}
    images: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        found = _member_tile(member)
        if found is None:
            continue
        kind, tile_id = found
        if kind == "img":
            images[tile_id] = member
            continue
        handle = archive.extractfile(member)
        assert handle is not None
        labels[tile_id] = convert_annotation(tile_id, json.loads(handle.read()))
    if set(labels) != set(images):
        missing = sorted(set(labels) ^ set(images))[:5]
        raise DataBuildError(f"images and annotations do not match, e.g. {missing}")
    return [labels[t] for t in sorted(labels)], images


# --- split ------------------------------------------------------------------------------------


def split_by_photo(
    tiles: Iterable[TileLabel], seed: int = SEED, fraction: float = HELDOUT_FRACTION
) -> dict[str, Split]:
    """Assign every source photo to one split, stratified by whether the photo has damage.

    All tiles of a photo share its split, so neighbouring (overlapping) tiles never leak across.
    """
    photos: dict[str, bool] = {}
    for tile in tiles:
        photos[tile.source_photo] = photos.get(tile.source_photo, False) or tile.has_damage
    rng = random.Random(seed)
    assignment: dict[str, Split] = {}
    for stratum in (False, True):
        group = sorted(p for p, damaged in photos.items() if damaged == stratum)
        rng.shuffle(group)
        n_heldout = round(len(group) * fraction)
        for i, photo in enumerate(group):
            assignment[photo] = "heldout" if i < n_heldout else "dev"
    return assignment


# --- write and seal ---------------------------------------------------------------------------


def _unseal_for_rebuild(heldout: Path) -> None:
    """Restore owner permissions on held-out *directories* so a rebuild can delete them.

    Only directory modes change; no held-out file is opened or read.
    """
    if not heldout.exists():
        return
    heldout.chmod(0o700)
    for root, dirs, _files in os.walk(heldout):
        for name in dirs:
            (Path(root) / name).chmod(0o700)


def seal(heldout: Path) -> None:
    for root, dirs, files in os.walk(heldout):
        for name in files:
            (Path(root) / name).chmod(stat.S_IRUSR)
        for name in dirs:
            (Path(root) / name).chmod(stat.S_IRUSR | stat.S_IXUSR)
    heldout.chmod(0)


@dataclass
class BuildResult:
    manifest_lines: list[str]
    summary: dict[str, Any]
    counts: dict[str, dict[str, int]] = field(default_factory=dict)


def _counts(tiles: list[TileLabel]) -> dict[str, int]:
    return {
        "tiles": len(tiles),
        "photos": len({t.source_photo for t in tiles}),
        "labeled_tiles": sum(t.has_label for t in tiles),
        "damage_tiles": sum(t.has_damage for t in tiles),
        "damage_boxes": sum(b.label == "damage" for t in tiles for b in t.boxes),
        "dirt_boxes": sum(b.label == "dirt" for t in tiles for b in t.boxes),
    }


def build(archive_path: Path, data_dir: Path = DATA_DIR, seed: int = SEED) -> BuildResult:
    dev, heldout = data_dir / "dev", data_dir / "heldout"
    _unseal_for_rebuild(heldout)
    for target in (dev, heldout):
        if target.exists():
            shutil.rmtree(target)
        (target / "img").mkdir(parents=True)

    with tarfile.open(archive_path, "r:") as archive:
        tiles, images = read_labels(archive)
        assignment = split_by_photo(tiles, seed=seed)
        by_split: dict[Split, list[TileLabel]] = {"dev": [], "heldout": []}
        manifest: list[str] = []
        for tile in tiles:
            split = assignment[tile.source_photo]
            by_split[split].append(tile)
            handle = archive.extractfile(images[tile.tile_id])
            assert handle is not None
            payload = handle.read()
            (data_dir / split / "img" / f"{tile.tile_id}.png").write_bytes(payload)
            if split == "heldout":
                digest = hashlib.sha256(payload).hexdigest()
                manifest.append(f"{digest}  heldout/img/{tile.tile_id}.png")

    for split, members in by_split.items():
        text = "".join(t.model_dump_json() + "\n" for t in members)
        (data_dir / split / "labels.jsonl").write_text(text, encoding="utf-8")
        if split == "heldout":
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            manifest.append(f"{digest}  heldout/labels.jsonl")

    counts = {split: _counts(members) for split, members in by_split.items()}
    if counts["heldout"]["labeled_tiles"] < MIN_HELDOUT_LABELED:
        raise DataBuildError(
            f"held-out has {counts['heldout']['labeled_tiles']} labeled tiles, "
            f"fewer than {MIN_HELDOUT_LABELED}"
        )
    seal(heldout)
    manifest.sort(key=lambda line: line.split("  ", 1)[1])
    summary = {
        "source": "Dataset Ninja export of YOLO Annotated Wind Turbine Surface Damage",
        "archive": ARCHIVE_NAME,
        "archive_sha256": ARCHIVE_SHA256,
        "seed": seed,
        "heldout_fraction_of_photos": HELDOUT_FRACTION,
        "grouping": "source photo (DJI_xxxx), stratified by photo has-damage",
        "manifest_sha256": hashlib.sha256("".join(f"{x}\n" for x in manifest).encode()).hexdigest(),
        "counts": counts,
    }
    return BuildResult(manifest_lines=manifest, summary=summary, counts=counts)
