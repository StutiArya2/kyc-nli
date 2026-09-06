"""Core data model for KYC-NLI.

The task is framed as document-level NLI:

    premise    = the set of field observations physically present on a document
                 (multiple zones, multiple scripts, possibly OCR-corrupted)
    hypothesis = a single assertion about the holder, drawn from an application
                 form, a sanctions record, or another document
    label      = ENTAILMENT / CONTRADICTION / NEUTRAL

The critical definition is NEUTRAL. In this project NEUTRAL is a property of the
*premise*, not of the model: it means the document does not carry the evidence
needed to adjudicate the hypothesis at all. It is NOT a confidence threshold.
See docs/label-definitions.md and docs/decisions/0002-neutral-is-evidence-insufficiency.md.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField


class Label(str, Enum):
    """Three-way NLI label."""

    ENTAILMENT = "entailment"
    CONTRADICTION = "contradiction"
    NEUTRAL = "neutral"


class Script(str, Enum):
    """Writing system of an observed string. Distinct from language."""

    LATIN = "Latn"
    DEVANAGARI = "Deva"
    TAMIL = "Taml"
    BENGALI = "Beng"
    ARABIC = "Arab"  # Perso-Arabic, used for Urdu
    # Retained but not in the active language set; see decision 0005.
    CYRILLIC = "Cyrl"
    HAN = "Hani"


class Zone(str, Enum):
    """Where on (or around) the document a value was read from.

    Zones matter because the same logical field appears in several zones in
    different scripts and formats, and the cross-zone comparison is exactly
    where exact string matching fails.
    """

    VIZ = "viz"  # Visual Inspection Zone: the human-readable printed face
    MRZ = "mrz"  # Machine Readable Zone: ICAO 9303, Latin-only, A-Z0-9< 
    BARCODE = "barcode"  # PDF417 / QR payload, where present
    CHIP = "chip"  # eMRTD DG1/DG11 contactless chip read
    FORM = "form"  # user-typed onboarding form; not part of the document


class Field(str, Enum):
    """Closed schema of identity fields this project reasons over.

    Deliberately small. Every field here appears in ICAO Doc 9303 MRZ or in the
    VIZ of the document types covered by MIDV-2020.
    """

    SURNAME = "surname"
    GIVEN_NAMES = "given_names"
    DATE_OF_BIRTH = "date_of_birth"
    DATE_OF_ISSUE = "date_of_issue"
    DATE_OF_EXPIRY = "date_of_expiry"
    DOCUMENT_NUMBER = "document_number"
    NATIONALITY = "nationality"
    SEX = "sex"
    PLACE_OF_BIRTH = "place_of_birth"
    ISSUING_AUTHORITY = "issuing_authority"
    DOCUMENT_TYPE = "document_type"
    TEMPLATE_ERA = "template_era"  # design generation of the physical document


#: Fields that carry a date and are subject to cross-field temporal rules.
DATE_FIELDS: frozenset[Field] = frozenset(
    {Field.DATE_OF_BIRTH, Field.DATE_OF_ISSUE, Field.DATE_OF_EXPIRY}
)

#: Fields the MRZ is capable of carrying at all (ICAO 9303 TD1/TD3).
MRZ_FIELDS: frozenset[Field] = frozenset(
    {
        Field.SURNAME,
        Field.GIVEN_NAMES,
        Field.DATE_OF_BIRTH,
        Field.DATE_OF_EXPIRY,
        Field.DOCUMENT_NUMBER,
        Field.NATIONALITY,
        Field.SEX,
        Field.DOCUMENT_TYPE,
    }
)


class FieldObservation(BaseModel):
    """One value as actually read from one zone of one document.

    ``value`` is the *observed* string, i.e. post-OCR and therefore possibly
    corrupted. ``clean_value`` retains the ground-truth string that was printed,
    for error analysis only -- it must never be visible to a model at inference.
    """

    model_config = ConfigDict(frozen=True)

    field: Field
    zone: Zone
    value: str
    script: Script
    language: str = PydanticField(description="BCP-47-ish language code, e.g. 'ru', 'ar'")
    confidence: float = PydanticField(default=1.0, ge=0.0, le=1.0)
    clean_value: str | None = PydanticField(
        default=None, description="Ground-truth pre-noise string. Analysis only, never an input."
    )

    @property
    def was_corrupted(self) -> bool:
        return self.clean_value is not None and self.clean_value != self.value


class Hypothesis(BaseModel):
    """The assertion being checked against the document."""

    model_config = ConfigDict(frozen=True)

    field: Field
    value: str
    script: Script
    language: str
    #: Natural-language rendering, used by the neural NLI models. The rule
    #: baseline uses the structured fields above and ignores this.
    text: str


class Provenance(BaseModel):
    """How an instance came to exist. Required for every instance.

    Reviewers will ask where every example came from. Making this mandatory and
    machine-readable means the benchmark card can be regenerated from the data.
    """

    model_config = ConfigDict(frozen=True)

    generator: str = PydanticField(description="e.g. 'synthetic_v0', 'midv2020_derived'")
    source_corpus: str | None = None
    source_license: str | None = None
    seed: int | None = None
    #: True only if any byte traces back to a real person's real document.
    contains_real_pii: bool = False


class Instance(BaseModel):
    """One labelled NLI instance: document evidence + hypothesis + gold label."""

    id: str
    language: str
    premise: list[FieldObservation]
    hypothesis: Hypothesis
    label: Label

    #: Minimal-pair grouping. All instances sharing a contrast_group_id differ by
    #: one controlled edit; a model must get the whole group right to score on
    #: the contrast metric. This is what separates semantic inference from
    #: surface string similarity.
    contrast_group_id: str | None = None
    #: Which phenomenon this instance is designed to probe, e.g.
    #: 'cross_script_name', 'impossible_date_triple', 'ocr_homoglyph',
    #: 'field_absent'. Drives the per-phenomenon breakdown in evaluation.
    phenomenon: str = "unspecified"
    #: Human-readable reason the gold label is what it is. Doubles as the
    #: target for the explanation component.
    rationale: str = ""
    provenance: Provenance

    def observations(self, field: Field) -> list[FieldObservation]:
        """All premise observations of ``field``, across zones."""
        return [o for o in self.premise if o.field == field]

    def observation(self, field: Field, zone: Zone) -> FieldObservation | None:
        for o in self.premise:
            if o.field == field and o.zone == zone:
                return o
        return None

    @property
    def premise_fields(self) -> set[Field]:
        return {o.field for o in self.premise}


class Prediction(BaseModel):
    """A system's output for one instance."""

    instance_id: str
    label: Label
    #: Probability assigned to the predicted label. Used for risk-coverage
    #: curves; systems that cannot produce one should report 1.0 and will
    #: simply have a flat curve.
    confidence: float = PydanticField(default=1.0, ge=0.0, le=1.0)
    #: Which premise observations drove the decision. Required for the
    #: explainability claim to be measurable rather than asserted.
    supporting: list[str] = PydanticField(default_factory=list)
    conflicting: list[str] = PydanticField(default_factory=list)
    rationale: str = ""
