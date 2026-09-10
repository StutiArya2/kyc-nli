"""Serialisation tests.

These need no torch: they guard what the model is allowed to see, which is a
property of the text, not of the network. The training and inference paths are
exercised in the Colab notebook and by a smoke test that skips without torch.
"""

from __future__ import annotations

import pytest

from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.nli.dataset import (
    LABEL_TO_ID,
    LABELS,
    leaks_ground_truth,
    serialise_hypothesis,
    serialise_observation,
    serialise_premise,
    to_pairs,
)
from kyc_nli.schema import Field, FieldObservation, Label, Script, Zone


@pytest.fixture(scope="module")
def instances():
    return InstanceGenerator(GeneratorConfig(identities_per_language=10, seed=13)).generate()


def _obs(value: str, clean: str | None = None, conf: float = 1.0) -> FieldObservation:
    return FieldObservation(
        field=Field.SURNAME,
        zone=Zone.VIZ,
        value=value,
        script=Script.LATIN,
        language="en",
        confidence=conf,
        clean_value=clean,
    )


# --------------------------------------------------------------------------
# What the model must never see.
# --------------------------------------------------------------------------


def test_clean_value_is_never_serialised() -> None:
    """The pre-corruption value is for error analysis, not for the model."""
    text = serialise_observation(_obs("SHXRMA", clean="SHARMA"))
    assert "SHXRMA" in text
    assert "SHARMA" not in text


def test_no_instance_leaks_ground_truth(instances) -> None:
    assert [i.id for i in instances if leaks_ground_truth(i)] == []


def test_unreadable_fields_emit_a_marker_not_the_garbage(instances) -> None:
    """A field OCR could not read should say so, not pass noise through.

    M1 measured that unreadable fields are the dominant failure and NEUTRAL is
    defined by evidence absence, so this marker carries most of the signal for
    the hardest class. Passing the corrupted characters instead would invite the
    model to pattern-match on noise.
    """
    text = serialise_observation(_obs("???????", clean="SHARMA", conf=0.05))
    assert text.endswith("=?")
    assert "?" * 7 not in text
    assert "SHARMA" not in text


def test_transliteration_variants_are_not_in_the_premise(instances) -> None:
    """The rule baseline's ICAO tables must not reach the model.

    Handing the model the baseline's central advantage would make any win over
    that baseline uninterpretable.
    """
    for inst in instances[:100]:
        text = serialise_premise(inst)
        assert "variant" not in text.lower()
        assert "icao" not in text.lower()


# --------------------------------------------------------------------------
# Shape and content.
# --------------------------------------------------------------------------


def test_premise_is_stable_across_calls(instances) -> None:
    """Same instance, same string: the order must not depend on dict iteration."""
    for inst in instances[:50]:
        assert serialise_premise(inst) == serialise_premise(inst)


def test_premise_mentions_every_non_excluded_field(instances) -> None:
    inst = instances[0]
    text = serialise_premise(inst)
    for obs in inst.premise:
        if obs.field is Field.DOCUMENT_TYPE:
            continue
        assert obs.zone.value in text


def test_raw_mrz_block_is_excluded(instances) -> None:
    """It is ~90 characters of filler duplicating the parsed MRZ fields."""
    for inst in instances[:50]:
        assert "<<<<" not in serialise_premise(inst)


def test_label_ids_are_stable_and_complete() -> None:
    assert set(LABELS) == set(Label)
    assert sorted(LABEL_TO_ID.values()) == [0, 1, 2]


def test_to_pairs_is_aligned(instances) -> None:
    premises, hypotheses, labels = to_pairs(instances)
    assert len(premises) == len(hypotheses) == len(labels) == len(instances)
    for i, inst in enumerate(instances):
        assert hypotheses[i] == serialise_hypothesis(inst)
        assert labels[i] == LABEL_TO_ID[inst.label]


def test_serialisation_stays_within_a_workable_token_budget(instances) -> None:
    """A verbose premise is a slow epoch.

    The first serialisation ran to a median of 347 subword tokens, which on CPU
    is a three-hour epoch. Characters are a proxy, but a regression here means
    the training cost has silently doubled.
    """
    lengths = [len(serialise_premise(i)) for i in instances]
    median = sorted(lengths)[len(lengths) // 2]
    assert median < 400, f"median premise is {median} characters; it was ~250"
