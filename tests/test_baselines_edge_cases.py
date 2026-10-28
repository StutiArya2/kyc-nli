"""Degenerate documents, put to both baselines.

`tests/test_baselines.py` measures how *well* the rule engine does on generated
data. This file asks what it does when handed a document the generator would
never produce: no observation of the claimed field, every zone unreadable, an
unparsable date, two zones that disagree with each other.

Those cases decide the false-mismatch rate, which is the metric the incumbent
system is actually judged on -- a genuine holder rejected because a character
was misread. The rule engine must reach NEUTRAL, not CONTRADICTION, whenever
the evidence is destroyed rather than contradictory. Getting that boundary
wrong makes the baseline unfairly easy to beat, which CLAUDE.md forbids as
loudly as it forbids weakening it any other way.
"""

from __future__ import annotations

import pytest

from kyc_nli.baselines import available_systems
from kyc_nli.baselines.exact import ExactMatchBaseline
from kyc_nli.baselines.rules import RuleBaseline
from kyc_nli.schema import (
    Field,
    FieldObservation,
    Hypothesis,
    Instance,
    Label,
    Provenance,
    Script,
    Zone,
)


def obs(field: Field, zone: Zone, value: str, confidence: float = 0.95, **kw):
    return FieldObservation(
        field=field, zone=zone, value=value, script=kw.pop("script", Script.LATIN),
        language=kw.pop("language", "en"), confidence=confidence, **kw
    )


def instance(
    premise: list[FieldObservation],
    *,
    field: Field = Field.SURNAME,
    claim: str = "CHATTERJEE",
    label: Label = Label.ENTAILMENT,
) -> Instance:
    return Instance(
        id="edge-0",
        language="en",
        premise=premise,
        hypothesis=Hypothesis(
            field=field, value=claim, script=Script.LATIN, language="en",
            text=f"The holder's {field.value} is {claim}.",
        ),
        label=label,
        provenance=Provenance(generator="test"),
    )


@pytest.fixture
def rules() -> RuleBaseline:
    return RuleBaseline()


# --------------------------------------------------------------------------
# Absent or destroyed evidence must be NEUTRAL, never CONTRADICTION
# --------------------------------------------------------------------------


def test_a_claim_about_a_field_the_document_does_not_carry_is_neutral(rules) -> None:
    """Not a mismatch. A passport has no place-of-issue field to disagree with."""
    prediction = rules.predict(
        instance([obs(Field.SURNAME, Zone.VIZ, "CHATTERJEE")], field=Field.PLACE_OF_BIRTH)
    )
    assert prediction.label is Label.NEUTRAL


def test_an_empty_premise_is_neutral_rather_than_a_crash(rules) -> None:
    """A document from which nothing was read at all -- a blank capture."""
    assert rules.predict(instance([])).label is Label.NEUTRAL


def test_a_field_read_at_zero_confidence_is_neutral(rules) -> None:
    """An OCR engine reporting no confidence has not produced evidence. Treating
    its output as a value and rejecting the holder on it is the failure mode the
    whole project exists to remove."""
    prediction = rules.predict(
        instance([obs(Field.SURNAME, Zone.VIZ, "CH4TT3RJ33", confidence=0.0)])
    )
    assert prediction.label is Label.NEUTRAL


def test_a_field_read_as_replacement_characters_is_neutral(rules) -> None:
    """High reported confidence, no recoverable content. Confidence alone is not
    a sufficient legibility test, which is why there is a second one."""
    prediction = rules.predict(
        instance([obs(Field.SURNAME, Zone.VIZ, "???????", confidence=0.99)])
    )
    assert prediction.label is Label.NEUTRAL


def test_an_empty_string_read_is_neutral_not_a_mismatch(rules) -> None:
    """M1 measured this as ~97% of all Urdu error: the word comes back blank.
    Calling that a contradiction would reject nearly every Urdu holder."""
    prediction = rules.predict(
        instance([obs(Field.SURNAME, Zone.VIZ, "", confidence=0.9)])
    )
    assert prediction.label is Label.NEUTRAL


def test_a_date_mangled_past_parsing_is_neutral(rules) -> None:
    """Without this the baseline calls every OCR-corrupted date a CONTRADICTION,
    which is both wrong and an unfairly easy target for the model to beat."""
    prediction = rules.predict(
        instance(
            [obs(Field.DATE_OF_BIRTH, Zone.VIZ, "1Z JUL 19B4")],
            field=Field.DATE_OF_BIRTH,
            claim="1984-07-12",
        )
    )
    assert prediction.label is Label.NEUTRAL


def test_an_unparsable_claim_is_neutral_not_a_mismatch(rules) -> None:
    """The hypothesis can be malformed too -- it comes from a form a human typed."""
    prediction = rules.predict(
        instance(
            [obs(Field.DATE_OF_BIRTH, Zone.VIZ, "1984-07-12")],
            field=Field.DATE_OF_BIRTH,
            claim="not a date",
        )
    )
    assert prediction.label is Label.NEUTRAL


# --------------------------------------------------------------------------
# Evidence that is present and does decide
# --------------------------------------------------------------------------


def test_one_legible_zone_is_enough_even_when_another_is_destroyed(rules) -> None:
    """The cross-zone recovery the project is about: an intact MRZ rescuing a
    VIZ that OCR ruined. If this abstained, there would be no project."""
    prediction = rules.predict(
        instance(
            [
                obs(Field.SURNAME, Zone.VIZ, "", confidence=0.1),
                obs(Field.SURNAME, Zone.MRZ, "CHATTERJEE"),
            ]
        )
    )
    assert prediction.label is Label.ENTAILMENT
    assert any("mrz" in s for s in prediction.supporting)


