"""Non-neural baselines. These are what the neural model has to beat."""

from kyc_nli.baselines.exact import ExactMatchBaseline
from kyc_nli.baselines.rules import RuleBaseline, RuleConfig

BASELINES = {
    ExactMatchBaseline.name: ExactMatchBaseline,
    RuleBaseline.name: RuleBaseline,
}

__all__ = ["BASELINES", "ExactMatchBaseline", "RuleBaseline", "RuleConfig"]
