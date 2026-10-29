# Known limitations

What does not work or is not covered, its impact, and the issue that owns it. Shown honestly in
the README and the Evaluation page. See skill `write-decision`.

- The fleet is synthetic: real DTU photos of one Nordtank turbine grouped into 12 turbines for the demo — impact: rankings illustrate the method, not a real farm — issue: #11
- Sizes are relative (pixels and share of blade area), not millimetres: tiles carry no scale — impact: severity relies on relative size and appearance — issue: #6
- Severity has no public ground truth; it is graded against our own illustrative rubric and checked on a small hand-labelled set — issue: #7, #10
