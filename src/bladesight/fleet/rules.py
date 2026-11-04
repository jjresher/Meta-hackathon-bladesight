"""The rules the agent's tools enforce in code, with stable ids for the trace.

Each rule is raised by exactly one kind of `ToolError` in `tools.py`. The tool result the model
reads is unchanged (so recorded runs still replay from the cache). The rule id is recovered from
the error text by `rule_for_error`: the messages are fixed strings in `tools.py`, so the mapping is
exact, and an unrecognised error maps to no rule rather than a guess.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..contracts import RuleRef


@dataclass(frozen=True)
class Rule:
    id: str
    text: str
    pattern: re.Pattern[str]  # matches the start of the tool's error message

    def ref(self) -> RuleRef:
        return RuleRef(id=self.id, text=self.text)


def _rule(rule_id: str, text: str, prefix: str) -> Rule:
    return Rule(rule_id, text, re.compile(prefix))


RULES: dict[str, Rule] = {
    r.id: r
    for r in (
        _rule(
            "verified_only",
            "A repair or monitor work order may only cite defects whose verification verdict "
            "is ok.",
            r"no work order without a verified assessment",
        ),
        _rule(
            "reinspect_unverified_only",
            "Re-inspection is only for defects that are not verified; verified ones get a work "
            "order.",
            r"these defects are already verified \(ok\)",
        ),
        _rule(
            "assessed_before_reinspection",
            "A defect must have been assessed before a re-inspection can be requested.",
            r"\S+ was never assessed",
        ),
        _rule(
            "defects_in_inspection",
            "Every cited defect must exist in the named inspection.",
            r"defects not in ",
        ),
        _rule(
            "cite_a_defect",
            "Every order cites at least one defect id.",
            r"cite at least one defect id",
        ),
        _rule(
            "order_kind",
            "A work order is a repair or a monitor order; anything else is a re-inspection.",
            r"kind must be 'repair' or 'monitor'",
        ),
        _rule("order_priority", "Priority is P1, P2 or P3.", r"priority must be P1, P2 or P3"),
        _rule(
            "report_cites_existing_orders",
            "The report may only cite work orders that exist.",
            r"the report cites work orders that do not exist",
        ),
        _rule(
            "report_cites_assessed_defects",
            "The report may only cite defects that were assessed and verified.",
            r"the report cites defects that were not assessed",
        ),
        _rule(
            "two_inspections_to_compare",
            "A comparison needs two inspections of the turbine.",
            r"\S+ has fewer than two inspections",
        ),
        _rule("known_image", "Image ids must exist in the store.", r"unknown image "),
        _rule("known_tool", "Only the seven fleet tools exist.", r"unknown tool "),
        _rule(
            "known_ids",
            "Inspection and defect ids must exist, and required arguments must be given.",
            r"unknown id or missing argument",
        ),
        _rule("valid_arguments", "Arguments must have the documented types.", r"bad arguments"),
    )
}


def rule_for_error(message: str) -> Rule | None:
    """The rule behind a tool error message, or None if the message is not one of ours."""
    for rule in RULES.values():
        if rule.pattern.match(message):
            return rule
    return None


def error_of(result: str) -> str | None:
    """The `error` field of a tool result (JSON text), or None when the call was accepted.

    Stored traces cut results at 700 characters, so a cut JSON is read with a regex instead.
    """
    try:
        payload = json.loads(result)
    except ValueError:
        found = re.match(r'\{"error":"((?:[^"\\]|\\.)*)', result)
        return found.group(1) if found else None
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        return payload["error"]
    return None
