"""Severity agreement (issue #10): Muse Spark vs the human labels of the gold set.

The labels were put by one person without wind-energy experience, applying `docs/rubric.md`: this
measures agreement with the rubric applied by a non-specialist, not severity validated by a
specialist. Crops marked 0 (unreadable) are left out of the kappa and reported apart. The model
grades the same crops the labeller saw (`gold.crop_for`), with the assess prompt and without a
detector confidence (the boxes come from the dataset, not from the detector).
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..assess import AssessError, assess_defect
from ..contracts import Assessment, BBox, Defect, Measurement
from ..meta import MUSE_SPARK_OPEN_MODEL, MetaClient, MetaSettings
from .gold import GOLD_CSV, crop_for, read_rows

LEVELS = (1, 2, 3, 4, 5)
# Muse Spark Open reasons before answering and the reasoning counts against the output budget
# (1500 tokens left an empty reply on 23 of 40 crops), so it gets a much larger budget.
OPEN_WEIGHTS_MAX_TOKENS = 6000


def weighted_kappa(a: Sequence[int], b: Sequence[int], weights: str = "quadratic") -> float:
    """Cohen's weighted kappa on the 1-5 scale (`quadratic` or `linear` disagreement weights)."""
    if len(a) != len(b) or not a:
        raise ValueError("two non-empty ratings of the same length are needed")
    k = len(LEVELS)
    observed = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b, strict=True):
        observed[x - 1][y - 1] += 1
    n = float(len(a))
    row = [sum(r) for r in observed]
    col = [sum(observed[i][j] for i in range(k)) for j in range(k)]

    def w(i: int, j: int) -> float:
        d = abs(i - j) / (k - 1)
        return d * d if weights == "quadratic" else d

    num = sum(w(i, j) * observed[i][j] for i in range(k) for j in range(k)) / n
    den = sum(w(i, j) * row[i] * col[j] for i in range(k) for j in range(k)) / (n * n)
    return 1.0 if den == 0 else 1.0 - num / den


def confusion(human: Sequence[int], model: Sequence[int]) -> list[list[int]]:
    matrix = [[0] * len(LEVELS) for _ in LEVELS]
    for h, m in zip(human, model, strict=True):
        matrix[h - 1][m - 1] += 1
    return matrix


def bootstrap_kappa(
    human: Sequence[int], model: Sequence[int], n_boot: int = 2000, seed: int = 20261030
) -> tuple[float, float]:
    """95% percentile interval over crops (resampling pairs; undefined draws are skipped)."""
    rng = random.Random(seed)
    values = []
    for _ in range(n_boot):
        idx = [rng.randrange(len(human)) for _ in human]
        h, m = [human[i] for i in idx], [model[i] for i in idx]
        if len(set(h)) == 1 and len(set(m)) == 1:
            continue  # kappa is degenerate when both raters are constant
        values.append(weighted_kappa(h, m))
    values.sort()
    return values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]


@dataclass
class Graded:
    crop_id: str
    human: int  # 0 = unreadable
    assessment: Assessment | None
    error: str | None = None


def grade_gold(
    client: MetaClient,
    settings: MetaSettings,
    data_dir: Path,
    csv_path: Path = GOLD_CSV,
    provider: str = "meta",
    model: str | None = None,
    max_tokens: int | None = None,
) -> list[Graded]:
    """Muse Spark grades every labelled crop (on the crops the human saw)."""
    graded = []
    for row in read_rows(csv_path):
        if row["severity"] == "":
            raise ValueError(f"{row['crop_id']} is not labelled yet")
        box = BBox(
            x1=float(row["x1"]), y1=float(row["y1"]), x2=float(row["x2"]), y2=float(row["y2"])
        )
        w, h = box.x2 - box.x1, box.y2 - box.y1
        defect = Defect(
            id=row["crop_id"], image_id=row["tile_id"], concept="dataset damage box",
            source="box_prompt", label="damage", score=1.0, bbox=box, mask_area_px=w * h,
        )  # fmt: skip
        measurement = Measurement(
            defect_id=defect.id,
            area_px=w * h,
            tile_area_ratio=min(w * h / (586 * 371), 1.0),
            length_px=max(w, h),
            width_px=min(w, h),
            elongation=1 - min(w, h) / max(w, h) if max(w, h) > 0 else 0.0,
            position="unknown",
        )
        close = crop_for(row, data_dir, 0.4)
        wide = crop_for(row, data_dir, 3.0)
        try:
            a = assess_defect(
                client, settings, b"", defect, measurement, provider=provider,
                crops=(close, wide), with_score=False, model=model,
                **({"max_tokens": max_tokens} if max_tokens else {}),
            )  # fmt: skip
            graded.append(Graded(row["crop_id"], int(row["severity"]), a))
        except AssessError as error:
            graded.append(Graded(row["crop_id"], int(row["severity"]), None, str(error)))
    return graded


