"""Neural NLI models.

Phase 1 of the plan. The model is a cross-encoder over (serialised document,
claim) pairs, exposing the same ``predict`` interface as the rule baselines so
the existing evaluation harness scores it with no special-casing.

Requires the ``nli`` extra: pip install -e ".[nli]"
"""

from kyc_nli.nli.dataset import LABELS, serialise_hypothesis, serialise_premise, to_pairs

__all__ = ["LABELS", "serialise_hypothesis", "serialise_premise", "to_pairs"]
