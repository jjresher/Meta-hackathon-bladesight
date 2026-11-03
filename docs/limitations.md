# Known limitations

What does not work or is not covered, its impact, and the issue that owns it. Shown honestly in
the README and the Evaluation page. See skill `write-decision`.

- The fleet is synthetic: real DTU photos of one Nordtank turbine grouped into 12 turbines for the demo — impact: rankings illustrate the method, not a real farm — issue: #11
- Sizes are relative (pixels and share of blade area), not millimetres: tiles carry no scale — impact: severity relies on relative size and appearance — issue: #6
- Severity has no public ground truth; it is graded against our own illustrative rubric and checked on a small hand-labelled set — issue: #7, #10
- The git/gh restrictions on agents are only partly enforced: the `deny` rules in `.claude/settings.json` are prefix patterns, so flags after the branch name, `git -C <dir> push`, `--amend`, `git config user.*`, `gh api -X ...` and similar are not matched. The rest is enforced by instruction (`AGENTS.md` rule 9) and by GitHub branch protection on `main`, which only the human can configure — impact: an agent could break a rule by accident; the human merges every PR — issue: #1
- The API contract checks shapes, not cross-object invariants (summary counts vs images, unique turbine ranks, box corner order, step order); only the example fixtures are checked for consistency by a test, and fixtures are validated by pydantic, not by a JSON Schema validator — impact: the pipeline must build consistent objects itself — issue: #12
- The contract has no per-class threshold sweep, operating-point marker, error-gallery entries or severity confusion matrix in `EvalReport`, no per-defect 2017-vs-2018 comparison object and no structured tool result in `AgentStep` (text only); `WorkOrder.evidence` is free text, so the "verified assessment only" rule must be enforced in the agent's `create_work_order` tool — impact: extend the contract (minor version) when #9, #10, #11 need it — issue: #9, #10, #11
- Tiles are served from the gitignored `data/`, so the Render image must fetch or bake the demo tiles at build time, or the inspection viewer shows broken images — issue: #14