def summarize(graded: Sequence[Graded]) -> dict[str, object]:
    readable = [g for g in graded if g.human != 0 and g.assessment]
    human = [g.human for g in readable]
    model = [g.assessment.severity for g in readable if g.assessment]
    unreadable = [g for g in graded if g.human == 0]
    out: dict[str, object] = {
        "n_total": len(graded),
        "n_unreadable_human": len(unreadable),
        "n_model_failed": sum(g.assessment is None for g in graded if g.human != 0),
        "n_compared": len(readable),
        "human_distribution": dict(sorted(Counter(human).items())),
        "model_distribution": dict(sorted(Counter(model).items())),
        "unreadable_model_grades": dict(
            sorted(Counter(g.assessment.severity for g in unreadable if g.assessment).items())
        ),
    }
    if readable:
        out |= {
            "kappa_quadratic": weighted_kappa(human, model),
            "kappa_linear": weighted_kappa(human, model, "linear"),
            "exact": sum(h == m for h, m in zip(human, model, strict=True)) / len(human),
            "within_one": sum(abs(h - m) <= 1 for h, m in zip(human, model, strict=True))
            / len(human),
            "mean_signed_diff": sum(m - h for h, m in zip(human, model, strict=True)) / len(human),
            "confusion": confusion(human, model),
        }
        if len(human) > 5:
            low, high = bootstrap_kappa(human, model)
            out["kappa_quadratic_ci"] = (low, high)
    return out


def render_markdown(
    summary: dict[str, object],
    graded: Sequence[Graded],
    cost_usd: float,
    *,
    name: str = "Muse Spark",
    model_line: str = "(`muse-spark-1.3`, `reasoning.effort=low`, `store=false`)",
    grades_file: str = "model_grades.csv",
) -> str:
    conf = summary.get("confusion")
    matrix = ""
    if isinstance(conf, list):
        matrix = "\n".join(
            [
                "| human \\ model | 1 | 2 | 3 | 4 | 5 |",
                "|---|---|---|---|---|---|",
                *[
                    f"| {i + 1} | " + " | ".join(str(v) for v in row) + " |"
                    for i, row in enumerate(conf)
                ],
            ]
        )
    ci = summary.get("kappa_quadratic_ci")
    ci_text = (
        f" (95% bootstrap interval {ci[0]:.2f} to {ci[1]:.2f})" if isinstance(ci, tuple) else ""
    )
    unreadable = [g.crop_id for g in graded if g.human == 0]
    failed = [g.crop_id for g in graded if g.human != 0 and g.assessment is None]
    unreadable_model = summary["unreadable_model_grades"] or "none"
    unreadable_text = f" ({', '.join(unreadable)})" if unreadable else ""
    failed_text = f" ({', '.join(failed)})" if failed else ""
    reading = (
        "**Reading.** The model grades lower than the human on average and mostly at the "
        "bottom of the scale; kappa near zero means agreement barely above chance. Severity "
        "shown by the product is therefore advisory, and the verification layer (second look, "
        "abstention) is the safety net, not a certification of the grade."
        if float(summary.get("mean_signed_diff", 0.0)) < -0.5  # type: ignore[arg-type]
        else ""
    )
    nan = float("nan")
    exact = float(summary.get("exact", nan))  # type: ignore[arg-type]
    within_one = float(summary.get("within_one", nan))  # type: ignore[arg-type]
    mean_diff = float(summary.get("mean_signed_diff", nan))  # type: ignore[arg-type]
    return f"""# Severity agreement: {name} vs the human labels (issues #10, #15)

**What this measures.** The 40 gold crops were labelled by one person with no wind-energy
experience, applying `docs/rubric.md` (our own illustrative rubric, observable criteria) blind to
the model on these crops. This file reports how much {name} agrees with that person
applying the rubric. It is agreement with the rubric applied by a non-specialist, **not**
severity validated by a wind-turbine specialist.

Crops: the dataset's own damage boxes (one per source photo, four size quartiles, seed 20261030;
`eval/gold/severity.csv` holds ids, boxes and the human labels, no images). {name}
{model_line} graded the same crops the labeller saw,
with the `assess/v1` prompt and without a detector confidence (the boxes come from the dataset).
Model grades are in `eval/gold/{grades_file}`. Cost of the run: {cost_usd:.4f} USD (documented
prices, not invoice-checked).

## Counts

- Crops: {summary["n_total"]}; compared: {summary["n_compared"]}.
- Labelled 0 (unreadable) by the human: {summary["n_unreadable_human"]}{unreadable_text}; they
  are left out of the kappa and the confusion matrix (model grades on them: {unreadable_model}).
- Model failures (no valid grade after one retry): {summary["n_model_failed"]}{failed_text}.
- Human severity distribution: {summary["human_distribution"]}.
- Model severity distribution: {summary["model_distribution"]}.

## Agreement (n = {summary["n_compared"]})

- Quadratic weighted kappa: **{summary.get("kappa_quadratic", float("nan")):.2f}**{ci_text}
  (linear weighted kappa {summary.get("kappa_linear", float("nan")):.2f}).
- Exact agreement: {exact:.0%}; within one level: {within_one:.0%}; mean (model - human):
  {mean_diff:+.2f} levels.

{reading}

## Confusion matrix (rows: human, columns: model)

{matrix}

## Limits

- One rater without domain experience and no second rater: there is no inter-rater agreement, so
  the ceiling for the model's agreement is unknown.
- n = 40 gives a wide interval; the crops are dataset boxes selected by size quartile, so large
  boxes are over-represented relative to the dataset (73% of the boxes in the 20-tile spike
  sample are under 400 px^2).
- The labeller wrote the rubric and had seen earlier model gradings (issue #7); the page only hid
  the grades for these crops. The model also receives measurements as text that the human does not.
- The kappa compares two ratings of the same crops; it says nothing about whether either is right.
"""


