"""Synthetic instance generator for the KYC-NLI benchmark.

Design commitments, each of which exists to answer a specific reviewer
objection:

1. CONTRAST GROUPS. Instances are emitted in minimal-pair triples that share a
   ``contrast_group_id`` and differ by one controlled edit. A model that has
   learned string similarity rather than inference will get one member of a
   group right and the others wrong, and the contrast-consistency metric will
   expose that. Emitting isolated examples would hide it.

2. NEUTRAL IS STRUCTURAL. Every NEUTRAL instance is neutral because the premise
   physically lacks the evidence, not because a score fell below a threshold.
   The generator constructs neutrality by removing a field from the document or
   by asserting a field the document type never carries.

3. PROVENANCE IS MANDATORY. Every instance records its generator, seed and
   whether any real PII is involved (always False here). The benchmark card is
   regenerated from these records rather than written by hand.

4. PHENOMENON LABELS. Every instance is tagged with the phenomenon it probes, so
   results are reported per-phenomenon. An aggregate number would let a win on
   the easy temporal cases hide a loss on cross-script matching.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from kyc_nli.data import mrz
from kyc_nli.data.name_pools import NamePool, pool_for
from kyc_nli.languages import load_languages
from kyc_nli.ocr.noise import NOISE_PRESETS, NoiseConfig, OCRNoiser
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
from kyc_nli.translit import get_transliterator

#: Issuing-state codes per language, ICAO 3-letter.
#:
#: All five active languages map to IND, and that is the point rather than an
#: oversight: these are five languages appearing on documents issued by ONE
#: state. An Indian passport prints the holder's name in English and the
#: regional script on the same physical document, so the cross-script
#: comparison is in-document rather than across two records from two countries.
NATIONALITY: dict[str, str] = {
    "en": "IND",
    "hi": "IND",
    "ta": "IND",
    "bn": "IND",
    "ur": "IND",
    # Retained, not in the active set (decision 0005).
    "ru": "RUS",
    "ar": "EGY",
    "zh": "CHN",
}

#: Document design generations, with the window in which each was issued.
#: A document whose issue date falls outside its template's window is
#: physically impossible regardless of whether each field is individually valid.
TEMPLATE_ERAS: tuple[tuple[str, int, int], ...] = (
    ("2006-series", 2006, 2010),
    ("2010-series", 2010, 2015),
    ("2015-hologram", 2015, 2020),
    ("2020-polycarbonate", 2020, 2026),
)

#: Fields that a passport carries in the VIZ but which are absent from the MRZ.
#: Asserting one of these against an MRZ-only premise is structurally NEUTRAL.
VIZ_ONLY_FIELDS: tuple[Field, ...] = (
    Field.PLACE_OF_BIRTH,
    Field.DATE_OF_ISSUE,
    Field.ISSUING_AUTHORITY,
)


@dataclass
class Identity:
    """A fabricated document holder plus the document issued to them."""

    language: str
    script: Script
    surname_native: str
    given_native: str
    surname_latin: str
    given_latin: str
    date_of_birth: date
    date_of_issue: date
    date_of_expiry: date
    document_number: str
    nationality: str
    sex: str
    place_of_birth: str
    issuing_authority: str
    template_era: str


@dataclass
class GeneratorConfig:
    """Everything needed to reproduce a dataset. Serialised into the manifest."""

    languages: tuple[str, ...] = ("en", "hi", "ta", "bn", "ur")
    identities_per_language: int = 200
    noise_preset: str = "moderate"
    seed: int = 20260906
    #: Fraction of ENTAILMENT pairs that use an alternative romanisation
    #: rather than the one printed on the document. Raising this makes the task
    #: harder for a lookup-table baseline and is the main difficulty knob.
    alt_romanisation_rate: float = 0.4


class InstanceGenerator:
    """Builds labelled NLI instances from fabricated identities."""

    def __init__(self, config: GeneratorConfig | None = None) -> None:
        self.config = config or GeneratorConfig()
        self.rng = random.Random(self.config.seed)
        noise_cfg: NoiseConfig = NOISE_PRESETS[self.config.noise_preset]
        self.noiser = OCRNoiser(noise_cfg, seed=self.config.seed)
        self.languages = load_languages()

    # -- identity construction ---------------------------------------------

    def make_identity(self, language: str) -> Identity:
        pool: NamePool = pool_for(language)
        spec = self.languages[language]

        # The pool supplies BOTH forms. The document's Latin zone prints the
        # attested romanisation the holder actually uses, not whatever a
        # rule-based romaniser emits -- deriving it from the transliterator
        # printed SARM for शर्मा and CHUBRAMANIYAN for சுப்ரமணியன். The
        # transliterator's job is to recognise variants at match time.
        surname_native, surname_latin = self.rng.choice(pool.surnames)
        given_native, given_latin = self.rng.choice(pool.given)
        place_native, _place_latin = self.rng.choice(pool.places)
        authority_native, _authority_latin = self.rng.choice(pool.authorities)

        era, era_start, era_end = self.rng.choice(TEMPLATE_ERAS)
        issue_year = self.rng.randint(era_start, era_end)
        date_of_issue = date(issue_year, self.rng.randint(1, 12), self.rng.randint(1, 28))
        date_of_expiry = _add_years(date_of_issue, 10)
        age_at_issue = self.rng.randint(18, 70)
        date_of_birth = _add_years(date_of_issue, -age_at_issue)

        return Identity(
            language=language,
            script=spec.script,
            surname_native=surname_native,
            given_native=given_native,
            surname_latin=surname_latin,
            given_latin=given_latin,
            date_of_birth=date_of_birth,
            date_of_issue=date_of_issue,
            date_of_expiry=date_of_expiry,
            document_number=self._document_number(),
            nationality=NATIONALITY[language],
            sex=self.rng.choice(("M", "F")),
            place_of_birth=place_native,
            issuing_authority=authority_native,
            template_era=era,
        )

    def _document_number(self) -> str:
        letters = "".join(self.rng.choice("ABCDEFGHIJKLMNPQRSTUVWXYZ") for _ in range(2))
        digits = "".join(self.rng.choice("0123456789") for _ in range(7))
        return letters + digits

    # -- premise construction ----------------------------------------------

    def build_premise(
        self,
        identity: Identity,
        *,
        apply_noise: bool = True,
        omit: frozenset[Field] = frozenset(),
    ) -> list[FieldObservation]:
        """The document as read: VIZ in the native script plus the Latin MRZ.

        ``omit`` removes fields from the document entirely, which is how
        structural NEUTRAL instances are constructed.
        """
        obs: list[FieldObservation] = []
        script = identity.script

        def add(field: Field, zone: Zone, value: str, script_: Script, noisy: bool) -> None:
            if field in omit:
                return
            if noisy and apply_noise:
                corrupted, edits = self.noiser.corrupt(value, script_)
                obs.append(
                    FieldObservation(
                        field=field,
                        zone=zone,
                        value=corrupted,
                        script=script_,
                        language=identity.language,
                        confidence=_confidence_from_edits(edits, value),
                        clean_value=value,
                    )
                )
            else:
                obs.append(
                    FieldObservation(
                        field=field,
                        zone=zone,
                        value=value,
                        script=script_,
                        language=identity.language,
                        confidence=1.0,
                        clean_value=value,
                    )
                )

        # Visual Inspection Zone, printed in the native script.
        add(Field.SURNAME, Zone.VIZ, identity.surname_native, script, True)
        add(Field.GIVEN_NAMES, Zone.VIZ, identity.given_native, script, True)
        add(Field.PLACE_OF_BIRTH, Zone.VIZ, identity.place_of_birth, script, True)
        add(Field.ISSUING_AUTHORITY, Zone.VIZ, identity.issuing_authority, script, True)
        add(
            Field.DATE_OF_BIRTH,
            Zone.VIZ,
            identity.date_of_birth.strftime("%d %b %Y").upper(),
            Script.LATIN,
            True,
        )
        add(
            Field.DATE_OF_ISSUE,
            Zone.VIZ,
            identity.date_of_issue.strftime("%d %b %Y").upper(),
            Script.LATIN,
            True,
        )
        add(
            Field.DATE_OF_EXPIRY,
            Zone.VIZ,
            identity.date_of_expiry.strftime("%d %b %Y").upper(),
            Script.LATIN,
            True,
        )
        add(Field.TEMPLATE_ERA, Zone.VIZ, identity.template_era, Script.LATIN, False)

        # Machine Readable Zone: Latin only, ICAO transliteration of the same name.
        line1, line2 = mrz.build_td3(
            surname_latin=identity.surname_latin,
            given_latin=identity.given_latin,
            document_number=identity.document_number,
            nationality=identity.nationality,
            date_of_birth=identity.date_of_birth,
            sex=identity.sex,
            date_of_expiry=identity.date_of_expiry,
        )
        add(Field.SURNAME, Zone.MRZ, identity.surname_latin, Script.LATIN, True)
        add(Field.GIVEN_NAMES, Zone.MRZ, identity.given_latin, Script.LATIN, True)
        add(Field.DATE_OF_BIRTH, Zone.MRZ, mrz.format_mrz_date(identity.date_of_birth),
            Script.LATIN, True)
        add(Field.DATE_OF_EXPIRY, Zone.MRZ, mrz.format_mrz_date(identity.date_of_expiry),
            Script.LATIN, True)
        add(Field.DOCUMENT_NUMBER, Zone.MRZ, identity.document_number, Script.LATIN, True)
        add(Field.NATIONALITY, Zone.MRZ, identity.nationality, Script.LATIN, False)
        add(Field.SEX, Zone.MRZ, identity.sex, Script.LATIN, False)
        # The raw MRZ lines are retained as a single observation so that a system
        # may recompute check digits.
        obs.append(
            FieldObservation(
                field=Field.DOCUMENT_TYPE,
                zone=Zone.MRZ,
                value=f"{line1}\n{line2}",
                script=Script.LATIN,
                language="und",
                confidence=1.0,
                clean_value=f"{line1}\n{line2}",
            )
        )
        return obs

    # -- instance construction ---------------------------------------------

    def generate(self) -> list[Instance]:
        """Full dataset for the configured languages."""
        instances: list[Instance] = []
        for language in self.config.languages:
            for i in range(self.config.identities_per_language):
                identity = self.make_identity(language)
                other = self.make_identity(language)
                stem = f"{language}-{i:05d}"
                instances += self._cross_script_group(identity, other, stem)
                instances += self._temporal_group(identity, stem)
                instances += self._evidence_group(identity, stem)
        self.rng.shuffle(instances)
        return instances

    # -- contrast group 1: cross-script name matching ----------------------

    def _cross_script_group(
        self, identity: Identity, other: Identity, stem: str
    ) -> list[Instance]:
        """E / C / N triple over the surname, holding the document fixed.

        This is the group that tests the core claim. The premise is identical
        across all three members; only the hypothesis changes.
        """
        group = f"{stem}-name"
        spec = self.languages[identity.language]
        translit = get_transliterator(identity.script, identity.language)
        premise = self.build_premise(identity)
        variants = sorted(translit.variants(identity.surname_native))

        # ENTAILMENT: a legitimate alternative romanisation of the same name.
        if variants and self.rng.random() < self.config.alt_romanisation_rate:
            claimed = self.rng.choice(variants)
            phenomenon = "cross_script_name_alt_romanisation"
        else:
            claimed = identity.surname_latin
            phenomenon = "cross_script_name_icao"

        entail = self._instance(
            id=f"{group}-e",
            identity=identity,
            premise=premise,
            field=Field.SURNAME,
            claimed_value=claimed,
            label=Label.ENTAILMENT,
            phenomenon=phenomenon,
            contrast_group_id=group,
            identity_id=stem,
            rationale=(
                f"The document prints {identity.surname_native!r} in "
                f"{spec.script.value}; {claimed!r} is an accepted Latin rendering "
                f"of that string, and the MRZ independently carries "
                f"{identity.surname_latin!r}."
            ),
        )

        # CONTRADICTION: a different person's surname. Chosen to be *close* in
        # Latin form where possible, so the instance is not solvable by a crude
        # edit-distance threshold.
        contradict = self._instance(
            id=f"{group}-c",
            identity=identity,
            premise=premise,
            field=Field.SURNAME,
            claimed_value=other.surname_latin,
            label=Label.CONTRADICTION,
            phenomenon="cross_script_name_mismatch",
            contrast_group_id=group,
            identity_id=stem,
            rationale=(
                f"{other.surname_latin!r} is not a rendering of "
                f"{identity.surname_native!r} under any accepted romanisation."
            ),
        )

        # NEUTRAL: the hypothesis asserts a field the document does not carry.
        absent_field = self.rng.choice(VIZ_ONLY_FIELDS)
        stripped = self.build_premise(identity, omit=frozenset({absent_field}))
        neutral = self._instance(
            id=f"{group}-n",
            identity=identity,
            premise=stripped,
            field=absent_field,
            claimed_value=self._value_of(identity, absent_field),
            label=Label.NEUTRAL,
            phenomenon="field_absent_from_document",
            contrast_group_id=group,
            identity_id=stem,
            rationale=(
                f"This document does not carry {absent_field.value}. The claim is "
                f"neither supported nor refuted by any evidence present; it must "
                f"be routed to human review rather than decided."
            ),
        )
        return [entail, contradict, neutral]

    # -- contrast group 2: cross-field temporal consistency -----------------

    def _temporal_group(self, identity: Identity, stem: str) -> list[Instance]:
        """E / C triple over jointly-(im)possible date combinations.

        A rule engine should score close to ceiling here. That is the point:
        this group is the control that tells us how much of any headline number
        comes from a subproblem that does not need a neural model at all.
        """
        group = f"{stem}-time"
        premise = self.build_premise(identity)

        consistent = self._instance(
            id=f"{group}-e",
            identity=identity,
            premise=premise,
            field=Field.DATE_OF_EXPIRY,
            claimed_value=identity.date_of_expiry.isoformat(),
            label=Label.ENTAILMENT,
            phenomenon="temporal_consistent",
            contrast_group_id=group,
            identity_id=stem,
            rationale=(
                f"Issued {identity.date_of_issue.isoformat()} under the "
                f"{identity.template_era} template, expiring "
                f"{identity.date_of_expiry.isoformat()}: a 10-year validity "
                f"consistent with the template era."
            ),
        )

        # The impossible triple from the proposal: each field individually valid,
        # jointly impossible.
        broken = Identity(**{**identity.__dict__})
        broken.date_of_expiry = _add_years(identity.date_of_issue, 40)
        broken_premise = self.build_premise(broken)
        impossible = self._instance(
            id=f"{group}-c",
            identity=broken,
            premise=broken_premise,
            field=Field.DATE_OF_EXPIRY,
            claimed_value=broken.date_of_expiry.isoformat(),
            label=Label.CONTRADICTION,
            phenomenon="impossible_date_triple",
            contrast_group_id=group,
            identity_id=stem,
            rationale=(
                f"Issue {broken.date_of_issue.isoformat()} and expiry "
                f"{broken.date_of_expiry.isoformat()} imply a 40-year validity. "
                f"No passport in the {broken.template_era} series is issued for "
                f"more than 10 years, so the fields are jointly impossible even "
                f"though each is individually well-formed."
            ),
        )
        return [consistent, impossible]

    # -- contrast group 3: evidence quality --------------------------------

    def _evidence_group(self, identity: Identity, stem: str) -> list[Instance]:
        """Separates 'the document says otherwise' from 'the document cannot say'.

        The two members differ only in whether the relevant field survived OCR.
        This is the group that makes the NEUTRAL definition operational, and it
        is the one a confidence-threshold system cannot get right by construction.
        """
        group = f"{stem}-evidence"

        # Heavy corruption destroys the VIZ surname, but the MRZ is also removed,
        # so no zone can adjudicate the claim: structurally NEUTRAL.
        destroyed = self.build_premise(identity, omit=frozenset({Field.SURNAME}))
        illegible = FieldObservation(
            field=Field.SURNAME,
            zone=Zone.VIZ,
            value="?" * max(3, len(identity.surname_native)),
            script=identity.script,
            language=identity.language,
            confidence=0.05,
            clean_value=identity.surname_native,
        )
        destroyed = [*destroyed, illegible]

        neutral = self._instance(
            id=f"{group}-n",
            identity=identity,
            premise=destroyed,
            field=Field.SURNAME,
            claimed_value=identity.surname_latin,
            label=Label.NEUTRAL,
            phenomenon="field_illegible",
            contrast_group_id=group,
            identity_id=stem,
            rationale=(
                "The surname is present on the document but unreadable, and no "
                "other zone carries it. The claim cannot be adjudicated from this "
                "evidence; it is not contradicted."
            ),
        )

        # Same claim, legible document that says something else: CONTRADICTION.
        premise = self.build_premise(identity)
        wrong = self._instance(
            id=f"{group}-c",
            identity=identity,
            premise=premise,
            field=Field.DATE_OF_BIRTH,
            claimed_value=_shift_date(identity.date_of_birth, days=1).isoformat(),
            label=Label.CONTRADICTION,
            phenomenon="date_off_by_one",
            contrast_group_id=group,
            identity_id=stem,
            rationale=(
                "Both the VIZ and the MRZ legibly carry a different date of birth. "
                "The evidence is present and refutes the claim."
            ),
        )
        return [neutral, wrong]

    # -- helpers ------------------------------------------------------------

    def _instance(
        self,
        *,
        id: str,
        identity: Identity,
        premise: list[FieldObservation],
        field: Field,
        claimed_value: str,
        label: Label,
        phenomenon: str,
        contrast_group_id: str,
        rationale: str,
        identity_id: str,
    ) -> Instance:
        hypothesis = Hypothesis(
            field=field,
            value=claimed_value,
            script=Script.LATIN,
            language="en",
            text=_verbalise(field, claimed_value),
        )
        return Instance(
            id=id,
            language=identity.language,
            premise=premise,
            hypothesis=hypothesis,
            label=label,
            identity_id=identity_id,
            contrast_group_id=contrast_group_id,
            phenomenon=phenomenon,
            rationale=rationale,
            provenance=Provenance(
                generator="synthetic_v0",
                source_corpus="kyc_nli.data.name_pools (embedded)",
                source_license="MIT",
                seed=self.config.seed,
                contains_real_pii=False,
            ),
        )

    @staticmethod
    def _value_of(identity: Identity, field: Field) -> str:
        return {
            Field.PLACE_OF_BIRTH: identity.place_of_birth,
            Field.DATE_OF_ISSUE: identity.date_of_issue.isoformat(),
            Field.ISSUING_AUTHORITY: identity.issuing_authority,
            Field.SURNAME: identity.surname_latin,
            Field.GIVEN_NAMES: identity.given_latin,
        }.get(field, "")


_FIELD_PHRASES: dict[Field, str] = {
    Field.SURNAME: "The holder's surname is {value}.",
    Field.GIVEN_NAMES: "The holder's given names are {value}.",
    Field.DATE_OF_BIRTH: "The holder was born on {value}.",
    Field.DATE_OF_ISSUE: "The document was issued on {value}.",
    Field.DATE_OF_EXPIRY: "The document expires on {value}.",
    Field.DOCUMENT_NUMBER: "The document number is {value}.",
    Field.NATIONALITY: "The holder's nationality is {value}.",
    Field.SEX: "The holder's recorded sex is {value}.",
    Field.PLACE_OF_BIRTH: "The holder was born in {value}.",
    Field.ISSUING_AUTHORITY: "The document was issued by {value}.",
    Field.DOCUMENT_TYPE: "The document type is {value}.",
    Field.TEMPLATE_ERA: "The document uses the {value} design.",
}


def _verbalise(field: Field, value: str) -> str:
    """Natural-language rendering of a hypothesis, for the neural models."""
    return _FIELD_PHRASES[field].format(value=value)


def _confidence_from_edits(edits: list[str], original: str) -> float:
    """Crude per-field OCR confidence: 1 minus the corrupted character fraction.

    Deliberately crude. A real engine's confidence is not this, and any result
    that depends on the exact shape of this function is not a real result.
    """
    if not original:
        return 1.0
    return max(0.0, 1.0 - len(edits) / len(original))


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return d.replace(year=d.year + years, day=28)


def _shift_date(d: date, days: int) -> date:
    return d + timedelta(days=days)
