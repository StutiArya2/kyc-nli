"""Human consensus and missing decisions must not silently become generator gold."""

from __future__ import annotations

import pytest

from kyc_nli.pilot_report import agreement, checked_rows, reconcile


def test_uncertainty_is_excluded_from_conditional_agreement():
    result = agreement(["entailment", "neutral", "uncertain"],
                       ["entailment", "neutral", "uncertain"])
    assert result["same_response_n"] == 3
    assert result["both_definite_n"] == 2
    assert result["conditional_kappa"] == 1
    assert result["per_class_on_definite_subset"]["contradiction"]["binary_kappa"] is None
    assert agreement([""], [""])["conditional_kappa"] is None


@pytest.mark.parametrize("problem", ["evidence", "duplicate", "label", "blank_without_reason"])
def test_review_integrity_guards(problem):
    reference = {"case_id": "case", "language": "configured_language",
                 "document_evidence": "?", "claim": "?"}
    row = dict(reference, reviewer_label="", reviewer_rationale="Insufficient evidence")
    rows = [row]
    if problem == "evidence":
        row["document_evidence"] = "changed"
    elif problem == "duplicate":
        rows.append(dict(row))
    elif problem == "label":
        row["reviewer_label"] = "fourth_gold_label"
    else:
        row["reviewer_rationale"] = ""
    with pytest.raises(ValueError):
        checked_rows(rows, {"case": reference}, "reviewer_label")


def test_reconciliation_retains_unresolved_and_generator_disagreement():
    expected = {str(i): {"language": "configured_language"} for i in range(4)}
    a = {str(i): {"human_label": label} for i, label in enumerate(
        ["entailment", "uncertain", "entailment", "uncertain"])}
    b = {i: dict(row) for i, row in a.items()}
    key = {str(i): {"generator_label": label} for i, label in enumerate(
        ["entailment", "entailment", "contradiction", "entailment"])}
    initial = {"1": {"adjudicated_label": ""}, "2": {"adjudicated_label": "contradiction"},
               "3": {"adjudicated_label": "contradiction"}}
    reviews = [{"1": {"reviewer_label": ""}, "3": {"reviewer_label": "contradiction"}}
               for _ in range(2)]
    rows = reconcile(expected, a, b, initial, reviews, key)
    assert rows[1]["candidate_human_label"] == ""
    assert rows[1]["status"] == "unresolved"
    assert rows[2]["decision_source"] == "initial_adjudication"
    assert rows[3]["status"] == "human_generator_disagreement"
    assert key["3"]["generator_label"] == "entailment"
    reviews[1]["1"]["reviewer_label"] = "neutral"
    assert reconcile(expected, a, b, initial, reviews, key)[1]["status"] == "unresolved"
    reviews[1].pop("3")
    with pytest.raises(ValueError, match="Follow-up"):
        reconcile(expected, a, b, initial, reviews, key)
