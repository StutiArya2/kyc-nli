"""Edge cases for the fine-tuning path.

`train()` produced the project's headline number and was executed by no test at
all. Most of it cannot be checked cheaply -- it is a training loop -- but two
things can, and both are load-bearing:

1. `_macro_f1` is a *reimplementation* of the metric. The dev score in
   `training_summary.json`, and therefore the "epoch 2 improved on epoch 1"
   claim in the M3 findings, comes from this function and not from sklearn. If
   the two disagree, the training log and the results table are measuring
   different things.
2. The loop runs end to end and writes a loadable checkpoint. That is the
   `slow` test at the bottom: a minute of real fine-tuning, deselected by
   default, and the only thing that would have caught a change breaking the
   9-hour run before the 9 hours were spent.
"""

from __future__ import annotations

import json
import random

import pytest
from sklearn.metrics import f1_score

from kyc_nli.nli.train import TrainConfig, _macro_f1

# --------------------------------------------------------------------------
# _macro_f1 against the reference implementation
# --------------------------------------------------------------------------


def test_the_hand_rolled_macro_f1_agrees_with_sklearn_on_random_inputs() -> None:
    """1000 random confusion patterns. A metric that agrees only on the easy
    cases is a metric that will disagree on the reported one."""
    rng = random.Random(4)
    for _ in range(1000):
        n = rng.randint(1, 30)
        gold = [rng.randrange(3) for _ in range(n)]
        pred = [rng.randrange(3) for _ in range(n)]
        expected = f1_score(gold, pred, labels=[0, 1, 2], average="macro", zero_division=0)
        assert _macro_f1(gold, pred) == pytest.approx(expected)


def test_a_perfect_prediction_scores_one() -> None:
    assert _macro_f1([0, 1, 2, 0], [0, 1, 2, 0]) == pytest.approx(1.0)


def test_a_class_that_never_appears_contributes_zero_not_nan() -> None:
    """Macro-F1 divides by three regardless. A NaN here would propagate into the
    'best dev score' comparison and quietly disable early stopping."""
    score = _macro_f1([0, 0, 1], [0, 0, 1])
    assert score == pytest.approx(2 / 3)


def test_predicting_one_class_for_everything_is_scored_as_the_failure_it_is() -> None:
    """The degenerate collapse a frozen-embedding CPU run is most at risk of."""
    assert _macro_f1([0, 1, 2] * 5, [0] * 15) < 0.2


def test_mismatched_lengths_raise_rather_than_truncating() -> None:
    """`zip` without strict= silently scores the shorter list and reports a
    number for a run that was never fully evaluated."""
    with pytest.raises(ValueError):
        _macro_f1([0, 1, 2], [0, 1])


# --------------------------------------------------------------------------
# TrainConfig
# --------------------------------------------------------------------------


def test_the_config_defaults_are_the_ones_the_published_run_used() -> None:
    """The M3 findings say distilbert, frozen embeddings, CPU. If the defaults
    drift, `python scripts/train_cross_encoder.py` stops reproducing them."""
    config = TrainConfig()
    assert config.base_model == "distilbert-base-multilingual-cased"
    assert config.freeze_embeddings is True
    assert config.device == "cpu"
    assert config.seed == 20260906


def test_the_config_round_trips_through_json() -> None:
    """It is written into training_summary.json as the record of the run."""
    from dataclasses import asdict

    config = TrainConfig(epochs=2, max_train=16)
    assert json.loads(json.dumps(asdict(config)))["epochs"] == 2


# --------------------------------------------------------------------------
# The loop itself
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_a_few_steps_of_real_fine_tuning_produce_a_loadable_checkpoint(tmp_path) -> None:
    """End to end: tokenise, freeze, step, evaluate, save, and load back.

    Deliberately tiny -- 16 training instances, 12 dev, one epoch -- because the
    point is the plumbing, not the score. The score is asserted only to be a
    real number in range; a model that has seen 16 examples has learned nothing
    and should not be expected to.
    """
    pytest.importorskip("torch")
    pytest.importorskip("transformers")

    from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
    from kyc_nli.data.io import save_instances, split_by_identity
    from kyc_nli.languages import load_languages
    from kyc_nli.nli.train import train

    generated = InstanceGenerator(
        GeneratorConfig(languages=tuple(load_languages()), identities_per_language=3, seed=5)
    ).generate()
    splits = split_by_identity(generated)
    train_path = save_instances(splits["train"][:16], tmp_path / "train.jsonl")
    dev_path = save_instances(splits["test"][:12], tmp_path / "dev.jsonl")

    config = TrainConfig(
        train_path=str(train_path),
        dev_path=str(dev_path),
        output_dir=str(tmp_path / "ckpt"),
        epochs=1,
        batch_size=4,
        max_length=64,
    )
    summary = train(config, log=lambda *_: None)

    assert len(summary["history"]) == 1
    assert 0.0 <= summary["best_dev_macro_f1"] <= 1.0
    assert summary["n_train"] == 16

    checkpoint = tmp_path / "ckpt"
    assert (checkpoint / "config.json").exists(), "no config.json -- the model will not load"
    assert (checkpoint / "training_summary.json").exists(), "the run left no record of itself"

    # The checkpoint must be usable by the same interface the baselines expose,
    # or it will not appear in `kyc-nli compare` and cannot be scored.
    from kyc_nli.nli.model import CrossEncoderNLI

    predictions = CrossEncoderNLI(str(checkpoint)).predict_all(splits["test"][:4])
    assert len(predictions) == 4
    assert all(0.0 <= p.confidence <= 1.0 for p in predictions)
