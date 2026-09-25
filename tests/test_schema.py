"""Edge cases for the core data model.

The schema is the contract every other module relies on, and two of its
guarantees are load-bearing for the *validity* of the results rather than for
correctness of the code: that a confidence is a probability, and that
``clean_value`` is distinguishable from ``value``. Both are asserted here so
that a change which quietly relaxes them fails the build.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kyc_nli.schema import (
    DATE_FIELDS,
    MRZ_FIELDS,
    Field,
    FieldObservation,
    Hypothesis,
    Instance,
    Label,
    Prediction,
    Provenance,
    Script,
    Zone,
)


def _obs(**kw) -> FieldObservation:
    base = dict(
        field=Field.SURNAME,
        zone=Zone.VIZ,
        value="CHATTERJEE",
        script=Script.LATIN,
        language="en",
    )
    base.update(kw)
    return FieldObservation(**base)


def _instance(premise: list[FieldObservation]) -> Instance:
    return Instance(
        id="t-0",
        language="en",
        premise=premise,
        hypothesis=Hypothesis(
            field=Field.SURNAME,
            value="CHATTERJEE",
            script=Script.LATIN,
            language="en",
            text="The holder's surname is CHATTERJEE.",
        ),
        label=Label.ENTAILMENT,
        provenance=Provenance(generator="test"),
    )


# --------------------------------------------------------------------------
# Confidence is a probability
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-0.001, 1.001, 2.0, -1.0])
def test_a_confidence_outside_zero_to_one_is_rejected(bad: float) -> None:
    """The rule baseline thresholds on this and the risk-coverage curve ranks by
    it. A value of 1.4 would silently sort above every genuine certainty."""
    with pytest.raises(ValidationError):
        _obs(confidence=bad)
    with pytest.raises(ValidationError):
        Prediction(instance_id="t-0", label=Label.ENTAILMENT, confidence=bad)


@pytest.mark.parametrize("ok", [0.0, 1.0, 0.5])
def test_the_endpoints_of_the_probability_range_are_allowed(ok: float) -> None:
    """0.0 is the legitimate reading of a field that was not recovered at all."""
    assert _obs(confidence=ok).confidence == ok


# --------------------------------------------------------------------------
# clean_value: analysis only, never an input
# --------------------------------------------------------------------------


def test_was_corrupted_is_false_when_there_is_no_ground_truth_to_compare() -> None:
    """An observation with no clean_value is not 'clean'; it is unknown. Reading
    it as clean would understate the corruption rate in every ablation."""
    assert _obs(clean_value=None).was_corrupted is False


def test_was_corrupted_is_false_when_ocr_happened_to_be_perfect() -> None:
    assert _obs(value="CHATTERJEE", clean_value="CHATTERJEE").was_corrupted is False


def test_was_corrupted_detects_a_pure_deletion() -> None:
    """The dominant Urdu failure mode is the whole word vanishing."""
    assert _obs(value="", clean_value="CHATTERJEE").was_corrupted is True


def test_was_corrupted_detects_a_single_character_substitution() -> None:
    assert _obs(value="CHATTERJBE", clean_value="CHATTERJEE").was_corrupted is True


# --------------------------------------------------------------------------
# Immutability
# --------------------------------------------------------------------------


def test_an_observation_cannot_be_mutated_after_construction() -> None:
    """Premises are shared across the contrast group members built from them.
    A mutable observation would let one member's corruption leak into another's
    and destroy the minimal-pair property the contrast metric depends on."""
    obs = _obs()
    with pytest.raises(ValidationError):
        obs.value = "TAMPERED"


def test_a_hypothesis_cannot_be_mutated_after_construction() -> None:
    h = _instance([]).hypothesis
    with pytest.raises(ValidationError):
        h.value = "TAMPERED"


# --------------------------------------------------------------------------
# Lookups on a premise
# --------------------------------------------------------------------------


def test_observations_returns_every_zone_that_carries_the_field() -> None:
    """Cross-zone comparison is the whole task; returning only the first would
    reduce it to reading the VIZ."""
    inst = _instance([_obs(zone=Zone.VIZ), _obs(zone=Zone.MRZ), _obs(zone=Zone.CHIP)])
    assert len(inst.observations(Field.SURNAME)) == 3


def test_observations_of_an_absent_field_is_empty_not_an_error() -> None:
    """NEUTRAL instances are built by removing a field, so absence is normal."""
    assert _instance([_obs()]).observations(Field.PLACE_OF_BIRTH) == []


def test_observation_returns_none_for_a_zone_that_was_not_read() -> None:
    """Not every document has a chip, and not every chip read succeeds."""
    inst = _instance([_obs(zone=Zone.VIZ)])
    assert inst.observation(Field.SURNAME, Zone.CHIP) is None
    assert inst.observation(Field.SURNAME, Zone.VIZ) is not None


def test_premise_fields_of_an_empty_premise_is_an_empty_set() -> None:
    """The degenerate NEUTRAL case -- a document from which nothing was read --
    must be representable, not a construction error."""
    inst = _instance([])
    assert inst.premise_fields == set()
    assert inst.observations(Field.SURNAME) == []


def test_premise_fields_deduplicates_across_zones() -> None:
    inst = _instance([_obs(zone=Zone.VIZ), _obs(zone=Zone.MRZ)])
    assert inst.premise_fields == {Field.SURNAME}


# --------------------------------------------------------------------------
# Field sets
# --------------------------------------------------------------------------


def test_the_mrz_field_set_excludes_what_a_td3_cannot_carry() -> None:
    """Asking the MRZ for a place of birth is a category error, and a rule that
    did so would abstain forever on a field that is simply not there."""
    assert Field.PLACE_OF_BIRTH not in MRZ_FIELDS
    assert Field.DATE_OF_ISSUE not in MRZ_FIELDS  # TD3 line 2 has no issue date
    assert Field.DATE_OF_EXPIRY in MRZ_FIELDS


def test_every_date_field_is_actually_a_date_field() -> None:
    assert {Field.DATE_OF_BIRTH, Field.DATE_OF_ISSUE, Field.DATE_OF_EXPIRY} == DATE_FIELDS
    assert all(f.value.startswith("date_") for f in DATE_FIELDS)


# --------------------------------------------------------------------------
# Serialisation round-trip
# --------------------------------------------------------------------------


def test_an_instance_survives_a_json_round_trip_with_non_latin_text() -> None:
    """Every instance goes to disk as JSONL and comes back. A model that lost
    Devanagari on the way through would fail in a way that looks like an OCR
    result rather than an I/O bug."""
    inst = _instance([_obs(value="চট্টোপাধ্যায়", script=Script.BENGALI, language="bn")])
    again = Instance.model_validate_json(inst.model_dump_json())
    assert again.premise[0].value == "চট্টোপাধ্যায়"
    assert again.label is Label.ENTAILMENT
    assert again.premise[0].script is Script.BENGALI


def test_enums_serialise_as_their_string_values_not_their_names() -> None:
    """The JSONL is read by the notebook and by human reviewers; 'Deva' is the
    ISO 15924 code, 'DEVANAGARI' is a Python identifier."""
    payload = _obs(script=Script.DEVANAGARI).model_dump_json()
    assert '"Deva"' in payload
    assert "DEVANAGARI" not in payload


def test_an_unknown_label_is_rejected_rather_than_coerced() -> None:
    """A fourth label arriving from a hand-edited file must not become data."""
    inst = _instance([])
    payload = inst.model_dump_json().replace('"entailment"', '"probably"')
    with pytest.raises(ValidationError):
        Instance.model_validate_json(payload)


def test_defaults_keep_an_instance_constructible_from_the_minimum() -> None:
    """identity_id and contrast_group_id are optional so that a one-off probe
    instance can be built by hand; the splitter has a documented fallback."""
    inst = _instance([])
    assert inst.identity_id is None
    assert inst.contrast_group_id is None
    assert inst.phenomenon == "unspecified"
    assert inst.provenance.contains_real_pii is False
