"""DTU wind turbine tiles: download, conversion, grouped split and the sealed held-out split.

Source, licence and citation: `DATA.md`. The held-out split is never read before issue #16.
"""

from .models import Box, Split, TileLabel
from .splits import HeldoutSealedError, image_path, load_split

__all__ = [
    "Box",
    "HeldoutSealedError",
    "Split",
    "TileLabel",
    "image_path",
    "load_split",
]
