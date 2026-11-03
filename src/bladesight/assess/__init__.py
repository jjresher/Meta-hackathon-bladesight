"""Severity assessment with Muse Spark against `docs/rubric.md` (issue #7)."""

from .assess import RUBRIC_VERSION, AssessError, assess_defect, parse_assessment

__all__ = ["RUBRIC_VERSION", "AssessError", "assess_defect", "parse_assessment"]
