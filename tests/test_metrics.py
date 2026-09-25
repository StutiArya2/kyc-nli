"""Edge cases for the evaluation harness.

Every number in every table in this project comes out of `evaluate`. A metric
that is subtly wrong in an edge case does not announce itself -- it produces a
plausible float that goes straight into a report. These tests therefore check
the degenerate inputs (a class absent from the gold, a class never predicted, a
singleton contrast group, an empty split) against results computed by hand.
"""

from __future__ import annotations

import pytest

from kyc_nli.evaluation.metrics import (
    evaluate,
    review_load_at_error,
    risk_coverage,
    selective_curve,
)
from kyc_nli.schema import (
    Field,
    Hypothesis,
    Instance,
    Label,
    Prediction,
    Provenance,
    Script,
)


def mk(
    idx: int,
    gold: Label,
    *,
    language: str = "en",
    phenomenon: str = "p",
    group: str | None = None,
) -> Instance:
    return Instance(
        id=f"i-{idx}",
        language=language,
        premise=[],
        hypothesis=Hypothesis(
            field=Field.SURNAME, value="X", script=Script.LATIN, language=language, text="t"
        ),
        label=gold,
        contrast_group_id=group,
        phenomenon=phenomenon,
        provenance=Provenance(generator="test"),
    )


def pred(idx: int, label: Label, confidence: float = 1.0) -> Prediction:
    return Prediction(instance_id=f"i-{idx}", label=label, confidence=confidence)


E, C, N = Label.ENTAILMENT, Label.CONTRADICTION, Label.NEUTRAL


# --------------------------------------------------------------------------
# Refusing to score nonsense
# --------------------------------------------------------------------------


def test_evaluating_an_empty_split_raises_rather_than_returning_zero() -> None:
    """An empty test split is a splitting bug. Returning 0.0 macro-F1 would look
    like a catastrophically bad system and send the reader hunting the model."""
    with pytest.raises(ValueError, match="empty"):
        evaluate("s", [], [])


def test_a_missing_prediction_is_named_rather_than_silently_dropped() -> None:
    """Scoring 999 of 1000 instances and reporting it as 1000 is the quietest
    possible way to inflate a result."""
    instances = [mk(0, E), mk(1, C)]
    with pytest.raises(ValueError, match="no prediction"):
        evaluate("s", instances, [pred(0, E)])


def test_extra_predictions_do_not_change_any_denominator() -> None:
    """Callers score a subset while holding the full prediction list. Every rate
    must be over the instances evaluated, review load included."""
    instances = [mk(0, E), mk(1, N)]
    extra = [pred(0, E), pred(1, N), pred(2, N), pred(3, N)]
    report = evaluate("s", instances, extra)
    assert report.n_instances == 2
    assert report.review_load == 0.5  # not 0.75


# --------------------------------------------------------------------------
# Classes that are absent or never predicted
# --------------------------------------------------------------------------


def test_a_class_absent_from_the_gold_scores_zero_not_nan() -> None:
    """Macro-F1 averages over all three labels always, so a split that happens to
    contain no NEUTRAL still divides by three. A NaN here would propagate into
    every aggregate silently."""
    instances = [mk(0, E), mk(1, C)]
    report = evaluate("s", instances, [pred(0, E), pred(1, C)])
    assert report.per_class_f1["neutral"] == 0.0
    assert report.macro_f1 == pytest.approx(2 / 3)


def test_a_perfect_system_on_all_three_classes_scores_one() -> None:
    instances = [mk(0, E), mk(1, C), mk(2, N)]
    report = evaluate("s", instances, [pred(0, E), pred(1, C), pred(2, N)])
    assert report.macro_f1 == pytest.approx(1.0)


def test_a_system_that_always_says_neutral_has_full_review_load() -> None:
    """The degenerate safe system. It never rejects a genuine holder and it
    automates nothing -- both of which must show up in the numbers."""
    instances = [mk(0, E), mk(1, C), mk(2, N)]
    report = evaluate("s", instances, [pred(i, N) for i in range(3)])
    assert report.review_load == 1.0
    assert report.false_mismatch_rate == 0.0
    assert report.over_abstention_rate == 1.0
    assert report.overconfident_rate == 0.0


# --------------------------------------------------------------------------
# Deployment rates, each computed by hand
# --------------------------------------------------------------------------


