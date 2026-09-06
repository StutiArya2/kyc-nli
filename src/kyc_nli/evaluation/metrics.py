"""Evaluation protocol for KYC-NLI.

Four reporting levels, all of which are mandatory. Reporting only the first is
how a weak result gets published:

1. OVERALL   macro-F1 and per-class F1. Macro, not accuracy: the classes are
             not balanced in deployment and NEUTRAL is the rarest and most
             consequential.
2. PER-LANGUAGE  a headline driven by English tells us nothing about the
             cross-script claim.
3. PER-PHENOMENON  separates the subproblems. If the temporal cases carry the
             average while cross-script matching is flat, the contribution is
             a rule engine wearing a transformer.
4. CONTRAST-GROUP CONSISTENCY  the fraction of minimal-pair groups where every
             member is correct. A model exploiting surface similarity scores
             well on (1) and badly here.

Operational metrics come after: a KYC system routing NEUTRAL to human review is
judged on how much human review it buys and what it costs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sklearn.metrics import classification_report, confusion_matrix

from kyc_nli.schema import Instance, Label, Prediction

LABEL_ORDER: tuple[Label, ...] = (Label.ENTAILMENT, Label.CONTRADICTION, Label.NEUTRAL)


@dataclass
class EvaluationReport:
    system: str
    n_instances: int
    macro_f1: float
    per_class_f1: dict[str, float]
    per_language_macro_f1: dict[str, float]
    per_phenomenon_accuracy: dict[str, float]
    contrast_consistency: float
    n_contrast_groups: int
    #: Rate at which the system says ENTAILMENT/CONTRADICTION when the gold
    #: label is NEUTRAL. In deployment this is an unreviewed decision on
    #: insufficient evidence, which is the failure mode that costs money.
    overconfident_rate: float
    #: Rate at which the system says NEUTRAL when the document actually decides.
    over_abstention_rate: float
    #: The metric the incumbent system is judged on: a genuine holder rejected
    #: because two spellings of their name differ.
    false_mismatch_rate: float
    confusion: list[list[int]] = field(default_factory=list)
    review_load: float = 0.0

    def to_markdown(self) -> str:
        lines = [
            f"### {self.system}",
            "",
            f"- instances: {self.n_instances}",
            f"- macro-F1: **{self.macro_f1:.4f}**",
            f"- contrast-group consistency: **{self.contrast_consistency:.4f}** "
            f"({self.n_contrast_groups} groups)",
            f"- false-mismatch rate: {self.false_mismatch_rate:.4f}",
            f"- overconfident on NEUTRAL: {self.overconfident_rate:.4f}",
            f"- over-abstention: {self.over_abstention_rate:.4f}",
            f"- human review load: {self.review_load:.4f}",
            "",
            "| class | F1 |",
            "| --- | --- |",
        ]
        lines += [f"| {k} | {v:.4f} |" for k, v in self.per_class_f1.items()]
        lines += ["", "| language | macro-F1 |", "| --- | --- |"]
        lines += [f"| {k} | {v:.4f} |" for k, v in sorted(self.per_language_macro_f1.items())]
        lines += ["", "| phenomenon | accuracy |", "| --- | --- |"]
        lines += [
            f"| {k} | {v:.4f} |"
            for k, v in sorted(self.per_phenomenon_accuracy.items(), key=lambda kv: kv[1])
        ]
        return "\n".join(lines)


def evaluate(
    system: str,
    instances: list[Instance],
    predictions: list[Prediction],
) -> EvaluationReport:
    """Score ``predictions`` against the gold labels on ``instances``."""
    by_id = {p.instance_id: p for p in predictions}
    missing = [i.id for i in instances if i.id not in by_id]
    if missing:
        raise ValueError(f"{len(missing)} instances have no prediction, e.g. {missing[:3]}")

    gold = [i.label.value for i in instances]
    pred = [by_id[i.id].label.value for i in instances]
    labels = [lab.value for lab in LABEL_ORDER]

    report = classification_report(
        gold, pred, labels=labels, output_dict=True, zero_division=0
    )
    per_class_f1 = {lab: float(report[lab]["f1-score"]) for lab in labels}
    macro_f1 = float(report["macro avg"]["f1-score"])

    # Per-language macro-F1.
    per_language: dict[str, float] = {}
    by_language: dict[str, list[Instance]] = defaultdict(list)
    for inst in instances:
        by_language[inst.language].append(inst)
    for lang, subset in by_language.items():
        g = [i.label.value for i in subset]
        p = [by_id[i.id].label.value for i in subset]
        r = classification_report(g, p, labels=labels, output_dict=True, zero_division=0)
        per_language[lang] = float(r["macro avg"]["f1-score"])

    # Per-phenomenon accuracy.
    hits: dict[str, list[bool]] = defaultdict(list)
    for inst in instances:
        hits[inst.phenomenon].append(by_id[inst.id].label is inst.label)
    per_phenomenon = {k: sum(v) / len(v) for k, v in hits.items()}

    # Contrast-group consistency.
    groups: dict[str, list[bool]] = defaultdict(list)
    for inst in instances:
        if inst.contrast_group_id:
            groups[inst.contrast_group_id].append(by_id[inst.id].label is inst.label)
    consistency = (
        sum(1 for members in groups.values() if all(members)) / len(groups) if groups else 0.0
    )

    # Deployment-facing rates.
    neutral_gold = [i for i in instances if i.label is Label.NEUTRAL]
    overconfident = (
        sum(1 for i in neutral_gold if by_id[i.id].label is not Label.NEUTRAL)
        / len(neutral_gold)
        if neutral_gold
        else 0.0
    )
    decidable = [i for i in instances if i.label is not Label.NEUTRAL]
    over_abstention = (
        sum(1 for i in decidable if by_id[i.id].label is Label.NEUTRAL) / len(decidable)
        if decidable
        else 0.0
    )
    entailed = [i for i in instances if i.label is Label.ENTAILMENT]
    false_mismatch = (
        sum(1 for i in entailed if by_id[i.id].label is Label.CONTRADICTION) / len(entailed)
        if entailed
        else 0.0
    )
    review_load = sum(1 for p in predictions if p.label is Label.NEUTRAL) / len(predictions)

    return EvaluationReport(
        system=system,
        n_instances=len(instances),
        macro_f1=macro_f1,
        per_class_f1=per_class_f1,
        per_language_macro_f1=per_language,
        per_phenomenon_accuracy=per_phenomenon,
        contrast_consistency=consistency,
        n_contrast_groups=len(groups),
        overconfident_rate=overconfident,
        over_abstention_rate=over_abstention,
        false_mismatch_rate=false_mismatch,
        confusion=confusion_matrix(gold, pred, labels=labels).tolist(),
        review_load=review_load,
    )


def risk_coverage(
    instances: list[Instance],
    predictions: list[Prediction],
    steps: int = 20,
) -> list[tuple[float, float]]:
    """Risk-coverage curve: (coverage, error rate) as the confidence bar rises.

    This is the selective-prediction view. It matters because the proposal's
    NEUTRAL-to-human-review mechanism is, operationally, an abstention policy,
    and abstention policies are compared on this curve rather than on accuracy.
    A system whose NEUTRAL class is really a confidence threshold will show an
    identical curve to one that thresholds on confidence directly; a system
    whose NEUTRAL is structural will not.
    """
    by_id = {p.instance_id: p for p in predictions}
    scored = sorted(
        ((by_id[i.id].confidence, by_id[i.id].label is i.label) for i in instances),
        key=lambda t: t[0],
        reverse=True,
    )
    n = len(scored)
    curve: list[tuple[float, float]] = []
    for k in range(1, steps + 1):
        cut = max(1, round(n * k / steps))
        window = scored[:cut]
        errors = sum(1 for _, correct in window if not correct)
        curve.append((cut / n, errors / cut))
    return curve