def main(argv: list[str] | None = None) -> int:
    import argparse
    import csv
    import io
    import sys

    from ..meta import MetaError, build_client

    parser = argparse.ArgumentParser(prog="python -m bladesight.eval.agreement")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--csv", type=Path, default=GOLD_CSV)
    parser.add_argument("--provider", choices=["meta", "baseten", "stub"], default="meta")
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--cost-usd", type=float, help="cost of the live run when this is a cached re-render"
    )
    args = parser.parse_args(argv)
    settings = MetaSettings.from_env()
    client = build_client(settings, provider=args.provider)
    open_weights = args.provider == "baseten"
    model = MUSE_SPARK_OPEN_MODEL if open_weights else None
    out = args.out or Path(
        "docs/evidence/severity_agreement_open_weights.md"
        if open_weights
        else "docs/evidence/severity_agreement.md"
    )
    grades_file = "model_grades_open_weights.csv" if open_weights else "model_grades.csv"
    try:
        graded = grade_gold(
            client, settings, args.data_dir, args.csv, args.provider, model,
            OPEN_WEIGHTS_MAX_TOKENS if open_weights else None,
        )  # fmt: skip
    except (MetaError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    cost = args.cost_usd if args.cost_usd is not None else sum(r.cost_usd for r in client.records)
    summary = summarize(graded)
    if open_weights:
        text = render_markdown(
            summary, graded, cost, name="Muse Spark Open (Baseten)",
            model_line=f"(`{MUSE_SPARK_OPEN_MODEL}`, chat completions on Baseten)",
            grades_file=grades_file,
        )  # fmt: skip
    else:
        text = render_markdown(summary, graded, cost)
    out.write_text(text, encoding="utf-8")
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["crop_id", "human", "model_type", "model_severity", "model_confidence"])
    for g in graded:
        a = g.assessment
        writer.writerow(
            [g.crop_id, g.human, a.defect_type if a else "", a.severity if a else "",
             f"{a.confidence:.2f}" if a else ""]
        )  # fmt: skip
    args.csv.with_name(grades_file).write_text(buffer.getvalue(), encoding="utf-8")
    print(
        f"graded {len(graded)} crops: live={sum(r.source == 'live' for r in client.records)} "
        f"cached={sum(r.source == 'cache' for r in client.records)} cost_usd={cost:.4f}; "
        f"kappa={summary.get('kappa_quadratic', float('nan')):.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
