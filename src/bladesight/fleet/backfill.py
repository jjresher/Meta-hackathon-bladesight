"""Fill the provenance and autonomy fields into a store written before they existed. Free.

- Agent runs: `trace.annotate_run` (rationale, decision, outcome, rule, turn, provider per step),
  derived from the stored steps only.
- Work orders: `model` / `provider` of the agent run that created them (`WorkOrder.run_id`).
- Verifications: `model` / `provider` of the second look. Before this field existed, the pipeline
  ran the second look on the same client and model as the severity grade
  (`process.process_image`), so they are taken from the defect's assessment. A verification with
  no assessment is left as it is.

Idempotent: running it twice gives the same store.
"""

from __future__ import annotations

from .store import Store
from .trace import annotate_run


def backfill(store: Store) -> dict[str, int]:
    counts = {"runs": 0, "work_orders": 0, "verifications": 0}
    runs = {}
    if (store.root / "runs").exists():
        for run in store.runs():
            store.save_run(annotate_run(run))
            runs[run.id] = run
            counts["runs"] += 1
    orders = []
    for order in store.work_orders():
        run = runs.get(order.run_id or "")
        if run is not None and order.model is None:
            order = order.model_copy(update={"model": run.model, "provider": run.provider})
            counts["work_orders"] += 1
        orders.append(order)
    if orders:
        store.save_work_orders(orders)
    if (store.root / "inspections").exists():
        for inspection in store.inspections():
            changed = False
            for image in inspection.images:
                for d in image.defects:
                    v, a = d.verification, d.assessment
                    if v is not None and a is not None and v.model is None:
                        d.verification = v.model_copy(
                            update={"model": a.model, "provider": a.provider}
                        )
                        counts["verifications"] += 1
                        changed = True
            if changed:
                store.save_inspection(inspection)
    return counts
