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

from kyc_nli.evaluation.significance import Interval, bootstrap_macro_f1
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
    #: 95% bootstrap CI on macro-F1, resampled over contrast groups. None when
    #: evaluate() was called with bootstrap=0. A macro-F1 reported without this
    #: is an assertion, not a measurement -- see docs/evaluation-protocol.md.
    macro_f1_ci: Interval | None = None

    def to_markdown(self) -> str:
        lines = [
            f"### {self.system}",
            "",
            f"- instances: {self.n_instances}",
            (
                f"- macro-F1: **{self.macro_f1:.4f}**"
                + (
                    f"  (95% CI [{self.macro_f1_ci.low:.4f}, {self.macro_f1_ci.high:.4f}], "
                    f"{self.macro_f1_ci.n_resamples} resamples over contrast groups)"
                    if self.macro_f1_ci
                    else ""
                )
            ),
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
    bootstrap: int = 0,
    seed: int = 20260906,
) -> EvaluationReport:
    """Score ``predictions`` against the gold labels on ``instances``.

    ``bootstrap`` is the number of resamples used for the macro-F1 confidence
    interval; 0 skips it. Pass ``DEFAULT_RESAMPLES`` for anything whose number
    goes in a table -- a bare point estimate invites "is that difference real?"
    with no answer.
    """
    if not instances:
        raise ValueError(
            "Cannot evaluate an empty instance list. An empty split is almost "
            "always a splitting bug rather than an intended experiment."
        )
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
    # Over the instances actually evaluated, not over `predictions`: a caller
    # scoring a subset passes the full prediction list, and counting the extras
    # would put this one rate on a different denominator from all the others.
    review_load = sum(1 for i in instances if by_id[i.id].label is Label.NEUTRAL) / len(instances)

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
        macro_f1_ci=(
            bootstrap_macro_f1(instances, predictions, n_resamples=bootstrap, seed=seed)
            if bootstrap
            else None
        ),
    )


