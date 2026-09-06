"""Exact-string-match baseline: the system KYC-NLI claims to replace.

This is the WEAK baseline. It exists to quantify the problem, not to be beaten
impressively. Reporting only a win over this would be strawmanning; see
``kyc_nli.baselines.rules`` for the baseline that actually has to be beaten.
"""

from __future__ import annotations

from kyc_nli.schema import Instance, Label, Prediction


class ExactMatchBaseline:
    """Compares the hypothesis value byte-for-byte against every observation.

    Has no notion of NEUTRAL, so it never predicts one. That is the honest
    behaviour of the incumbent system and the source of its false-mismatch rate.
    """

    name = "exact_match"

    def predict(self, instance: Instance) -> Prediction:
        claimed = instance.hypothesis.value.strip().upper()
        supporting: list[str] = []

        for obs in instance.observations(instance.hypothesis.field):
            if obs.value.strip().upper() == claimed:
                supporting.append(f"{obs.zone.value}:{obs.field.value}")

        if supporting:
            return Prediction(
                instance_id=instance.id,
                label=Label.ENTAILMENT,
                confidence=1.0,
                supporting=supporting,
                rationale="Exact string match found.",
            )
        return Prediction(
            instance_id=instance.id,
            label=Label.CONTRADICTION,
            confidence=1.0,
            conflicting=[
                f"{o.zone.value}:{o.field.value}"
                for o in instance.observations(instance.hypothesis.field)
            ],
            rationale="No exact string match; treated as a mismatch.",
        )