def test_false_mismatch_counts_only_entailment_called_contradiction() -> None:
    """A genuine holder rejected. Calling them NEUTRAL is a review, not a
    rejection, and must not be counted here."""
    instances = [mk(0, E), mk(1, E), mk(2, E), mk(3, E)]
    preds = [pred(0, C), pred(1, N), pred(2, E), pred(3, E)]
    report = evaluate("s", instances, preds)
    assert report.false_mismatch_rate == 0.25
    assert report.over_abstention_rate == 0.25


def test_the_rates_are_zero_when_their_denominator_class_is_absent() -> None:
    """No NEUTRAL gold means no opportunity to be overconfident on NEUTRAL. Zero
    is the honest reading; a crash or a NaN is not."""
    instances = [mk(0, E), mk(1, E)]
    report = evaluate("s", instances, [pred(0, E), pred(1, E)])
    assert report.overconfident_rate == 0.0

    instances = [mk(0, N), mk(1, N)]
    report = evaluate("s", instances, [pred(0, N), pred(1, N)])
    assert report.over_abstention_rate == 0.0
    assert report.false_mismatch_rate == 0.0


# --------------------------------------------------------------------------
# Contrast-group consistency
# --------------------------------------------------------------------------


def test_a_group_scores_only_when_every_member_is_correct() -> None:
    """This is the whole point of the metric: 3 of 4 right is 0, not 0.75."""
    instances = [mk(i, E, group="g") for i in range(4)]
    preds = [pred(0, E), pred(1, E), pred(2, E), pred(3, C)]
    assert evaluate("s", instances, preds).contrast_consistency == 0.0


def test_instances_with_no_group_are_excluded_from_the_denominator() -> None:
    """Counting ungrouped instances as trivially-consistent groups would let a
    dataset dilute the metric towards 1.0 just by adding singletons."""
    instances = [mk(0, E, group="g"), mk(1, C, group="g"), mk(2, E, group=None)]
    report = evaluate("s", instances, [pred(0, E), pred(1, C), pred(2, C)])
    assert report.n_contrast_groups == 1
    assert report.contrast_consistency == 1.0


def test_consistency_is_zero_when_there_are_no_groups_at_all() -> None:
    report = evaluate("s", [mk(0, E)], [pred(0, E)])
    assert report.n_contrast_groups == 0
    assert report.contrast_consistency == 0.0


# --------------------------------------------------------------------------
# Breakdowns
# --------------------------------------------------------------------------


def test_a_language_present_only_once_still_gets_its_own_row() -> None:
    """Urdu is the smallest and weakest slice; dropping thin slices would delete
    exactly the evidence the cross-script claim is tested on."""
    instances = [mk(0, E, language="en"), mk(1, C, language="ur")]
    report = evaluate("s", instances, [pred(0, E), pred(1, E)])
    assert set(report.per_language_macro_f1) == {"en", "ur"}
    assert report.per_language_macro_f1["ur"] == 0.0


def test_per_phenomenon_accuracy_is_plain_accuracy_within_the_slice() -> None:
    instances = [mk(0, E, phenomenon="a"), mk(1, C, phenomenon="a"), mk(2, N, phenomenon="b")]
    report = evaluate("s", instances, [pred(0, E), pred(1, E), pred(2, N)])
    assert report.per_phenomenon_accuracy == {"a": 0.5, "b": 1.0}


def test_the_markdown_report_renders_without_a_confidence_interval() -> None:
    """bootstrap=0 is the fast path used in tests and in the demo; it must not
    produce a report that crashes on formatting a None."""
    text = evaluate("s", [mk(0, E)], [pred(0, E)]).to_markdown()
    assert "macro-F1" in text and "95% CI" not in text


# --------------------------------------------------------------------------
# risk_coverage
# --------------------------------------------------------------------------


def test_risk_coverage_over_no_instances_raises_instead_of_dividing_by_zero() -> None:
    with pytest.raises(ValueError):
        risk_coverage([], [])


def test_risk_coverage_reaches_full_coverage_at_the_overall_error_rate() -> None:
    """The last point must reconcile with plain accuracy, or the curve is
    measuring something other than the system being reported."""
    instances = [mk(i, E) for i in range(4)]
    preds = [pred(0, E, 0.9), pred(1, E, 0.8), pred(2, C, 0.2), pred(3, C, 0.1)]
    curve = risk_coverage(instances, preds, steps=4)
    assert curve[-1] == (1.0, 0.5)


