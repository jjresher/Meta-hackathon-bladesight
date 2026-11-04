# Open weights: Muse Spark Open on Baseten vs the Meta Model API (issue #15)

Same 40 gold crops, same labeller's labels, same `assess/v1` prompt, same crops (`gold.crop_for`),
no detector confidence. Models: Muse Spark `muse-spark-1.3` (Meta Model API, low reasoning effort, requests
not stored) and Muse Spark Open `meta-models/muse-spark-open` (Baseten, OpenAI-compatible chat
completions; its id comes from the Baseten `/v1/models` listing of the account: the plan's
`-1026` suffix returned 404). Reproduce: `uv run python -m bladesight.eval.agreement --provider
baseten` (the Meta run: `--provider meta`). Costs are documented prices times real usage, not
invoice-checked. As in `severity_agreement.md`, the labels are one non-specialist applying
`docs/rubric.md`: this is agreement with the rubric applied by that person.

| | Muse Spark (Meta Model API) | Muse Spark Open (Baseten) |
|---|---|---|
| Valid grades | 40 of 40 | 40 of 40 (needs a 6,000-token output budget, see below) |
| Quadratic weighted kappa (95% interval) | 0.12 (-0.05 to 0.29) | 0.19 (0.01 to 0.38) |
| Exact agreement / within one level | 25% / 48% | 30% / 55% |
| Mean (model - human) | -1.30 levels | -1.20 levels |
| Model severity distribution | {1: 29, 2: 6, 3: 5} | {1: 27, 2: 6, 3: 7} |
| Cost of the 40 crops | 0.1515 USD | 0.4195 USD (about 2.8x) |
| Evidence | [`severity_agreement.md`](severity_agreement.md) | [`severity_agreement_open_weights.md`](severity_agreement_open_weights.md) |

- The two models give the **same severity on 32 of the 40 crops** (`eval/gold/model_grades.csv`
  vs `model_grades_open_weights.csv`). Both grade mostly 1 and neither grades above 3.
- The kappa difference (0.19 vs 0.12) is inside the overlap of the two intervals at n = 40:
  we do not claim the open model is better, only that it is **comparable** on this check, with a
  wide interval.
- Muse Spark Open reasons before it answers and the reasoning counts against the output budget: at
  1,500 tokens it returned an empty reply on 23 of 40 crops (that first attempt, 0.45 USD, was
  discarded and is why Baseten spend in total is about 0.89 USD); at 6,000 tokens all 40 were valid.
- Baseten image input accepted the OpenAI-style `image_url` data URLs (confirmed on the live API);
  no retry or 4xx on the final run.
- Not done in this sprint: the fleet agent and the report on open weights, and the UI badge that
  shows which model produced each assessment (every `Assessment` already carries `model` and
  `provider` in the API). Detection stays on SAM 3.1, which has no open-weights path here.
