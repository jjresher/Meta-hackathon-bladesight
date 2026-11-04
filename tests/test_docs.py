"""Docs hygiene: relative links resolve and the banned wording is absent."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["README.md", "DATA.md", "docs/submission/checklist.md", "docs/submission/video_script.md"]
BANNED = ("expert-labelled", "expert-labeled", "ground truth", "ground-truth")


def test_relative_links_in_the_main_docs_resolve() -> None:
    missing = []
    for name in DOCS:
        text = (ROOT / name).read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (ROOT / Path(name).parent / target).exists():
                missing.append(f"{name} -> {target}")
    assert not missing, missing


def test_banned_wording_is_absent_from_docs_and_source() -> None:
    hits = []
    for path in [*ROOT.glob("docs/**/*.md"), *ROOT.glob("src/**/*.py"), ROOT / "README.md"]:
        text = path.read_text(encoding="utf-8").lower()
        hits += [f"{path.relative_to(ROOT)}: {word}" for word in BANNED if word in text]
    assert not hits, hits
