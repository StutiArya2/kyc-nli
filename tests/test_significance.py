"""Bootstrap and significance tests."""

from __future__ import annotations

import pytest
from sklearn.metrics import f1_score

from kyc_nli.baselines import ExactMatchBaseline, RuleBaseline
from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.evaluation.significance import (
    LABEL_ORDER,
    _encode,
    _macro_f1,
    bootstrap_macro_f1,
    paired_bootstrap,
)


@pytest.fixture(scope="module")
def scored():
    instances = InstanceGenerator(
        GeneratorConfig(identities_per_language=15, seed=5)
    ).generate()
    rules = RuleBaseline()
    exact = ExactMatchBaseline()
    return (
        instances,
        [rules.predict(i) for i in instances],
        [exact.predict(i) for i in instances],
    )


def test_macro_f1_matches_sklearn(scored) -> None:
    """Our fast macro-F1 must agree with the reference implementation.

    The bootstrap calls it thousands of times, so it is hand-written for speed.
    That is only acceptable if it gives the same answer.
    """
    instances, rule_preds, _ = scored
    gold, pred, _ = _encode(instances, rule_preds)
    reference = f1_score(gold, pred, average="macro", labels=range(len(LABEL_ORDER)))
    assert _macro_f1(gold, pred) == pytest.approx(reference, abs=1e-12)


def test_interval_contains_the_point_estimate(scored) -> None:
    instances, rule_preds, _ = scored
    ci = bootstrap_macro_f1(instances, rule_preds, n_resamples=300, seed=1)
    assert ci.low <= ci.point <= ci.high
    assert 0.0 < ci.width < 0.5


def test_bootstrap_is_deterministic(scored) -> None:
    """Same seed, same interval. Every number must be reproducible."""
    instances, rule_preds, _ = scored
    a = bootstrap_macro_f1(instances, rule_preds, n_resamples=200, seed=42)
    b = bootstrap_macro_f1(instances, rule_preds, n_resamples=200, seed=42)
    assert (a.low, a.point, a.high) == (b.low, b.point, b.high)


def test_the_interval_does_not_depend_on_the_order_instances_arrive_in(scored) -> None:
    """Same data, same seed, any order -> the same interval.

    The test above holds the order fixed, so it could not see this. The
    resampler draws groups by position, and groups used to be built in arrival
    order: a split evaluated straight from the generator (shuffled) and the same
    split read back from disk (sorted by id) gave different intervals --
    [0.566, 0.637] against [0.565, 0.640] for the rule engine. A confidence
    interval that moves when a file is reordered is not reproducible.
    """
    import random

    instances, rule_preds, exact_preds = scored
    shuffled = list(instances)
    random.Random(7).shuffle(shuffled)
    reversed_ = list(reversed(instances))

    base = bootstrap_macro_f1(instances, rule_preds, n_resamples=300, seed=11)
    for order in (shuffled, reversed_):
        again = bootstrap_macro_f1(order, rule_preds, n_resamples=300, seed=11)
        assert (again.low, again.point, again.high) == (base.low, base.point, base.high)

    # The paired test resamples the same way, so it must be order-invariant too.
    a = paired_bootstrap(instances, rule_preds, exact_preds, "r", "e", n_resamples=300, seed=11)
    b = paired_bootstrap(shuffled, rule_preds, exact_preds, "r", "e", n_resamples=300, seed=11)
    assert (a.low, a.delta, a.high, a.p_value) == (b.low, b.delta, b.high, b.p_value)


def test_group_resampling_gives_wider_intervals_than_instance_resampling(scored) -> None:
    """The justification for the whole design, made testable.

    Instances in a contrast group share a premise, so their outcomes correlate.
    Resampling instances independently treats correlated observations as
    independent and understates the variance. If this test ever fails, the
    resampling unit has been changed and every reported interval is too narrow.
    """
    instances, rule_preds, _ = scored

    # Strip the grouping: each instance becomes its own resampling unit.
    ungrouped = [i.model_copy(update={"contrast_group_id": None}) for i in instances]

    grouped_ci = bootstrap_macro_f1(instances, rule_preds, n_resamples=500, seed=7)
    instance_ci = bootstrap_macro_f1(ungrouped, rule_preds, n_resamples=500, seed=7)

    assert grouped_ci.width > instance_ci.width, (
        f"group-level width {grouped_ci.width:.4f} is not wider than "
        f"instance-level {instance_ci.width:.4f} -- correlated observations are "
        f"being treated as independent"
    )


def test_paired_bootstrap_detects_a_large_real_difference(scored) -> None:
    instances, rule_preds, exact_preds = scored
    cmp = paired_bootstrap(
        instances, rule_preds, exact_preds, "rule_engine", "exact_match", n_resamples=300
    )
    assert cmp.delta > 0.25
    assert cmp.significant
    assert cmp.low > 0
    assert cmp.p_value < 0.01


def test_paired_bootstrap_finds_no_difference_between_a_system_and_itself(scored) -> None:
    """The null case. A test that only ever fires positive proves nothing."""
    instances, rule_preds, _ = scored
    cmp = paired_bootstrap(
        instances, rule_preds, rule_preds, "rules", "rules", n_resamples=300
    )
    assert cmp.delta == pytest.approx(0.0, abs=1e-12)
    assert not cmp.significant


def test_report_carries_an_interval_when_asked(scored) -> None:
    from kyc_nli.evaluation import evaluate

    instances, rule_preds, _ = scored
    assert evaluate("r", instances, rule_preds).macro_f1_ci is None
    report = evaluate("r", instances, rule_preds, bootstrap=200)
    assert report.macro_f1_ci is not None
    assert report.macro_f1_ci.point == pytest.approx(report.macro_f1, abs=1e-12)
    assert "95% CI" in report.to_markdown()