def test_a_date_matches_across_format_differences(rules) -> None:
    """The VIZ prints 12 JUL 1984 and the MRZ carries 840712. Same date."""
    prediction = rules.predict(
        instance(
            [obs(Field.DATE_OF_BIRTH, Zone.VIZ, "12 JUL 1984")],
            field=Field.DATE_OF_BIRTH,
            claim="1984-07-12",
        )
    )
    assert prediction.label is Label.ENTAILMENT


def test_a_genuinely_different_name_is_contradicted(rules) -> None:
    """The engine must still be able to say no; an engine that only ever
    abstains has a perfect false-mismatch rate and no value."""
    prediction = rules.predict(
        instance([obs(Field.SURNAME, Zone.VIZ, "ANNAMALAI")], claim="CHATTERJEE")
    )
    assert prediction.label is Label.CONTRADICTION
    assert prediction.conflicting


def test_two_similar_but_different_surnames_land_in_the_indeterminate_band(rules) -> None:
    """MUKHERJEE against CHATTERJEE scores ~63 on the similarity scale: too far
    apart to accept, too close to reject on a corrupted read. The engine abstains
    and buys the answer with human review -- which is the whole reason its review
    load is 63% and the reason there is headroom for a model to take some of it
    back. An edit that collapses this band into a decision would make the
    baseline look better on macro-F1 and worse on the metric that matters."""
    prediction = rules.predict(
        instance([obs(Field.SURNAME, Zone.VIZ, "MUKHERJEE")], claim="CHATTERJEE")
    )
    assert prediction.label is Label.NEUTRAL
    assert "indeterminate" in prediction.rationale


def test_a_cross_script_name_matches_through_its_transliteration(rules) -> None:
    """The central capability. The VIZ is Devanagari and the claim is Latin."""
    prediction = rules.predict(
        instance(
            [obs(Field.SURNAME, Zone.VIZ, "चटर्जी", script=Script.DEVANAGARI, language="hi")],
            claim="CHATTERJEE",
        )
    )
    assert prediction.label in (Label.ENTAILMENT, Label.CONTRADICTION)


# --------------------------------------------------------------------------
# Every prediction must be well formed
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "premise",
    [
        [],
        [obs(Field.SURNAME, Zone.VIZ, "")],
        [obs(Field.SURNAME, Zone.VIZ, "?", confidence=0.0)],
        [obs(Field.SURNAME, Zone.VIZ, "CHATTERJEE")],
        [obs(Field.SURNAME, Zone.MRZ, "CHATTERJEE"), obs(Field.SURNAME, Zone.VIZ, "MUKHERJEE")],
    ],
)
def test_every_prediction_carries_a_usable_rationale_and_confidence(premise) -> None:
    """The explainability claim is only measurable if every prediction is
    explained -- including the ones the engine found trivial."""
    for system in (RuleBaseline(), ExactMatchBaseline()):
        prediction = system.predict(instance(premise))
        assert prediction.instance_id == "edge-0"
        assert 0.0 <= prediction.confidence <= 1.0
        assert prediction.rationale.strip(), f"{system.name} explained nothing"


def test_the_two_zones_disagreeing_does_not_crash_either_system() -> None:
    """A real forgery signal, and the case where supporting and conflicting
    evidence both exist for the same claim."""
    premise = [
        obs(Field.SURNAME, Zone.MRZ, "CHATTERJEE"),
        obs(Field.SURNAME, Zone.VIZ, "MUKHERJEE"),
    ]
    for system in (RuleBaseline(), ExactMatchBaseline()):
        assert system.predict(instance(premise)).label in set(Label)


# --------------------------------------------------------------------------
# The incumbent
# --------------------------------------------------------------------------


def test_exact_match_never_abstains_even_with_no_evidence_at_all() -> None:
    """Its defining flaw, and the reason its false-mismatch rate is 89%. It has
    no way to say 'I cannot tell', so a blank read becomes a rejection."""
    prediction = ExactMatchBaseline().predict(instance([]))
    assert prediction.label is Label.CONTRADICTION


def test_exact_match_is_defeated_by_a_single_misread_character() -> None:
    prediction = ExactMatchBaseline().predict(
        instance([obs(Field.SURNAME, Zone.VIZ, "CHATTERJEF")], claim="CHATTERJEE")
    )
    assert prediction.label is Label.CONTRADICTION


def test_exact_match_still_tolerates_case_and_surrounding_whitespace() -> None:
    """It is a weak baseline, not a broken one. Beating a straw man proves
    nothing, so it gets the normalisation any real implementation would have."""
    prediction = ExactMatchBaseline().predict(
        instance([obs(Field.SURNAME, Zone.VIZ, "  chatterjee ")], claim="CHATTERJEE")
    )
    assert prediction.label is Label.ENTAILMENT


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


def test_both_baselines_are_registered_and_share_one_interface() -> None:
    """`kyc-nli compare` iterates this registry; anything not in it is never
    scored, and anything in it with a different interface breaks the run."""
    systems = available_systems()
    assert {"exact_match", "rule_engine"} <= set(systems)
    for name, cls in systems.items():
        model = cls()
        assert model.name == name
        assert callable(model.predict)
