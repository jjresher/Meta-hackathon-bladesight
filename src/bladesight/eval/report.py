"""Write the evaluation as the `EvalReport` contract, a Markdown evidence file and an SVG curve."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from ..contracts import ClassMetrics, EvalReport, Interval, SweepPoint
from .metrics import (
    IOU_LEVELS,
    LABELS,
    PRIMARY_IOU,
    TileResult,
    aggregate,
    bootstrap,
    error_gallery,
    image_level,
    sweep,
)

MAX_IDS_PER_CAUSE = 12
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 20261029


def _class_metrics(
    results: Sequence[TileResult], iou: float, with_ci: bool, n_boot: int
) -> list[ClassMetrics]:
    out = []
    for label in LABELS:
        c = aggregate(results, label, iou)
        ci = bootstrap(results, label, iou, n_boot) if with_ci and results else None
        out.append(
            ClassMetrics.model_validate(
                {
                    "label": label,
                    "tp": c.tp,
                    "fp": c.fp,
                    "fn": c.fn,
                    "precision": c.precision,
                    "recall": c.recall,
                    "f1": c.f1,
                    "precision_ci": Interval(low=ci.precision.low, high=ci.precision.high)
                    if ci
                    else None,
                    "recall_ci": Interval(low=ci.recall.low, high=ci.recall.high) if ci else None,
                }
            )
        )
    return out


def build_report(
    split: str,
    results: Sequence[TileResult],
    *,
    cost_usd: float,
    evidence_path: str,
    n_boot: int = BOOTSTRAP_N,
    needs_review_share: float | None = None,
    sample_note: str | None = None,
) -> EvalReport:
    damage = image_level(results, "damage")
    return EvalReport.model_validate(
        {
            "split": split,
            "n_images": len(results),
            "iou_threshold": PRIMARY_IOU,
            "classes": _class_metrics(results, PRIMARY_IOU, True, n_boot),
            "classes_iou50": _class_metrics(results, 0.5, False, n_boot),
            "image_recall": damage["image_recall"],
            "sweep": [
                SweepPoint(
                    threshold=p["threshold"],
                    recall=p["recall"],
                    precision=p["precision"],
                    false_alarms_per_image=p["false_alarms_per_image"],
                )
                for p in sweep(results)
            ],
            "needs_review_share": needs_review_share,
            "prompt_versions": {
                "propose": "detect/v1",
                "assess": "assess/v1",
                "verify": "verify/v1",
            },
            "cost_usd": cost_usd,
            "evidence_path": evidence_path,
            "sample_note": sample_note,
            "generated_at": datetime.now(UTC),
        }
    )


def sweep_svg(points: Sequence[SweepPoint], width: int = 520, height: int = 320) -> str:
    """Recall (y) against false alarms per image (x), one point per score threshold."""
    margin = 48
    xs = [p.false_alarms_per_image for p in points] or [0.0]
    x_max = max(max(xs), 0.1) * 1.1

    def x(v: float) -> float:
        return margin + (width - 2 * margin) * v / x_max

    def y(v: float) -> float:
        return height - margin - (height - 2 * margin) * v

    path = " ".join(
        f"{'M' if i == 0 else 'L'}{x(p.false_alarms_per_image):.1f},{y(p.recall):.1f}"
        for i, p in enumerate(sorted(points, key=lambda p: p.false_alarms_per_image))
    )
    dots = "".join(
        f'<circle cx="{x(p.false_alarms_per_image):.1f}" cy="{y(p.recall):.1f}" r="3"/>'
        f'<text x="{x(p.false_alarms_per_image) + 5:.1f}" y="{y(p.recall) - 5:.1f}" font-size="9">'
        f"{p.threshold:g}</text>"
        for p in points
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Damage recall against false alarms per image, by score threshold" '
        f'font-family="sans-serif" fill="#1a1a1a" stroke="none">'
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>'
        f'<g stroke="#1a1a1a" stroke-width="1"><line x1="{margin}" y1="{height - margin}" '
        f'x2="{width - margin}" y2="{height - margin}"/><line x1="{margin}" y1="{margin}" '
        f'x2="{margin}" y2="{height - margin}"/></g>'
        f'<path d="{path}" fill="none" stroke="#c0392b" stroke-width="2"/>'
        f'<g fill="#c0392b">{dots}</g>'
        f'<text x="{width / 2}" y="{height - 10}" font-size="11" text-anchor="middle">'
        f"false alarms per image</text>"
        f'<text x="14" y="{height / 2}" font-size="11" text-anchor="middle" '
        f'transform="rotate(-90 14 {height / 2})">damage recall (IoU 0.3)</text>'
        f'<text x="{width / 2}" y="16" font-size="12" text-anchor="middle">'
        f"Damage: recall vs false alarms (labels: score threshold)</text></svg>"
    )


def render_markdown(
    report: EvalReport,
    results: Sequence[TileResult],
    *,
    title: str,
    command: str,
    notes: Sequence[str] = (),
    svg_name: str = "sweep.svg",
) -> str:
    damage = image_level(results, "damage")
    gallery = error_gallery(results, "damage")
    lines = [
        f"# {title}",
        "",
        f"Command: `{command}`. Split: `{report.split}`. Tiles: {report.n_images} "
        f"({int(damage['tiles_with_truth'])} with damage boxes, "
        f"{int(damage['clean_tiles'])} with no box at all). Cost: {report.cost_usd:.4f} USD "
        "(documented prices, not invoice-checked).",
        "",
        *notes,
        "",
        "## Box matching (IoU 0.3 primary, 0.5 also reported)",
        "",
        "| Class | TP | FP | FN | Precision (95% CI) | Recall (95% CI) | F1 | Recall IoU 0.5 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    by50 = {c.label: c for c in report.classes_iou50}
    for c in report.classes:
        p, r = c.precision_ci, c.recall_ci
        lines.append(
            f"| {c.label} | {c.tp} | {c.fp} | {c.fn} | {c.precision:.3f}"
            f" ({p.low:.3f}-{p.high:.3f}) | {c.recall:.3f} ({r.low:.3f}-{r.high:.3f}) | "
            f"{c.f1:.3f} | {by50[c.label].recall:.3f} |"
            if p and r
            else f"| {c.label} | {c.tp} | {c.fp} | {c.fn} | {c.precision:.3f} | {c.recall:.3f} | "
            f"{c.f1:.3f} | {by50[c.label].recall:.3f} |"
        )
    lines += [
        "",
        f"Intervals: bootstrap over tiles ({BOOTSTRAP_N} resamples, seed {BOOTSTRAP_SEED}); "
        "tiles of one photo are correlated, so the intervals are probably a little too narrow. "
        "Precision is reported as 0 when there are no predictions.",
        "",
        "## Image level and lenient overlap (damage)",
        "",
        f"- Image-level recall (a damaged tile has at least one damage prediction): "
        f"**{damage['image_recall']:.3f}** over {int(damage['tiles_with_truth'])} tiles.",
        "- False-alarm rate on tiles with no box at all: "
        f"**{damage['clean_false_alarm_rate']:.3f}** over {int(damage['clean_tiles'])} tiles.",
        f"- Truth boxes touched by any damage prediction (any overlap): "
        f"**{damage['touch_recall']:.3f}** of {int(damage['truth_boxes'])}.",
        "",
        "## Threshold sweep (damage, IoU 0.3)",
        "",
        "| Score threshold | Recall | Precision | False alarms per image |",
        "|---|---|---|---|",
        *[
            f"| {p.threshold:g} | {p.recall:.3f} | {p.precision:.3f} | "
            f"{p.false_alarms_per_image:.3f} |"
            for p in report.sweep
        ],
        "",
        f"![Damage recall vs false alarms]({svg_name})",
        "",
        "## Error gallery (tile ids, damage; crops are never committed)",
        "",
        *[
            f"- `{cause}` ({len(ids)}): {', '.join(ids[:MAX_IDS_PER_CAUSE]) or '-'}"
            + (" ..." if len(ids) > MAX_IDS_PER_CAUSE else "")
            for cause, ids in gallery.items()
        ],
        "",
        f"Prompt versions: {report.prompt_versions}. IoU levels computed: {list(IOU_LEVELS)}.",
    ]
    if report.needs_review_share is not None:
        lines += ["", f"Share of defects sent to review: {report.needs_review_share:.3f}."]
    return "\n".join(lines) + "\n"


def write_outputs(
    report: EvalReport,
    results: Sequence[TileResult],
    out_dir: Path,
    stem: str,
    *,
    title: str,
    command: str,
    notes: Sequence[str] = (),
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md, svg = out_dir / f"{stem}.md", out_dir / f"{stem}_sweep.svg"
    md.write_text(
        render_markdown(report, results, title=title, command=command, notes=notes), "utf-8"
    )
    svg.write_text(sweep_svg(report.sweep), encoding="utf-8")
    return md, svg
