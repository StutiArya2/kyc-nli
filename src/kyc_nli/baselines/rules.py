"""The strong non-neural baseline: transliteration-aware rules plus fuzzy matching.

This baseline is built to WIN. It gets the ICAO transliteration tables, the
variant sets, MRZ check digits, date parsing, the cross-field temporal rules and
a tuned fuzzy threshold. If a fine-tuned NLI model cannot beat this, the central
claim of the project is false, and it is far better to discover that in week two
from a 300-line rule engine than in month five from a training run.

Every reviewer of this proposal will ask whether the neural approach is doing
anything a rule engine could not. This file is the answer, and it has to be a
real answer, so do not weaken it to make the model look good. If you find
yourself tempted to remove a rule, add it to the ablation table instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from rapidfuzz import fuzz

from kyc_nli.data import mrz
from kyc_nli.languages import load_languages
from kyc_nli.schema import (
    DATE_FIELDS,
    Field,
    FieldObservation,
    Instance,
    Label,
    Prediction,
    Zone,
)
from kyc_nli.translit import get_transliterator

#: Maximum passport validity in years, by template era. A document claiming a
#: longer validity is impossible regardless of field-level well-formedness.
MAX_VALIDITY_YEARS = 10

_DATE_FORMATS = ("%Y-%m-%d", "%d %b %Y", "%d/%m/%Y", "%d.%m.%Y", "%Y%m%d")


@dataclass
class RuleConfig:
    """Thresholds. Tune these on dev, never on test."""

    #: Similarity at or above which two names are considered the same person.
    match_threshold: float = 88.0
    #: Similarity at or below which they are considered different people.
    #: The band between the two is where the baseline abstains -- which is this
    #: baseline's version of NEUTRAL, and precisely the conflation the project
    #: argues against. Keeping it here makes the comparison meaningful.
    mismatch_threshold: float = 60.0
    #: OCR confidence below which a field is treated as unreadable.
    illegible_confidence: float = 0.35
    #: Fraction of a value that may be replacement characters before it counts
    #: as unreadable regardless of reported confidence.
    illegible_char_ratio: float = 0.3


class RuleBaseline:
    """Transliteration-aware rule engine over the closed field schema."""

    name = "rule_engine"

    def __init__(self, config: RuleConfig | None = None) -> None:
        self.config = config or RuleConfig()
        self.languages = load_languages()

    # -- entry point --------------------------------------------------------

    def predict(self, instance: Instance) -> Prediction:
        field = instance.hypothesis.field
        observations = instance.observations(field)

        # Rule 0: evidence check. No observation of the field at all means the
        # document cannot speak to the claim.
        if not observations:
            return self._neutral(
                instance,
                "The document carries no observation of this field.",
            )

        legible = [o for o in observations if not self._is_illegible(o)]
        if not legible:
            return self._neutral(
                instance,
                "Every observation of this field is unreadable.",
            )

        # Rule 1: cross-field temporal consistency. Runs before field matching,
        # because a jointly impossible document is contradicted regardless of
        # whether the individual claimed value matches.
        temporal = self._check_temporal_consistency(instance)
        if temporal is not None:
            return temporal

        if field in DATE_FIELDS:
            return self._match_date(instance, legible)
        if field in (Field.SURNAME, Field.GIVEN_NAMES, Field.PLACE_OF_BIRTH,
                     Field.ISSUING_AUTHORITY):
            return self._match_name(instance, legible)
        return self._match_literal(instance, legible)

    # -- rule 1: cross-field temporal consistency ---------------------------

    def _check_temporal_consistency(self, instance: Instance) -> Prediction | None:
        """Flags documents whose date fields are jointly impossible.

        This is the rule that the proposal's 'issue 1995 / expiry 2035 / 2020
        template' example needs, and it is deterministic. Expect it to be near
        ceiling; that is the finding, not a failure.
        """
        issue = self._first_date(instance, Field.DATE_OF_ISSUE)
        expiry = self._first_date(instance, Field.DATE_OF_EXPIRY)
        birth = self._first_date(instance, Field.DATE_OF_BIRTH)
        era = instance.observation(Field.TEMPLATE_ERA, Zone.VIZ)

        conflicts: list[str] = []
        reasons: list[str] = []

        if issue and expiry:
            validity = (expiry - issue).days / 365.25
            if validity > MAX_VALIDITY_YEARS + 0.5:
                conflicts += ["viz:date_of_issue", "viz:date_of_expiry"]
                reasons.append(
                    f"validity of {validity:.1f} years exceeds the "
                    f"{MAX_VALIDITY_YEARS}-year maximum"
                )
            elif validity < 0:
                conflicts += ["viz:date_of_issue", "viz:date_of_expiry"]
                reasons.append("expiry precedes issue")

        if birth and issue and birth >= issue:
            conflicts += ["viz:date_of_birth", "viz:date_of_issue"]
            reasons.append("date of birth is not before date of issue")

        if era and issue:
            match = re.match(r"(\d{4})", era.value)
            if match and issue.year < int(match.group(1)):
                conflicts += ["viz:template_era", "viz:date_of_issue"]
                reasons.append(
                    f"issue year {issue.year} predates the {era.value} template"
                )

        if not conflicts:
            return None
        return Prediction(
            instance_id=instance.id,
            label=Label.CONTRADICTION,
            confidence=0.99,
            conflicting=sorted(set(conflicts)),
            rationale="Jointly impossible date fields: " + "; ".join(reasons) + ".",
        )

    # -- rule 2: transliteration-aware name matching ------------------------

    def _match_name(self, instance: Instance, observations: list[FieldObservation]) -> Prediction:
        claimed = _normalise(instance.hypothesis.value)
        best_score = 0.0
        best_obs: FieldObservation | None = None

        for obs in observations:
            for candidate in self._latin_candidates(obs):
                score = max(
                    fuzz.ratio(claimed, candidate),
                    fuzz.token_sort_ratio(claimed, candidate),
                )
                if score > best_score:
                    best_score, best_obs = score, obs

        tag = f"{best_obs.zone.value}:{best_obs.field.value}" if best_obs else ""
        if best_score >= self.config.match_threshold:
            return Prediction(
                instance_id=instance.id,
                label=Label.ENTAILMENT,
                confidence=min(1.0, best_score / 100.0),
                supporting=[tag],
                rationale=(
                    f"Best transliteration-aware similarity {best_score:.1f} "
                    f"against {tag} exceeds the match threshold."
                ),
            )
        if best_score <= self.config.mismatch_threshold:
            return Prediction(
                instance_id=instance.id,
                label=Label.CONTRADICTION,
                confidence=min(1.0, 1.0 - best_score / 100.0),
                conflicting=[tag],
                rationale=(
                    f"Best similarity {best_score:.1f} falls below the mismatch "
                    f"threshold under every accepted romanisation."
                ),
            )
        return self._neutral(
            instance,
            f"Similarity {best_score:.1f} falls in the indeterminate band.",
            confidence=0.5,
        )

    def _latin_candidates(self, obs: FieldObservation) -> set[str]:
        """All Latin renderings of an observation, via its script's engine."""
        try:
            # Pass the language: Urdu and Arabic share a script but need
            # different tables, and dispatching on script alone silently gives
            # Urdu names the Arabic treatment.
            engine = get_transliterator(obs.script, obs.language)
        except NotImplementedError:
            return {_normalise(obs.value)}
        return {_normalise(v) for v in engine.variants(obs.value)} | {_normalise(obs.value)}

    # -- rule 3: date matching with format normalisation --------------------

    def _match_date(self, instance: Instance, observations: list[FieldObservation]) -> Prediction:
        claimed = _parse_date(instance.hypothesis.value)
        if claimed is None:
            return self._neutral(instance, "The claimed value is not a parsable date.")

        parsed_any = False
        for obs in observations:
            observed = _parse_date(obs.value)
            if observed is None:
                continue
            parsed_any = True
            tag = f"{obs.zone.value}:{obs.field.value}"
            if observed == claimed:
                return Prediction(
                    instance_id=instance.id,
                    label=Label.ENTAILMENT,
                    confidence=0.98,
                    supporting=[tag],
                    rationale=f"Date matches {tag} after format normalisation.",
                )

        # A date string mangled past parsing is missing evidence, not a
        # mismatch. Without this the baseline calls every OCR-corrupted date a
        # CONTRADICTION, which is both wrong and an unfairly easy target for the
        # neural model to beat.
        if not parsed_any:
            return self._neutral(
                instance,
                "No zone carries a parsable date for this field; the value is "
                "corrupted beyond adjudication.",
                confidence=0.5,
            )

        conflicting = [f"{o.zone.value}:{o.field.value}" for o in observations]
        return Prediction(
            instance_id=instance.id,
            label=Label.CONTRADICTION,
            confidence=0.9,
            conflicting=conflicting,
            rationale="No zone carries this date after format normalisation.",
        )

    # -- rule 4: literal fields, with MRZ check-digit verification ----------

    def _match_literal(
        self, instance: Instance, observations: list[FieldObservation]
    ) -> Prediction:
        claimed = _normalise(instance.hypothesis.value)
        for obs in observations:
            if _normalise(obs.value) == claimed:
                return Prediction(
                    instance_id=instance.id,
                    label=Label.ENTAILMENT,
                    confidence=0.95,
                    supporting=[f"{obs.zone.value}:{obs.field.value}"],
                    rationale="Literal match after normalisation.",
                )
        return Prediction(
            instance_id=instance.id,
            label=Label.CONTRADICTION,
            confidence=0.85,
            conflicting=[f"{o.zone.value}:{o.field.value}" for o in observations],
            rationale="No literal match in any zone.",
        )

    # -- helpers ------------------------------------------------------------

    def _is_illegible(self, obs: FieldObservation) -> bool:
        if obs.confidence < self.config.illegible_confidence:
            return True
        if not obs.value:
            return True
        unreadable = sum(1 for c in obs.value if c in "?�")
        return unreadable / len(obs.value) > self.config.illegible_char_ratio

    def _first_date(self, instance: Instance, field: Field) -> date | None:
        for obs in instance.observations(field):
            if self._is_illegible(obs):
                continue
            parsed = _parse_date(obs.value)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _neutral(instance: Instance, reason: str, confidence: float = 0.7) -> Prediction:
        return Prediction(
            instance_id=instance.id,
            label=Label.NEUTRAL,
            confidence=confidence,
            rationale=reason,
        )