def _ranked(
    instances: list[Instance], predictions: list[Prediction]
) -> list[tuple[float, bool, bool]]:
    """(confidence, correct, abstained) per instance, most confident first."""
    if not instances:
        raise ValueError("Cannot build a selective-prediction curve over no instances.")
    by_id = {p.instance_id: p for p in predictions}
    missing = [i.id for i in instances if i.id not in by_id]
    if missing:
        raise ValueError(f"{len(missing)} instances have no prediction, e.g. {missing[:3]}")
    def row(instance: Instance) -> tuple[float, bool, bool]:
        prediction = by_id[instance.id]
        return (
            prediction.confidence,
            prediction.label is instance.label,
            prediction.label is Label.NEUTRAL,
        )

    return sorted((row(i) for i in instances), key=lambda t: t[0], reverse=True)


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

    Coverage is the fraction of instances kept, taken most-confident-first; risk
    is the error rate among those kept. It ignores which label was predicted, so
    it answers "is this system's confidence worth anything" and nothing more.
    For the operational question -- how much human review does a given error
    budget buy -- use :func:`selective_curve`.

    **Ties are averaged, not ordered.** Instances sharing a confidence have no
    defensible order between them, and a stable sort would fall back on the order
    they arrived in. The exact-match baseline reports 1.0 for every prediction,
    so that fallback drew it a confidently descending curve that was purely an
    artefact of dataset order -- the most flattering possible reading of a system
    whose confidence carries no information at all. Risk inside a tied block is
    therefore the expectation over random orderings within it, which renders a
    flat-confidence system as the flat line it is.
    """
    scored = _ranked(instances, predictions)
    n = len(scored)

    # Cumulative expected errors at every cut, ties averaged within their block.
    cumulative: list[float] = [0.0]
    start = 0
    while start < n:
        end = start
        while end < n and scored[end][0] == scored[start][0]:
            end += 1
        block = end - start
        block_errors = sum(1 for _, correct, _ in scored[start:end] if not correct)
        for taken in range(1, block + 1):
            cumulative.append(cumulative[start] + block_errors * taken / block)
        start = end

    curve: list[tuple[float, float]] = []
    for k in range(1, steps + 1):
        cut = max(1, round(n * k / steps))
        curve.append((cut / n, cumulative[cut] / cut))
    return curve


@dataclass(frozen=True)
class OperatingPoint:
    """One (threshold -> review load, error) trade-off on the deployment curve."""

    threshold: float
    #: Fraction of traffic a human must look at: predicted NEUTRAL, or decided
    #: below the confidence bar.
    review_load: float
    #: Error rate among the cases the system decided *without* a human. This is
    #: the number a compliance function actually constrains.
    error_on_auto: float
    #: Fraction of traffic decided automatically. 1 - review_load.
    coverage: float
    n_auto: int

    def as_row(self) -> dict[str, float]:
        return {
            "threshold": self.threshold,
            "review_load": self.review_load,
            "error_on_auto": self.error_on_auto,
            "coverage": self.coverage,
            "n_auto": self.n_auto,
        }


def selective_curve(
    instances: list[Instance],
    predictions: list[Prediction],
    steps: int = 20,
) -> list[OperatingPoint]:
    """Review load against automation error, as the confidence bar is raised.

    This is the shape of the project's actual claim, and it differs from
    :func:`risk_coverage` in one way that matters: a NEUTRAL prediction is
    counted as *sent to a human*, never as an error and never as coverage. A
    system that abstains structurally is therefore not punished for abstaining,
    only for the decisions it does make -- which is how the deployed system is
    judged.

    At threshold 0 the review load is exactly the system's NEUTRAL rate, so the
    first point on this curve reproduces the ``review_load`` already reported by
    :func:`evaluate`, and the rest of the curve says what tightening the bar
    beyond that would buy.
    """
    scored = _ranked(instances, predictions)
    n = len(scored)
    points: list[OperatingPoint] = []
    for k in range(steps + 1):
        threshold = k / steps
        auto = [(c, ok) for c, ok, abstained in scored if not abstained and c >= threshold]
        n_auto = len(auto)
        errors = sum(1 for _, ok in auto if not ok)
        points.append(
            OperatingPoint(
                threshold=threshold,
                review_load=(n - n_auto) / n,
                error_on_auto=(errors / n_auto) if n_auto else 0.0,
                coverage=n_auto / n,
                n_auto=n_auto,
            )
        )
    return points


def operating_points(
    instances: list[Instance], predictions: list[Prediction]
) -> list[OperatingPoint]:
    """EVERY achievable operating point: one per distinct confidence value.

    Any threshold strictly between two adjacent confidences selects the same
    set of automated decisions as the upper one, so these are all the operating
    points there are. :func:`selective_curve` samples thresholds on a grid,
    which is fine for drawing a curve and wrong for answering "what is the best
    this system can do" -- the grid steps over cut points. The cross-encoder's
    confidences cluster just below 1.0, and a 0.01 grid lumped that whole
    cluster together: it reported 42.3% review at a 2% error budget where the
    true optimum is 35.4%.
    """
    scored = _ranked(instances, predictions)
    n = len(scored)
    decided = [(c, ok) for c, ok, abstained in scored if not abstained]
    points: list[OperatingPoint] = []
    errors = 0
    for idx, (conf, ok) in enumerate(decided):
        errors += not ok
        # Emit once per tie block, at its end: a threshold cannot split a tie.
        if idx + 1 == len(decided) or decided[idx + 1][0] != conf:
            k = idx + 1
            points.append(
                OperatingPoint(
                    threshold=conf,
                    review_load=(n - k) / n,
                    error_on_auto=errors / k,
                    coverage=k / n,
                    n_auto=k,
                )
            )
    return points


def review_load_at_error(
    instances: list[Instance],
    predictions: list[Prediction],
    max_error: float,
) -> OperatingPoint | None:
    """The cheapest operating point whose automation error stays within budget.

    "Cheapest" means lowest review load, found by an EXACT search over every
    achievable threshold (:func:`operating_points`), not a grid. Returns
    ``None`` when no threshold meets the budget -- which is a real answer, not a
    failure: it says the system cannot be operated at that error rate at any
    level of automation, and reporting an infeasible budget as 100% review
    would hide that.

    The threshold is chosen on ``instances`` themselves, so on a test split this
    is an ORACLE: the best the system could possibly do. That makes it the right
    tool for an impossibility claim ("unreachable even with the threshold tuned
    on the test set") and the wrong one for claiming a system meets a budget --
    for that, choose the threshold on dev with this function and apply it to
    test with :func:`operating_point_at`.
    """
    if not 0 <= max_error <= 1:
        raise ValueError(f"max_error must be a rate in [0, 1], got {max_error}")
    feasible = [p for p in operating_points(instances, predictions) if p.error_on_auto <= max_error]
    return min(feasible, key=lambda p: p.review_load) if feasible else None


def operating_point_at(
    instances: list[Instance], predictions: list[Prediction], threshold: float
) -> OperatingPoint:
    """What a FIXED threshold does on these instances.

    The honest half of a dev/test protocol: pick the threshold on dev with
    :func:`review_load_at_error`, then report what it does here. The error on
    test may exceed the budget it was tuned for -- that is the measurement, not
    a bug, and it is what a deployed system would actually experience.
    """
    scored = _ranked(instances, predictions)
    n = len(scored)
    auto = [ok for c, ok, abstained in scored if not abstained and c >= threshold]
    k = len(auto)
    return OperatingPoint(
        threshold=threshold,
        review_load=(n - k) / n,
        error_on_auto=(sum(1 for ok in auto if not ok) / k) if k else 0.0,
        coverage=k / n,
        n_auto=k,
    )
