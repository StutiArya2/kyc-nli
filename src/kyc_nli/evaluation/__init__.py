"""Scoring and reporting."""

from kyc_nli.evaluation.metrics import EvaluationReport, evaluate, risk_coverage
from kyc_nli.evaluation.significance import (
    DEFAULT_RESAMPLES,
    Comparison,
    Interval,
    bootstrap_macro_f1,
    paired_bootstrap,
)

__all__ = [
    "DEFAULT_RESAMPLES",
    "Comparison",
    "EvaluationReport",
    "Interval",
    "bootstrap_macro_f1",
    "evaluate",
    "paired_bootstrap",
    "risk_coverage",
]
