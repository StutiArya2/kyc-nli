"""Non-neural baselines. These are what the neural model has to beat."""

from typing import Protocol, runtime_checkable

from kyc_nli.baselines.exact import ExactMatchBaseline
from kyc_nli.baselines.rules import RuleBaseline, RuleConfig
from kyc_nli.schema import Instance, Prediction


@runtime_checkable
class NLISystem(Protocol):
    """What every scorable system must look like.

    This is the interface CLAUDE.md documents for adding a baseline, written
    down so a type checker can enforce it. The cross-encoder implements exactly
    the same one: a model scored through a different code path than its baseline
    is a model whose comparison nobody can check.

    ``predict_all`` is deliberately not part of it. Batching is a performance
    detail -- same predictions, same order -- so a system that does not batch
    must not be forced to pretend it does. Callers probe for it.
    """

    name: str

    def predict(self, instance: Instance) -> Prediction: ...

BASELINES = {
    ExactMatchBaseline.name: ExactMatchBaseline,
    RuleBaseline.name: RuleBaseline,
}


def available_systems() -> dict[str, type[NLISystem]]:
    """Baselines plus the trained cross-encoder, when one exists on disk.

    The neural model lives behind an optional extra and a trained checkpoint, so
    it joins the comparison only when both are present. Everything else in the
    harness treats it identically to a baseline.
    """
    systems = dict(BASELINES)
    try:
        from kyc_nli.languages import repo_root
        from kyc_nli.nli.model import DEFAULT_MODEL_DIR, CrossEncoderNLI

        # Check for an actual checkpoint file, not just the directory: a
        # training run creates the directory immediately and only writes weights
        # after the first epoch, so a dir-only check makes `compare` and `demo`
        # fail with a tokenizer error for hours while training is in flight.
        if (repo_root() / DEFAULT_MODEL_DIR / "config.json").is_file():
            systems[CrossEncoderNLI.name] = CrossEncoderNLI
    except ImportError:  # torch/transformers not installed
        pass
    return systems

__all__ = [
    "BASELINES",
    "ExactMatchBaseline",
    "NLISystem",
    "RuleBaseline",
    "RuleConfig",
    "available_systems",
]