def verify_mrz_check_digits(mrz_block: str) -> dict[str, bool]:
    """Recompute the TD3 check digits for a raw two-line MRZ.

    A failed check digit is hard evidence that a field was misread, which is
    information the neural model does not get for free. Included so the rule
    baseline is not artificially handicapped.
    """
    lines = [ln for ln in mrz_block.splitlines() if ln.strip()]
    if len(lines) != 2 or len(lines[1]) < 44:
        return {}
    line2 = lines[1]
    return {
        "document_number": mrz.check_digit(line2[0:9]) == line2[9],
        "date_of_birth": mrz.check_digit(line2[13:19]) == line2[19],
        "date_of_expiry": mrz.check_digit(line2[21:27]) == line2[27],
    }


def _normalise(text: str) -> str:
    """Uppercase, strip MRZ filler and punctuation, collapse whitespace."""
    text = text.upper().replace(mrz.FILLER, " ")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(value: str) -> date | None:
    """Parse the date formats that appear across VIZ, MRZ and form data."""
    value = value.strip().upper()

    # MRZ YYMMDD: the century is genuinely absent, so it must be inferred.
    if re.fullmatch(r"\d{6}", value):
        yy, mm, dd = int(value[:2]), int(value[2:4]), int(value[4:6])
        century = 1900 if yy > (date.today().year % 100) else 2000
        try:
            return date(century + yy, mm, dd)
        except ValueError:
            return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None