def test_risk_coverage_is_flat_when_every_confidence_is_identical() -> None:
    """The exact-match baseline reports 1.0 for everything. A flat line is the
    correct and informative answer: its confidence carries no signal."""
    instances = [mk(i, E) for i in range(4)]
    preds = [pred(0, E), pred(1, E), pred(2, C), pred(3, C)]
    assert {risk for _, risk in risk_coverage(instances, preds, steps=4)} == {0.5}


def test_risk_coverage_falls_when_confidence_ranks_correctness() -> None:
    instances = [mk(i, E) for i in range(4)]
    preds = [pred(0, E, 0.9), pred(1, E, 0.8), pred(2, C, 0.2), pred(3, C, 0.1)]
    curve = risk_coverage(instances, preds, steps=4)
    assert curve[0][1] == 0.0  # the most confident case is right
    assert curve[0][1] < curve[-1][1]


# --------------------------------------------------------------------------
# selective_curve: the deployment view
# --------------------------------------------------------------------------


def test_an_abstention_is_review_never_error_and_never_coverage() -> None:
    """The difference between this curve and risk-coverage. A structural NEUTRAL
    is the system working as designed, and charging it as an error would make
    the safest possible system look like the worst one."""
    instances = [mk(0, E), mk(1, E)]
    preds = [pred(0, N, 0.4), pred(1, E, 0.9)]
    point = selective_curve(instances, preds, steps=10)[0]
    assert point.threshold == 0.0
    assert point.review_load == 0.5
    assert point.coverage == 0.5
    assert point.error_on_auto == 0.0


def test_the_first_point_reproduces_the_review_load_evaluate_reports() -> None:
    """Two code paths, one number. If they disagree, one of them is wrong and
    the reader has no way to tell which."""
    instances = [mk(0, E), mk(1, C), mk(2, N), mk(3, E)]
    preds = [pred(0, E, 0.9), pred(1, N, 0.5), pred(2, N, 0.6), pred(3, C, 0.7)]
    report = evaluate("s", instances, preds)
    assert selective_curve(instances, preds)[0].review_load == report.review_load


def test_raising_the_bar_never_lowers_the_review_load() -> None:
    """Monotonicity. A non-monotone curve means the threshold is being applied
    inconsistently, which is easy to do and impossible to see in a plot."""
    instances = [mk(i, E if i % 2 else C) for i in range(20)]
    preds = [pred(i, E, i / 20) for i in range(20)]
    loads = [p.review_load for p in selective_curve(instances, preds, steps=20)]
    assert loads == sorted(loads)


def test_at_a_threshold_above_every_confidence_nothing_is_automated() -> None:
    instances = [mk(0, E), mk(1, C)]
    preds = [pred(0, E, 0.5), pred(1, C, 0.5)]
    last = selective_curve(instances, preds, steps=10)[-1]
    assert last.threshold == 1.0
    assert last.coverage == 0.0 and last.review_load == 1.0
    assert last.error_on_auto == 0.0  # no decisions, so no errors -- not NaN


# --------------------------------------------------------------------------
# review_load_at_error
# --------------------------------------------------------------------------


def test_the_cheapest_point_within_budget_is_the_one_returned() -> None:
    """Two thresholds may both meet the budget; the useful one is whichever
    automates more."""
    instances = [mk(i, E) for i in range(10)]
    preds = [pred(i, E if i < 9 else C, (i + 1) / 10) for i in range(10)]
    point = review_load_at_error(instances, preds, max_error=0.2)
    assert point is not None
    assert point.error_on_auto <= 0.2
    assert point.review_load <= 0.2


def test_an_unreachable_error_budget_returns_none_rather_than_a_fake_point() -> None:
    """Saying 'review everything' would imply the budget is satisfiable at 100%
    review, but a system that automates nothing has not met a 0% error target --
    it has declined to answer."""
    instances = [mk(i, E) for i in range(4)]
    preds = [pred(i, C, 0.9) for i in range(4)]  # always wrong, always confident
    assert review_load_at_error(instances, preds, max_error=0.0) is None


def test_a_budget_outside_zero_to_one_is_rejected() -> None:
    instances, preds = [mk(0, E)], [pred(0, E)]
    with pytest.raises(ValueError):
        review_load_at_error(instances, preds, max_error=1.5)
    with pytest.raises(ValueError):
        review_load_at_error(instances, preds, max_error=-0.1)


def test_a_perfect_system_needs_no_review_at_any_budget() -> None:
    instances = [mk(i, E) for i in range(5)]
    preds = [pred(i, E, 0.99) for i in range(5)]
    point = review_load_at_error(instances, preds, max_error=0.0)
    assert point is not None and point.review_load == 0.0
