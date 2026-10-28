"""Dev/test separation, indivisible confidence ties and empty-policy uncertainty."""

from __future__ import annotations

import numpy as np
import pytest

from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.languages import load_languages
from kyc_nli.schema import Label, Prediction
from kyc_nli.selective_v1 import (
    choose_on_dev,
    cluster_samples,
    policy_stats,
    prediction_index,
    uncertainty,
    wilson,
)


@pytest.fixture
def cases():
    language = next(iter(load_languages()))
    generated = InstanceGenerator(GeneratorConfig(
        languages=(language,), identities_per_language=3, seed=17,
    )).generate()
    labels = [Label.ENTAILMENT, Label.CONTRADICTION, Label.ENTAILMENT, Label.NEUTRAL]
    instances = [generated[i].model_copy(update={
        "id": f"case-{i}", "label": label, "contrast_group_id": f"group-{i // 2}",
    }) for i, label in enumerate(labels)]
    predictions = [Prediction(instance_id=instance.id, label=label, confidence=confidence)
                   for instance, label, confidence in zip(instances, [
                       Label.ENTAILMENT, Label.ENTAILMENT, Label.CONTRADICTION, Label.NEUTRAL,
                   ], [0.9, 0.8, 0.7, 0.99], strict=True)]
    return instances, predictions


def test_dev_threshold_is_fixed_when_test_errors_exceed_the_budget(cases):
    dev, predictions = cases
    selected = choose_on_dev(dev, predictions, [0.1])["0.1"]
    assert selected["threshold"] == 0.9
    test = [x.model_copy(update={"label": Label.CONTRADICTION}) for x in dev]
    measured = policy_stats(test, predictions, selected["threshold"])
    assert measured["automated_n"] == 1
    assert measured["automated_errors"] == 1
    assert measured["automated_error_rate"] == 1.0
    assert not measured["statistical_guarantee"]


def test_a_confidence_tie_cannot_be_split_to_meet_a_budget(cases):
    instances, predictions = cases
    tied = [p.model_copy(update={"confidence": 0.9}) for p in predictions[:2]]
    result = choose_on_dev(instances[:2], tied, [0.1])["0.1"]
    assert result["threshold"] is None
    assert result["status"] == "NO_NONEMPTY_DEV_OPERATING_POINT"


def test_neutral_remains_review_even_at_higher_confidence(cases):
    instances, predictions = cases
    result = policy_stats(instances, predictions, 0.0)
    assert result["automated_n"] == 3
    assert result["automated_errors"] == 2
    assert result["review_load"] == 0.25


def test_empty_automation_has_undefined_risk_not_zero_risk(cases):
    instances, predictions = cases
    result = policy_stats(instances, predictions, 1.0)
    assert result["automated_error_rate"] is None
    assert result["wilson_95_ci_iid_reference_only"] is None
    samples = cluster_samples(instances, 100, 13)
    interval, review = uncertainty(instances, predictions, 1.0, samples)
    assert interval["automated_error_95_ci"] is None
    assert interval["undefined_risk_resamples"] == 100
    assert np.all(review == 1.0)


def test_wilson_reference_does_not_claim_zero_upper_risk_for_zero_errors():
    low, high = wilson(0, 10)
    assert low == pytest.approx(0.0)
    assert high == pytest.approx(0.2775327998628892)


def test_bootstrap_keeps_members_of_each_contrast_group_together(cases):
    instances, _ = cases
    for index in cluster_samples(instances, 100, 9):
        assert np.count_nonzero(index == 0) == np.count_nonzero(index == 1)
        assert np.count_nonzero(index == 2) == np.count_nonzero(index == 3)


def test_predicted_rows_must_match_cases_exactly(cases):
    instances, predictions = cases
    with pytest.raises(ValueError, match="prediction/instance"):
        prediction_index(instances, predictions + [predictions[0]])
