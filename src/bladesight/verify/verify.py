"""A second, independent look at one assessed defect, plus rule checks -> `Verification`.

The second look sees a different crop (one medium-scale crop, no detector facts, a different
prompt). Verdicts:

- `ok`: the two looks agree, every rule check passes and confidence is high enough;
- `needs_review`: a human should look (the looks differ by one level, a rule check failed, or
  confidence is moderate);
- `reinspect`: the evidence cannot support a grade (the looks differ by 2+ levels, or confidence
  is very low): take new photos instead of guessing.

Every verdict carries its reasons. Thresholds are in `THRESHOLDS` (ledger: 2026-11-03, verify).
"""

from __future__ import annotations

from importlib import resources

from ..assess.assess import RUBRIC_VERSION, AssessError, parse_assessment
from ..assess.crops import crop_png
from ..contracts import Assessment, Check, Defect, Measurement, Verification
from ..meta import ChatMessage, ChatRequest, ImagePart, MetaClient, MetaError, MetaSettings

THRESHOLDS = {
    "ok_confidence": 0.3,  # combined confidence below this is never `ok`
    "reinspect_confidence": 0.15,  # combined confidence below this asks for new photos
    "reinspect_gap": 2,  # severity gap (levels) from which the looks are "disagreeing"
    "min_detector_score": 0.5,
    "min_inside_blade": 0.5,
    "serious_min_tile_share": 0.0005,  # severity >= 4 on a mask smaller than this is suspicious
    "minor_max_tile_share": 0.05,  # severity <= 2 on a mask larger than this is suspicious
}
SECOND_MAX_TOKENS = 1500


def _agreement(first: int, second: int | None) -> float:
    return 0.0 if second is None else 1.0 - abs(first - second) / 4


def rule_checks(defect: Defect, measurement: Measurement, assessment: Assessment) -> list[Check]:
    t = THRESHOLDS
    checks: list[Check] = []
    if measurement.inside_blade is None:
        checks.append(Check(name="inside_blade", passed=True, detail="no blade mask: not checked"))
    else:
        ok = measurement.inside_blade >= t["min_inside_blade"]
        checks.append(
            Check(
                name="inside_blade",
                passed=ok,
                detail=f"{measurement.inside_blade:.0%} of the mask is on the blade",
            )
        )
    ok = defect.score >= t["min_detector_score"]
    checks.append(
        Check(name="detector_score", passed=ok, detail=f"detector confidence {defect.score:.2f}")
    )
    share = measurement.tile_area_ratio
    if assessment.severity >= 4 and share < t["serious_min_tile_share"]:
        checks.append(
            Check(
                name="severity_vs_size",
                passed=False,
                detail=f"severity {assessment.severity} but it covers {share:.3%} of the photo",
            )
        )
    elif assessment.severity <= 2 and share > t["minor_max_tile_share"]:
        checks.append(
            Check(
                name="severity_vs_size",
                passed=False,
                detail=f"severity {assessment.severity} but it covers {share:.1%} of the photo",
            )
        )
    else:
        checks.append(
            Check(
                name="severity_vs_size",
                passed=True,
                detail=f"severity {assessment.severity} fits {share:.2%} of the photo",
            )
        )
    return checks


def decide(
    assessment: Assessment,
    second: Assessment | None,
    checks: list[Check],
    second_error: str | None = None,
    *,
    model: str | None = None,
    provider: str | None = None,
) -> Verification:
    """Pure decision logic: no model call, fully testable."""
    t = THRESHOLDS
    second_severity = second.severity if second else None
    agreement = _agreement(assessment.severity, second_severity)
    confidence = min(assessment.confidence, second.confidence) if second else 0.0
    gap = abs(assessment.severity - second.severity) if second else None
    reasons: list[str] = []

    verdict = "ok"
    if second is None:
        verdict = "needs_review"
        reasons.append(f"second look unavailable ({second_error or 'no valid reply'})")
    else:
        if gap is not None and gap >= t["reinspect_gap"]:
            verdict = "reinspect"
            reasons.append(f"the two looks differ by {gap} severity levels")
        elif gap == 1:
            verdict = "needs_review"
            reasons.append("the two looks differ by 1 severity level")
        if confidence < t["reinspect_confidence"]:
            verdict = "reinspect"
            reasons.append(
                f"combined confidence {confidence:.2f} is below {t['reinspect_confidence']}"
            )
        elif confidence < t["ok_confidence"]:
            verdict = "reinspect" if verdict == "reinspect" else "needs_review"
            reasons.append(f"combined confidence {confidence:.2f} is below {t['ok_confidence']}")
    for check in checks:
        if not check.passed:
            if verdict == "ok":
                verdict = "needs_review"
            reasons.append(f"rule check failed: {check.name} ({check.detail})")
    if verdict == "ok":
        reasons = [
            f"both looks agree on severity {assessment.severity}",
            f"combined confidence {confidence:.2f}",
            "all rule checks passed",
        ]
    return Verification.model_validate(
        {
            "defect_id": assessment.defect_id,
            "verdict": verdict,
            "agreement": agreement,
            "second_severity": second_severity,
            "checks": checks,
            "reasons": reasons,
            "model": second.model if second else model,
            "provider": second.provider if second else provider,
        }
    )


def second_look(
    client: MetaClient,
    settings: MetaSettings,
    png: bytes,
    defect: Defect,
    *,
    provider: str = "meta",
    model: str | None = None,
    max_tokens: int = SECOND_MAX_TOKENS,
) -> Assessment:
    prompt = resources.files("bladesight.verify").joinpath("prompts/v1.md").read_text("utf-8")
    image = ImagePart(
        data=crop_png(png, defect.bbox, pad=1.5, min_side=96.0), mime_type="image/png"
    )
    problem = ""
    for attempt in range(2):
        text = prompt.format(rubric_version=RUBRIC_VERSION)
        if attempt:
            text += f"\n\nYour previous reply was rejected: {problem}. Reply with the JSON only."
        reply = client.chat(
            ChatRequest(
                model=model or settings.chat_model,
                messages=[ChatMessage.user(text, image)],
                max_tokens=max_tokens,
            )
        )
        try:
            fields = parse_assessment(reply.text)
        except ValueError as error:
            problem = str(error).splitlines()[0][:200]
            continue
        return Assessment.model_validate(
            {
                "defect_id": defect.id,
                "defect_type": fields["defect_type"],
                "severity": fields["severity"],
                "rationale": fields["rationale"],
                "confidence": fields["confidence"],
                "rubric_version": RUBRIC_VERSION,
                "prompt_version": "verify/v1",
                "model": reply.model or model or settings.chat_model,
                "provider": provider,
            }
        )
    raise AssessError(f"{defect.id}: no valid second look after one retry ({problem})")


def verify_defect(
    client: MetaClient,
    settings: MetaSettings,
    png: bytes,
    defect: Defect,
    measurement: Measurement,
    assessment: Assessment,
    *,
    provider: str = "meta",
    model: str | None = None,
    max_tokens: int = SECOND_MAX_TOKENS,
) -> Verification:
    checks = rule_checks(defect, measurement, assessment)
    try:
        second = second_look(
            client, settings, png, defect, provider=provider, model=model, max_tokens=max_tokens
        )
        error = None
    except (AssessError, MetaError) as exc:  # an API failure abstains instead of crashing
        second, error = None, str(exc)
    return decide(
        assessment, second, checks, error, model=model or settings.chat_model, provider=provider
    )
