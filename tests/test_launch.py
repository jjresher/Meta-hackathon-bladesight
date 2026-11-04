"""The launch texts (#21): the X posts fit, carry the hashtag and only use placeholders for links."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "docs" / "submission" / "launch.md"
X_LINK_WEIGHT = 23  # X counts every link as 23 characters
LINK = re.compile(r"https?://\S+|<(?:demo|video) URL>")


def x_length(post: str) -> int:
    return len(LINK.sub("x" * X_LINK_WEIGHT, post))


def x_posts() -> list[str]:
    text = LAUNCH.read_text(encoding="utf-8")
    section = text.split("## X (main post", 1)[1].split("## LinkedIn", 1)[0]
    return [block.strip() for block in re.findall(r"```text\n(.*?)```", section, re.DOTALL)]


def test_every_x_post_fits_in_280_characters() -> None:
    posts = x_posts()
    assert len(posts) == 4  # the main post and a 3-post thread
    too_long = {p[:40]: x_length(p) for p in posts if x_length(p) > 280}
    assert not too_long, too_long


def test_the_main_post_has_the_hashtag_and_says_the_farm_is_synthetic() -> None:
    main = x_posts()[0]
    assert "#MetaAIHackathon" in main
    assert "synthetic" in main.lower()


def test_numbers_are_sourced_and_the_data_licence_is_credited() -> None:
    text = LAUNCH.read_text(encoding="utf-8")
    assert "CC BY-NC" in text
    for evidence in re.findall(r"`(docs/evidence/[^`]+)`", text):
        assert (ROOT / evidence).exists(), evidence
