"""The keep-alive workflow (#14): schedule, permissions and target, checked as text (no network)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "keepalive.yml"
PUBLIC_URL = "https://bladesight.onrender.com"


def test_keepalive_runs_every_ten_minutes_and_on_demand() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '- cron: "*/10 * * * *"' in text  # under Render Free's 15-minute idle limit
    assert re.search(r"^  workflow_dispatch:", text, re.MULTILINE)


def test_keepalive_has_minimal_permissions_and_a_timeout() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"^permissions:\n  contents: read\n", text, re.MULTILINE)
    assert not re.search(r":\s*write\b", text)  # no write scope anywhere
    assert "timeout-minutes:" in text
    assert "--max-time" in text


def test_keepalive_pings_the_public_health_endpoint_and_fails_on_non_200() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert f"HEALTH_URL: {PUBLIC_URL}/api/health" in text
    assert '"$code" = "200"' in text
    assert "exit 1" in text
    # The same URL the submission checklist gives the judges.
    checklist = (ROOT / "docs" / "submission" / "checklist.md").read_text(encoding="utf-8")
    assert PUBLIC_URL in checklist
