# Severity agreement: Muse Spark vs the human labels (issue #10)

**What this measures.** The 40 gold crops were labelled by one person with no wind-energy
experience, applying `docs/rubric.md` (our own illustrative rubric, observable criteria) blind to
the model on these crops. This file reports how much Muse Spark agrees with that person
applying the rubric. It is agreement with the rubric applied by a non-specialist, **not**
severity validated by a wind-turbine specialist.

Crops: the dataset's own damage boxes (one per source photo, four size quartiles, seed 20261030;
`eval/gold/severity.csv` holds ids, boxes and the human labels, no images). Muse Spark
(`muse-spark-1.3`, `reasoning.effort=low`, `store=false`) graded the same crops the labeller saw,
with the `assess/v1` prompt and without a detector confidence (the boxes come from the dataset).
Model grades are in `eval/gold/model_grades.csv`. Cost of the run: 0.1515 USD (documented
prices, not invoice-checked).

## Counts

- Crops: 40; compared: 40.
- Labelled 0 (unreadable) by the human: 0; they
  are left out of the kappa and the confusion matrix (model grades on them: none).
- Model failures (no valid grade after one retry): 0.
- Human severity distribution: {1: 10, 2: 5, 3: 14, 4: 9, 5: 2}.
- Model severity distribution: {1: 29, 2: 6, 3: 5}.

## Agreement (n = 40)

- Quadratic weighted kappa: **0.12** (95% bootstrap interval -0.05 to 0.29)
  (linear weighted kappa 0.05).
- Exact agreement: 25%; within one level: 48%; mean (model - human):
  -1.30 levels.

**Reading.** The model grades lower than the human on average and mostly at the bottom of the scale; kappa near zero means agreement barely above chance. Severity shown by the product is therefore advisory, and the verification layer (second look, abstention) is the safety net, not a certification of the grade.

## Confusion matrix (rows: human, columns: model)

| human \ model | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| 1 | 8 | 1 | 1 | 0 | 0 |
| 2 | 4 | 1 | 0 | 0 | 0 |
| 3 | 10 | 3 | 1 | 0 | 0 |
| 4 | 7 | 1 | 1 | 0 | 0 |
| 5 | 0 | 0 | 2 | 0 | 0 |

## Limits

- One rater without domain experience and no second rater: there is no inter-rater agreement, so
  the ceiling for the model's agreement is unknown.
- n = 40 gives a wide interval; the crops are dataset boxes selected by size quartile, so large
  boxes are over-represented relative to the dataset (73% of the boxes in the 20-tile spike
  sample are under 400 px^2).
- The labeller wrote the rubric and had seen earlier model gradings (issue #7); the page only hid
  the grades for these crops. The model also receives measurements as text that the human does not.
- The kappa compares two ratings of the same crops; it says nothing about whether either is right.
