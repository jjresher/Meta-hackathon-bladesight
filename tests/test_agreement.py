"""Weighted kappa, confusion matrix and the agreement summary, on known examples."""

from __future__ import annotations

import pytest

from bladesight.assess.assess import build_prompt
from bladesight.contracts import Assessment, BBox, Defect, Measurement
from bladesight.eval.agreement import (
    Graded,
    bootstrap_kappa,
    confusion,
    summarize,
    weighted_kappa,
)


def test_kappa_known_values() -> None:
    same = [1, 2, 3, 4, 5, 3, 2]
    assert weighted_kappa(same, same) == 1.0
    assert weighted_kappa([1, 5, 1, 5], [5, 1, 5, 1]) == pytest.approx(-1.0)
    # one off-by-one disagreement out of four: hand-computed quadratic weights
    a, b = [1, 2, 3, 4], [1, 2, 3, 5]
    assert weighted_kappa(a, b) == pytest.approx(13 / 14)  # 1 - (1/64) / (56/256)
    assert weighted_kappa(a, b, "linear") < 1.0
    # a constant rater against itself has no chance-corrected signal: defined as 1.0
    assert weighted_kappa([3, 3], [3, 3]) == 1.0


def test_kappa_needs_paired_ratings() -> None:
    with pytest.raises(ValueError):
        weighted_kappa([1, 2], [1])
    with pytest.raises(ValueError):
        weighted_kappa([], [])


def test_confusion_matrix_rows_are_human_columns_are_model() -> None:
    m = confusion([1, 1, 3, 5], [1, 2, 3, 4])
    assert m[0][0] == 1 and m[0][1] == 1 and m[2][2] == 1 and m[4][3] == 1
    assert sum(map(sum, m)) == 4


def test_bootstrap_interval_brackets_the_estimate_and_is_reproducible() -> None:
    human = [1, 2, 3, 4, 5, 3, 3, 2, 1, 4] * 3
    model = [1, 2, 3, 4, 4, 3, 2, 2, 1, 5] * 3
    low, high = bootstrap_kappa(human, model, n_boot=300, seed=1)
    assert low <= weighted_kappa(human, model) <= high
    assert (low, high) == bootstrap_kappa(human, model, n_boot=300, seed=1)


def _assessment(severity: int) -> Assessment:
    return Assessment(
        defect_id="x", defect_type="crack", severity=severity, rationale="r", confidence=0.5,
        rubric_version="v1", prompt_version="assess/v1", model="m", provider="stub",
    )  # fmt: skip


def test_unreadable_labels_are_reported_apart_and_left_out_of_kappa() -> None:
    graded = [
        Graded("a", 1, _assessment(1)),
        Graded("b", 3, _assessment(3)),
        Graded("c", 5, _assessment(4)),
        Graded("d", 0, _assessment(2)),  # the human could not read it
        Graded("e", 2, None, "invalid JSON twice"),
    ]
    out = summarize(graded)
    assert out["n_total"] == 5 and out["n_unreadable_human"] == 1 and out["n_model_failed"] == 1
    assert out["n_compared"] == 3 and out["unreadable_model_grades"] == {2: 1}
    assert out["human_distribution"] == {1: 1, 3: 1, 5: 1}
    assert out["exact"] == pytest.approx(2 / 3) and out["within_one"] == 1.0
    assert out["mean_signed_diff"] == pytest.approx(-1 / 3)


def test_prompt_without_a_detector_score_says_so() -> None:
    box = BBox(x1=0, y1=0, x2=10, y2=10)
    defect = Defect(id="x", image_id="i", concept="c", label="damage", score=1.0, bbox=box,
                    mask_area_px=100)  # fmt: skip
    m = Measurement(defect_id="x", area_px=100, tile_area_ratio=0.01, length_px=10, width_px=10,
                    elongation=0.0, position="unknown")  # fmt: skip
    assert "detector confidence 1.00" in build_prompt(defect, m)
    assert "no detector confidence" in build_prompt(defect, m, with_score=False)


def test_assess_defect_forwards_model_and_budget_and_keeps_defaults() -> None:
    import io

    from PIL import Image

    from bladesight.assess import assess_defect
    from bladesight.meta import ChatResult, MetaSettings, StubProvider, Usage, build_client

    box = BBox(x1=10, y1=10, x2=40, y2=40)
    defect = Defect(id="x", image_id="i", concept="c", label="damage", score=0.9, bbox=box,
                    mask_area_px=900)  # fmt: skip
    m = Measurement(defect_id="x", area_px=900, tile_area_ratio=0.01, length_px=30, width_px=30,
                    elongation=0.0, position="unknown")  # fmt: skip
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buffer, format="PNG")
    reply = ChatResult(
        text='{"defect_type":"dirt","severity":1,"rationale":"r","confidence":0.5}',
        usage=Usage(input_tokens=1, output_tokens=1),
        model="",
    )

    def run(**kwargs: object) -> StubProvider:
        stub = StubProvider(chat_responses=[reply])
        client = build_client(MetaSettings(), provider="stub", stub=stub)
        result = assess_defect(client, MetaSettings(), buffer.getvalue(), defect, m, **kwargs)  # type: ignore[arg-type]
        assert result.severity == 1
        return stub

    default = run().chat_calls[0]
    assert default.model == MetaSettings().chat_model and default.max_tokens == 1500
    custom = run(model="meta-models/muse-spark-open", max_tokens=6000).chat_calls[0]
    assert custom.model == "meta-models/muse-spark-open" and custom.max_tokens == 6000
