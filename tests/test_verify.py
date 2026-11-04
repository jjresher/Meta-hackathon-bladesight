"""Verification: every verdict branch, the rule checks and the second look, on the stub."""

from __future__ import annotations

import io
import json

import pytest
from PIL import Image

from bladesight.contracts import Assessment, BBox, Check, Defect, Measurement
from bladesight.meta import ChatResult, MetaSettings, StubProvider, Usage, build_client
from bladesight.verify import THRESHOLDS, decide, verify_defect
from bladesight.verify.verify import rule_checks


def _assessment(severity: int = 3, confidence: float = 0.8) -> Assessment:
    return Assessment(
        defect_id="T/I/d1",
        defect_type="surface_damage",
        severity=severity,
        rationale="r",
        confidence=confidence,
        rubric_version="v1",
        prompt_version="assess/v1",
        model="m",
        provider="stub",
    )


def _defect(score: float = 0.8) -> Defect:
    return Defect(
        id="T/I/d1",
        image_id="T/I",
        concept="c",
        label="damage",
        score=score,
        bbox=BBox(x1=20, y1=20, x2=60, y2=50),
        mask_area_px=900,
    )


def _measurement(share: float = 0.01, inside: float | None = None) -> Measurement:
    return Measurement(
        defect_id="T/I/d1",
        area_px=900,
        tile_area_ratio=share,
        length_px=40,
        width_px=10,
        elongation=0.75,
        inside_blade=inside,
        position="unknown",
    )


GOOD_CHECKS = [Check(name="x", passed=True, detail="ok")]


def test_ok_when_the_looks_agree_checks_pass_and_confidence_is_high() -> None:
    v = decide(_assessment(3, 0.8), _assessment(3, 0.7), GOOD_CHECKS)
    assert v.verdict == "ok" and v.agreement == 1.0 and v.second_severity == 3
    assert any("agree" in r for r in v.reasons)


def test_needs_review_when_the_looks_differ_by_one_level() -> None:
    v = decide(_assessment(3), _assessment(4), GOOD_CHECKS)
    assert v.verdict == "needs_review" and v.agreement == 0.75
    assert any("differ by 1" in r for r in v.reasons)


def test_reinspect_when_the_looks_differ_by_two_or_more_levels() -> None:
    v = decide(_assessment(4), _assessment(2), GOOD_CHECKS)
    assert v.verdict == "reinspect" and v.agreement == 0.5


def test_moderate_confidence_needs_review_and_very_low_confidence_reinspects() -> None:
    assert decide(_assessment(3, 0.2), _assessment(3, 0.9), GOOD_CHECKS).verdict == "needs_review"
    assert decide(_assessment(3, 0.9), _assessment(3, 0.1), GOOD_CHECKS).verdict == "reinspect"


def test_a_failed_rule_check_downgrades_an_otherwise_ok_verdict() -> None:
    failed = [Check(name="inside_blade", passed=False, detail="10% of the mask is on the blade")]
    v = decide(_assessment(3), _assessment(3), failed)
    assert v.verdict == "needs_review"
    assert any("inside_blade" in r for r in v.reasons)


def test_a_failed_rule_check_never_softens_reinspect() -> None:
    failed = [Check(name="x", passed=False, detail="d")]
    assert decide(_assessment(5), _assessment(1), failed).verdict == "reinspect"


def test_no_second_look_is_needs_review_with_zero_agreement() -> None:
    v = decide(_assessment(3), None, GOOD_CHECKS, "no valid second look")
    assert v.verdict == "needs_review" and v.agreement == 0.0 and v.second_severity is None
    assert "second look unavailable" in v.reasons[0]


def test_every_verdict_carries_reasons() -> None:
    for first, second, conf in [(3, 3, 0.9), (3, 4, 0.9), (5, 1, 0.9), (3, 3, 0.1)]:
        assert decide(_assessment(first), _assessment(second, conf), GOOD_CHECKS).reasons


