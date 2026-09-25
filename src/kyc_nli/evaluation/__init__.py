"""Scoring and reporting."""

from kyc_nli.evaluation.metrics import (
    EvaluationReport,
    OperatingPoint,
    evaluate,
    review_load_at_error,
    risk_coverage,
    selective_curve,
)
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
    "OperatingPoint",
    "bootstrap_macro_f1",
    "evaluate",
    "paired_bootstrap",
    "review_load_at_error",
    "risk_coverage",
    "selective_curve",
]
