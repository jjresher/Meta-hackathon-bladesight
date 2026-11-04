"""Grade one detected defect: crops + measurements -> validated `Assessment`.

Invalid output (not JSON, wrong enum, severity outside 1-5, empty rationale) is retried ONCE with
the validation error in the prompt; a second failure raises `AssessError` so the caller records
`InspectedDefect.error` instead of inventing a grade.
"""

from __future__ import annotations

import json
from importlib import resources

from pydantic import ValidationError

from ..contracts import Assessment, BBox, Defect, Measurement
from ..meta import ChatMessage, ChatRequest, ImagePart, MetaClient, MetaSettings
from .crops import close_and_context

RUBRIC_VERSION = "v1"
PROMPT_VERSION = "assess/v1"
MAX_TOKENS = 1500
_DEFECT_TYPES = {
    "leading_edge_erosion",
    "crack",
    "lightning_damage",
    "surface_damage",
    "dirt",
    "other",
}


class AssessError(RuntimeError):
    """The model did not return a valid assessment after the one allowed retry."""


def load_prompt(version: str = "v1") -> str:
    return resources.files("bladesight.assess").joinpath(f"prompts/{version}.md").read_text("utf-8")


def parse_assessment(text: str) -> dict[str, object]:
    """The JSON object in `text` (tolerates a code fence), validated; raises ValueError."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the reply")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("the reply is not a JSON object")
    if data.get("defect_type") not in _DEFECT_TYPES:
        raise ValueError(f"defect_type must be one of {sorted(_DEFECT_TYPES)}")
    severity = data.get("severity")
    if isinstance(severity, bool) or not isinstance(severity, int) or not 1 <= severity <= 5:
        raise ValueError("severity must be an integer from 1 to 5")
    confidence = data.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, int | float)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("confidence must be a number from 0 to 1")
    rationale = data.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("rationale must be a non-empty string")
    return {**data, "rationale": rationale.strip()}


def build_prompt(
    defect: Defect, measurement: Measurement, version: str = "v1", *, with_score: bool = True
) -> str:
    score_text = (
        f"detector confidence {defect.score:.2f}"
        if with_score
        else "no detector confidence (an annotated box from the dataset)"
    )
    return load_prompt(version).format(
        rubric_version=RUBRIC_VERSION,
        source=defect.source,
        score_text=score_text,
        area_px=measurement.area_px,
        tile_share=measurement.tile_area_ratio,
        elongation=measurement.elongation,
        position=measurement.position,
    )


def assess_defect(
    client: MetaClient,
    settings: MetaSettings,
    png: bytes,
    defect: Defect,
    measurement: Measurement,
    *,
    provider: str = "meta",
    crops: tuple[bytes, bytes] | None = None,
    with_score: bool = True,
) -> Assessment:
    """`crops` (close, context) overrides the default crops, e.g. the exact crops a human saw."""
    close, wide = crops or close_and_context(png, BBox.model_validate(defect.bbox))
    images = [
        ImagePart(data=close, mime_type="image/png"),
        ImagePart(data=wide, mime_type="image/png"),
    ]
    prompt = build_prompt(defect, measurement, with_score=with_score)
    problem = ""
    for attempt in range(2):
        text = (
            prompt
            if attempt == 0
            else (
                f"{prompt}\n\nYour previous reply was rejected: {problem}. "
                "Reply again with the JSON only."
            )
        )
        reply = client.chat(
            ChatRequest(
                model=settings.chat_model,
                messages=[ChatMessage.user(text, *images)],
                max_tokens=MAX_TOKENS,
            )
        )
        try:
            fields = parse_assessment(reply.text)
            return Assessment.model_validate(
                {
                    "defect_id": defect.id,
                    "defect_type": fields["defect_type"],
                    "severity": fields["severity"],
                    "rationale": fields["rationale"],
                    "confidence": fields["confidence"],
                    "rubric_version": RUBRIC_VERSION,
                    "prompt_version": PROMPT_VERSION,
                    "model": reply.model or settings.chat_model,
                    "provider": provider,
                }
            )
        except (ValueError, ValidationError) as error:
            problem = str(error).splitlines()[0][:200]
    raise AssessError(f"{defect.id}: no valid assessment after one retry ({problem})")