@pytest.mark.parametrize(
    ("severity", "share", "inside", "failing"),
    [
        (4, 0.0001, None, "severity_vs_size"),
        (2, 0.2, None, "severity_vs_size"),
        (3, 0.2, None, None),
        (3, 0.01, 0.1, "inside_blade"),
        (3, 0.01, 0.9, None),
    ],
)
def test_rule_checks(
    severity: int, share: float, inside: float | None, failing: str | None
) -> None:
    checks = rule_checks(_defect(), _measurement(share, inside), _assessment(severity))
    assert {c.name for c in checks if not c.passed} == ({failing} if failing else set())


def test_a_weak_detector_score_fails_its_check() -> None:
    checks = rule_checks(_defect(0.3), _measurement(), _assessment())
    assert [c.name for c in checks if not c.passed] == ["detector_score"]


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (200, 120), (80, 80, 80)).save(buffer, format="PNG")
    return buffer.getvalue()


def _reply(**fields: object) -> ChatResult:
    body = {
        "defect_type": "surface_damage",
        "severity": 3,
        "rationale": "paint loss",
        "confidence": 0.8,
        **fields,
    }
    return ChatResult(text=json.dumps(body), usage=Usage(input_tokens=50, output_tokens=30))


def _verify(*replies: ChatResult):
    stub = StubProvider(chat_responses=replies)
    client = build_client(MetaSettings(), provider="stub", stub=stub)
    verdict = verify_defect(
        client,
        MetaSettings(),
        _png(),
        _defect(),
        _measurement(0.01),
        _assessment(3),
        provider="stub",
    )
    return stub, verdict


def test_verify_defect_runs_one_second_look_with_a_single_crop() -> None:
    stub, verdict = _verify(_reply())
    assert verdict.verdict == "ok" and len(stub.chat_calls) == 1
    content = stub.chat_calls[0].messages[0].content
    assert len(content) == 2  # prompt + one medium crop
    assert "version v1" in content[0].text  # type: ignore[union-attr]
    assert "detector" not in content[0].text.lower()  # type: ignore[union-attr]


def test_verify_defect_retries_the_second_look_once_then_abstains() -> None:
    stub, verdict = _verify(ChatResult(text="no"), ChatResult(text="still no"))
    assert verdict.verdict == "needs_review" and len(stub.chat_calls) == 2
    _, recovered = _verify(ChatResult(text="no"), _reply())
    assert recovered.verdict == "ok"


def test_thresholds_are_the_documented_ones() -> None:
    assert THRESHOLDS == {
        "ok_confidence": 0.3,
        "reinspect_confidence": 0.15,
        "reinspect_gap": 2,
        "min_detector_score": 0.5,
        "min_inside_blade": 0.5,
        "serious_min_tile_share": 0.0005,
        "minor_max_tile_share": 0.05,
    }


def test_confidence_boundaries_are_strict_less_than() -> None:
    assert decide(_assessment(3, 0.3), _assessment(3, 0.3), GOOD_CHECKS).verdict == "ok"
    assert decide(_assessment(3, 0.15), _assessment(3, 0.15), GOOD_CHECKS).verdict == "needs_review"
    assert decide(_assessment(3, 0.14), _assessment(3, 0.14), GOOD_CHECKS).verdict == "reinspect"
    assert decide(_assessment(3, 0.1), _assessment(4, 0.1), GOOD_CHECKS).verdict == "reinspect"


def test_size_check_boundaries_pass_exactly_at_the_threshold() -> None:
    assert not [
        c for c in rule_checks(_defect(), _measurement(0.0005), _assessment(4)) if not c.passed
    ]
    assert not [
        c for c in rule_checks(_defect(), _measurement(0.05), _assessment(2)) if not c.passed
    ]


def test_reinspect_keeps_the_failed_check_reason() -> None:
    failed = [Check(name="inside_blade", passed=False, detail="d")]
    v = decide(_assessment(5), _assessment(1), failed)
    assert v.verdict == "reinspect" and any("inside_blade" in r for r in v.reasons)


def test_a_client_error_in_the_second_look_abstains() -> None:
    from bladesight.meta import MetaServerError

    stub = StubProvider(failures=[MetaServerError("boom")] * 5)
    client = build_client(MetaSettings(), provider="stub", stub=stub)
    verdict = verify_defect(
        client, MetaSettings(), _png(), _defect(), _measurement(), _assessment(3), provider="stub"
    )
    assert verdict.verdict == "needs_review" and verdict.agreement == 0.0
