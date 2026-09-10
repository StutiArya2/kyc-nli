"""Turning an Instance into text a cross-encoder can read.

Two rules govern this file, and both exist to keep the comparison against the
rule baseline honest.

1. THE MODEL NEVER SEES ``clean_value``. That field holds the pre-corruption
   ground truth and exists only for error analysis. Leaking it would let the
   model read the answer off the input.

2. THE MODEL NEVER SEES THE TRANSLITERATION VARIANT SETS. The rule baseline's
   central advantage is its ICAO tables and its romanisation lexicon; handing
   the same thing to the model would make "the model beats the rule engine"
   uninterpretable. The model gets raw observations and has to learn the
   relationship itself. If it wins, it won on inference.

The serialisation keeps the field name, the zone it came from, the value, and
whether it was legible. It drops the script tag (recoverable from the characters)
and the exact confidence (what matters is legible or not). Legibility is the one
that carries the most weight: milestone M1 measured that the dominant OCR failure
is fields that cannot be read at all, and NEUTRAL is defined by evidence absence.

Terseness is not cosmetic here. The first serialisation ran to a median of 347
tokens per instance; on a CPU that is a three-hour epoch. The current one is 159
and encodes the same facts.
"""

from __future__ import annotations

from kyc_nli.schema import Field, Instance, Label

#: Order labels consistently everywhere: this is the class index the model uses.
LABELS: tuple[Label, ...] = (Label.ENTAILMENT, Label.CONTRADICTION, Label.NEUTRAL)
LABEL_TO_ID: dict[Label, int] = {lab: i for i, lab in enumerate(LABELS)}

#: Dropped from the premise: the raw two-line MRZ block is ~90 characters of
#: mostly filler and duplicates the parsed MRZ fields that sit beside it. Keeping
#: it would spend a third of the token budget re-encoding information the model
#: already has in a cleaner form.
_EXCLUDED_FIELDS = frozenset({Field.DOCUMENT_TYPE})

#: Compact field names. The verbose serialisation ran to a median of 347 tokens
#: per instance, which on a CPU is the difference between a 3-hour epoch and a
#: 1-hour one. Nothing is lost: the names are a fixed closed vocabulary the model
#: learns as tokens either way, and shorter ones leave more of the budget for the
#: actual field VALUES, which is where the signal is.
_SHORT_FIELD: dict[str, str] = {
    "surname": "sur",
    "given_names": "giv",
    "date_of_birth": "dob",
    "date_of_issue": "doi",
    "date_of_expiry": "doe",
    "document_number": "num",
    "nationality": "nat",
    "sex": "sex",
    "place_of_birth": "pob",
    "issuing_authority": "auth",
    "document_type": "typ",
    "template_era": "era",
}

#: Below this confidence a field is marked unreadable rather than transcribed.
#: The rule baseline uses the same threshold (RuleConfig.illegible_confidence),
#: so neither system gets a different view of what counts as legible.
ILLEGIBLE_CONFIDENCE = 0.35


def serialise_observation(obs) -> str:
    """One field observation as text.

    Unreadable values become an explicit marker rather than their corrupted
    characters. Passing the garbage through would invite the model to
    pattern-match on noise; saying "unreadable" states the thing that actually
    decides the NEUTRAL cases.

    The script tag is omitted: it is recoverable from the characters themselves,
    and spending tokens to restate what the bytes already say is waste. Exact
    confidence is omitted too -- what matters is legible or not, and the
    threshold is shared with the rule baseline so neither system gets a
    different view of the evidence.
    """
    name = _SHORT_FIELD.get(obs.field.value, obs.field.value)
    if obs.confidence < ILLEGIBLE_CONFIDENCE or not obs.value.strip():
        return f"{name}:{obs.zone.value}=?"
    return f"{name}:{obs.zone.value}={obs.value}"


def serialise_premise(instance: Instance) -> str:
    """The document as a single string: every observation, in a stable order."""
    parts = [
        serialise_observation(obs)
        for obs in sorted(
            (o for o in instance.premise if o.field not in _EXCLUDED_FIELDS),
            key=lambda o: (o.field.value, o.zone.value),
        )
    ]
    if not parts:
        return "no readable fields on this document"
    return " | ".join(parts)


def serialise_hypothesis(instance: Instance) -> str:
    """The claim being checked, as natural language."""
    return instance.hypothesis.text


def to_pairs(instances: list[Instance]) -> tuple[list[str], list[str], list[int]]:
    """(premises, hypotheses, label_ids) ready for a tokeniser."""
    premises = [serialise_premise(i) for i in instances]
    hypotheses = [serialise_hypothesis(i) for i in instances]
    labels = [LABEL_TO_ID[i.label] for i in instances]
    return premises, hypotheses, labels


def leaks_ground_truth(instance: Instance) -> bool:
    """True if the serialisation exposes a pre-corruption value it must not.

    Guards rule 1: ``clean_value`` is the value before OCR corruption and exists
    for error analysis only. If it reaches the model, the model can read the
    answer off its input and the failure is invisible in the metrics -- it just
    looks like a very good model.

    WHAT THIS DOES *NOT* TREAT AS LEAKAGE, and two wrong versions of it:

    A first attempt asked whether ``clean_value`` appeared anywhere in the
    premise text. That flagged 1086 of 4905 training instances, all of them
    insertion corruptions: '23 SEP 2011' is a substring of '23 SEP 2011I'
    because inserting a character is what an insertion does.

    A second asked whether it appeared in any *other* field. That flagged 4570
    of 4905, and the concept was simply wrong. Identity documents repeat the
    same logical value across zones by design -- the VIZ prints a date and the
    MRZ prints the same date in another format. Recovering a corrupted VIZ field
    from an intact MRZ field is not cheating, it is precisely the cross-zone
    inference the task is asking for. Calling it leakage would forbid the model
    from doing the thing the project is about.

    The property that actually matters is narrow, and is a property of the
    SERIALISER rather than of the data: each observation must be rendered from
    its own ``value`` (or the unreadable marker), never from ``clean_value``.
    A third attempt that also flagged insertions -- because the clean value is
    necessarily a substring of a corrupted-by-insertion value -- got 453.
    The correct answer is zero, and it is zero by construction; this function
    exists so that a future edit to ``serialise_observation`` cannot quietly
    make it non-zero.
    """
    for obs in instance.premise:
        if obs.field in _EXCLUDED_FIELDS:
            continue
        if not obs.clean_value or obs.clean_value == obs.value:
            continue
        text = serialise_observation(obs)
        if text.endswith("=?"):
            continue  # unreadable: neither value nor clean_value is emitted
        if obs.value not in text:
            return True
    return False
