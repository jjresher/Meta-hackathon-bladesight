"""Evidence for the open-weights path (#15) and the agent's autonomy, from the stored replays.

- `autonomy(run, orders)`: what one agent run did, counted from its trace (steps, model turns,
  tool calls by tool, calls that carried the model's own rationale, rejections by rule, orders).
- `render_comparison(meta, open_)`: `docs/evidence/open_weights_farm.md`, the Meta replay vs the
  Muse Spark Open replay of the same stored detections: severity and verdict agreement per
  defect, work-order overlap, and the deterministic farm ranking each one gives.

Everything is read from `replay/` (free). Small n: these are agreement counts, not accuracy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..contracts import AgentRun, InspectedDefect, WorkOrder
from .rank import all_defects, build_fleet
from .store import Store


@dataclass
class Autonomy:
    run_id: str
    model: str
    provider: str
    status: str
    steps: int
    turns: int
    tool_calls: Counter[str] = field(default_factory=Counter)
    with_rationale: int = 0
    rejected: Counter[str] = field(default_factory=Counter)
    orders: Counter[str] = field(default_factory=Counter)
    cost_usd: float = 0.0


def autonomy(run: AgentRun, orders: list[WorkOrder]) -> Autonomy:
    calls = [s for s in run.steps if s.kind == "tool_call"]
    return Autonomy(
        run_id=run.id,
        model=run.model,
        provider=run.provider,
        status=run.status,
        steps=len(run.steps),
        turns=len({s.turn for s in run.steps if s.turn is not None}),
        tool_calls=Counter(s.tool or "?" for s in calls),
        with_rationale=sum(s.rationale is not None for s in calls),
        rejected=Counter(
            s.blocked_by_rule.id if s.blocked_by_rule else "unclassified"
            for s in calls
            if s.outcome == "rejected"
        ),
        orders=Counter(o.kind for o in orders if o.run_id == run.id),
        cost_usd=run.total_cost_usd,
    )


def latest_run(store: Store) -> AgentRun | None:
    if not (store.root / "runs").exists():
        return None
    runs = store.runs()
    return max(runs, key=lambda r: r.started_at) if runs else None


def autonomy_table(items: list[Autonomy]) -> list[str]:
    def fmt(counter: Counter[str]) -> str:
        return ", ".join(f"`{k}` {v}" for k, v in sorted(counter.items())) or "none"

    head = "| | " + " | ".join(f"`{a.run_id}` ({a.model})" for a in items) + " |"
    rows = [
        ("Status", [f"`{a.status}`" for a in items]),
        ("Steps in the trace", [str(a.steps) for a in items]),
        ("Model turns", [str(a.turns) for a in items]),
        ("Tool calls", [str(sum(a.tool_calls.values())) for a in items]),
        ("Tool calls by tool", [fmt(a.tool_calls) for a in items]),
        (
            "Tool calls with the model's own text before them",
            [str(a.with_rationale) for a in items],
        ),
        ("Calls rejected by a tool rule", [str(sum(a.rejected.values())) for a in items]),
        ("Rejections by rule", [fmt(a.rejected) for a in items]),
        ("Work orders", [str(sum(a.orders.values())) for a in items]),
        ("Work orders by kind", [fmt(a.orders) for a in items]),
        ("Agent cost (USD)", [f"{a.cost_usd:.4f}" for a in items]),
    ]
    return [
        head,
        "|---" * (len(items) + 1) + "|",
        *[f"| {name} | " + " | ".join(vals) + " |" for name, vals in rows],
    ]


def _graded(store: Store) -> dict[str, InspectedDefect]:
    return {
        d.defect.id: d
        for i in store.inspections()
        for d in all_defects(i)
        if d.assessment is not None and d.verification is not None
    }


def _spearman(a: list[float], b: list[float]) -> float:
    def ranks(xs: list[float]) -> list[float]:
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        out = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return out

    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def _defects_by_kind(orders: list[WorkOrder]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {"repair": set(), "monitor": set(), "reinspect": set()}
    for o in orders:
        out[o.kind].update(o.defect_ids)
    return out


def render_comparison(
    meta: Store, open_: Store, *, meta_farm_cost: float, open_farm_cost: float
) -> str:
    a, b = _graded(meta), _graded(open_)
    common = sorted(set(a) & set(b))
    pairs = [(a[i], b[i]) for i in common]
    sev = [(x.assessment.severity, y.assessment.severity) for x, y in pairs]  # type: ignore[union-attr]
    same = sum(p == q for p, q in sev)
    within = sum(abs(p - q) <= 1 for p, q in sev)
    n = len(pairs) or 1
    verdicts = ("ok", "needs_review", "reinspect")
    va = Counter(x.verification.verdict for x, _ in pairs)  # type: ignore[union-attr]
    vb = Counter(y.verification.verdict for _, y in pairs)  # type: ignore[union-attr]
    vsame = sum(x.verification.verdict == y.verification.verdict for x, y in pairs)  # type: ignore[union-attr]
    confusion = Counter(
        (x.verification.verdict, y.verification.verdict)  # type: ignore[union-attr]
        for x, y in pairs
    )
    sev_conf = Counter(sev)
    levels = sorted({s for p in sev for s in p})
    ok_both = sum(
        x.verification.verdict == "ok" and y.verification.verdict == "ok"  # type: ignore[union-attr]
        for x, y in pairs
    )
    ok_same_sev = sum(
        x.verification.verdict == "ok"  # type: ignore[union-attr]
        and y.verification.verdict == "ok"  # type: ignore[union-attr]
        and x.assessment.severity == y.assessment.severity  # type: ignore[union-attr]
        for x, y in pairs
    )
    errors_open = sum(d.error is not None for i in open_.inspections() for d in all_defects(i))

    fa = build_fleet(meta.inspections(), [])
    fb = build_fleet(open_.inspections(), [])
    ranks_a = {t.id: t.rank for t in fa.turbines}
    ranks_b = {t.id: t.rank for t in fb.turbines}
    ids = sorted(ranks_a)
    rho = _spearman([ranks_a[t] for t in ids], [ranks_b[t] for t in ids])
    top_a = [t.id for t in fa.turbines[:6]]
    top_b = [t.id for t in fb.turbines[:6]]

    ra, rb = latest_run(meta), latest_run(open_)
    oa = [o for o in meta.work_orders() if ra and o.run_id == ra.id]
    ob = [o for o in open_.work_orders() if rb and o.run_id == rb.id]
    ka, kb = _defects_by_kind(oa), _defects_by_kind(ob)

    def overlap(x: set[str], y: set[str]) -> str:
        union = x | y
        return f"{len(x & y)} of {len(union)} (Meta {len(x)}, Open {len(y)})" if union else "none"

    lines = [
        "# Open weights on the farm: Muse Spark (Meta API) vs Muse Spark Open (Baseten)",
        "",
        "Generated by `uv run poe fleet compare` from `replay/` (Meta) and "
        "`replay/open-weights/` (Open). Both replays share the SAME stored detections and",
        "measurements (Muse Spark box proposals + SAM 3.1 masks from the Meta run): only severity,",
        "the second look, the agent and the report changed model, so the differences below come",
        f"from the chat model. n is small ({len(pairs)} defects, 12 turbines, one run each):",
        "these are agreement counts between two models, not accuracy; neither run is a",
        "reference label.",
        "",
        "## Per defect",
        "",
        f"- Defects graded and verified in both runs: {len(pairs)} (Meta {len(a)}, Open {len(b)}; "
        f"left ungraded after an error in the Open run: {errors_open}).",
        f"- Same severity: **{same} of {len(pairs)}** ({same / n:.0%}); within one level: "
        f"{within} ({within / n:.0%}).",
        f"- Same verdict: **{vsame} of {len(pairs)}** ({vsame / n:.0%}). Verdict counts: Meta "
        + ", ".join(f"`{v}` {va[v]}" for v in verdicts)
        + "; Open "
        + ", ".join(f"`{v}` {vb[v]}" for v in verdicts)
        + ".",
        f"- Verified (`ok`) in both runs: {ok_both}; of those, the same severity in both: "
        f"{ok_same_sev}.",
        "",
        "Severity (rows Meta, columns Open):",
        "",
        "| Meta \\ Open | " + " | ".join(str(s) for s in levels) + " |",
        "|---" * (len(levels) + 1) + "|",
        *[f"| {r} | " + " | ".join(str(sev_conf[(r, c)]) for c in levels) + " |" for r in levels],
        "",
        "Verdict (rows Meta, columns Open):",
        "",
        "| Meta \\ Open | " + " | ".join(f"`{v}`" for v in verdicts) + " |",
        "|---|---|---|---|",
        *[
            f"| `{r}` | " + " | ".join(str(confusion[(r, c)]) for c in verdicts) + " |"
            for r in verdicts
        ],
        "",
        "## Farm ranking (deterministic score of verified defects, `fleet/rank.py`)",
        "",
        f"- Spearman rank correlation over the {len(ids)} turbines: {rho:.2f}.",
        f"- Top 6: Meta {', '.join(top_a)}; Open {', '.join(top_b)}; "
        f"in both: {len(set(top_a) & set(top_b))} of 6.",
        "",
        "| Turbine | Meta rank | Open rank |",
        "|---|---|---|",
        *[f"| {t} | {ranks_a[t]} | {ranks_b[t]} |" for t in sorted(ids, key=lambda t: ranks_a[t])],
        "",
        "## Work orders (each agent's own run)",
        "",
        f"- Meta run `{ra.id if ra else '-'}`: {len(oa)} orders; Open run "
        f"`{rb.id if rb else '-'}`: {len(ob)} orders.",
        f"- Defects in a repair order in both runs: {overlap(ka['repair'], kb['repair'])}.",
        f"- Defects in a monitor order in both runs: {overlap(ka['monitor'], kb['monitor'])}.",
        f"- Defects in a re-inspection request in both runs: "
        f"{overlap(ka['reinspect'], kb['reinspect'])}.",
        f"- Turbines with any order: Meta {sorted({o.turbine_id for o in oa})}; Open "
        f"{sorted({o.turbine_id for o in ob})}.",
        "",
        "## Agent autonomy (from each trace)",
        "",
        *autonomy_table([autonomy(r, o) for r, o in ((ra, oa), (rb, ob)) if r is not None]),
        "",
        "## Cost (documented prices x real usage, not invoice-checked)",
        "",
        f"- Grading + second look of the farm: Meta {meta_farm_cost:.4f} USD (the runs",
        "  behind the store, cumulative, see `docs/limitations.md`); Open "
        f"{open_farm_cost:.4f} USD (severity and second look only; detection reused).",
        f"- Agent run with its report: Meta {ra.total_cost_usd if ra else 0:.4f} USD; Open "
        f"{rb.total_cost_usd if rb else 0:.4f} USD.",
    ]
    return "\n".join(lines) + "\n"
