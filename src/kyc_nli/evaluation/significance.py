"""Bootstrap confidence intervals and paired significance testing.

Why this exists: without it, every number in a results table is an assertion
rather than a measurement, and "0.980 versus 0.649" invites the question "how
many runs, and is that difference real?" with no answer. `docs/evaluation-
protocol.md` requires intervals on every reported macro-F1.

THE RESAMPLING UNIT IS THE CONTRAST GROUP, NOT THE INSTANCE.

This is the one decision here that is easy to get wrong and expensive to get
wrong. Instances within a contrast group share a premise — they differ only in
the hypothesis — so their outcomes are correlated. Resampling instances
independently treats correlated observations as independent, which understates
the variance and produces intervals that are too narrow. Narrow intervals make
differences look significant when they are not, which is exactly the error a
reviewer is looking for.

The same reasoning drives group-level train/test splitting in
``kyc_nli.data.io.split_by_identity``. It is the same correlation, handled
consistently.

For comparing two systems we use a PAIRED bootstrap: one resample, both systems
scored on it, the difference recorded. Comparing two independently-computed
intervals and checking whether they overlap is a weaker and commonly-misread
test — two overlapping intervals can still correspond to a significant paired
difference.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from kyc_nli.schema import Instance, Label, Prediction

LABEL_ORDER: tuple[Label, ...] = (Label.ENTAILMENT, Label.CONTRADICTION, Label.NEUTRAL)

#: Default resample count. 1000 is the figure named in the evaluation protocol;
#: it gives a stable 95% interval to roughly the third decimal, which is finer
#: than any difference we would claim.
DEFAULT_RESAMPLES = 1000


@dataclass(frozen=True)
class Interval:
    """A point estimate with a percentile bootstrap confidence interval."""

    point: float
    low: float
    high: float
    n_resamples: int
    confidence: float = 0.95

    @property
    def width(self) -> float:
        return self.high - self.low

    def __str__(self) -> str:
        return f"{self.point:.4f} [{self.low:.4f}, {self.high:.4f}]"


@dataclass(frozen=True)
class Comparison:
    """A paired-bootstrap comparison of two systems on the same instances."""

    system_a: str
    system_b: str
    delta: float
    low: float
    high: float
    #: Fraction of resamples in which A did NOT beat B. This is a bootstrap
    #: p-value for the one-sided hypothesis "A is better than B"; it is not a
    #: p-value from a parametric test and should not be described as one.
    p_value: float
    n_resamples: int

    @property
    def significant(self) -> bool:
        """True when the 95% interval on the difference excludes zero."""
        return self.low > 0 or self.high < 0

    def __str__(self) -> str:
        verdict = "significant" if self.significant else "NOT significant"
        return (
            f"{self.system_a} - {self.system_b} = {self.delta:+.4f} "
            f"[{self.low:+.4f}, {self.high:+.4f}], p={self.p_value:.3f} ({verdict})"
        )


def _encode(instances: list[Instance], predictions: list[Prediction]) -> tuple:
    """Return (gold, pred, group_index) as integer arrays for fast resampling."""
    by_id = {p.instance_id: p for p in predictions}
    missing = [i.id for i in instances if i.id not in by_id]
    if missing:
        raise ValueError(f"{len(missing)} instances have no prediction, e.g. {missing[:3]}")

    label_ix = {lab: i for i, lab in enumerate(LABEL_ORDER)}
    gold = np.fromiter((label_ix[i.label] for i in instances), dtype=np.int8, count=len(instances))
    pred = np.fromiter(
        (label_ix[by_id[i.id].label] for i in instances), dtype=np.int8, count=len(instances)
    )

    groups: dict[str, list[int]] = defaultdict(list)
    for idx, inst in enumerate(instances):
        groups[inst.contrast_group_id or inst.id].append(idx)
    # Ragged by construction: groups differ in size, which is itself a reason to
    # resample groups rather than instances.
    group_members = [np.array(v, dtype=np.int32) for v in groups.values()]
    return gold, pred, group_members


def _macro_f1(gold: np.ndarray, pred: np.ndarray) -> float:
    """Macro-F1 over the three labels. Matches sklearn's zero_division=0."""
    total = 0.0
    for k in range(len(LABEL_ORDER)):
        tp = np.count_nonzero((pred == k) & (gold == k))
        fp = np.count_nonzero((pred == k) & (gold != k))
        fn = np.count_nonzero((pred != k) & (gold == k))
        denom = 2 * tp + fp + fn
        total += (2 * tp / denom) if denom else 0.0
    return total / len(LABEL_ORDER)


def _resample_indices(
    group_members: list[np.ndarray], rng: np.random.Generator
) -> np.ndarray:
    picks = rng.integers(0, len(group_members), size=len(group_members))
    return np.concatenate([group_members[p] for p in picks])


def bootstrap_macro_f1(
    instances: list[Instance],
    predictions: list[Prediction],
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = 20260906,
    confidence: float = 0.95,
) -> Interval:
    """Percentile bootstrap confidence interval on macro-F1.

    Resamples contrast groups with replacement; see the module docstring for why
    the group and not the instance is the unit.
    """
    gold, pred, group_members = _encode(instances, predictions)
    point = _macro_f1(gold, pred)

    rng = np.random.default_rng(seed)
    scores = np.empty(n_resamples, dtype=np.float64)
    for b in range(n_resamples):
        idx = _resample_indices(group_members, rng)
        scores[b] = _macro_f1(gold[idx], pred[idx])

    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(scores, [tail, 1.0 - tail])
    return Interval(
        point=point,
        low=float(low),
        high=float(high),
        n_resamples=n_resamples,
        confidence=confidence,
    )


def paired_bootstrap(
    instances: list[Instance],
    predictions_a: list[Prediction],
    predictions_b: list[Prediction],
    system_a: str = "A",
    system_b: str = "B",
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = 20260906,
    confidence: float = 0.95,
) -> Comparison:
    """Paired bootstrap on the macro-F1 difference between two systems.

    Both systems are scored on the *same* resample, so the comparison controls
    for which instances happened to be drawn. This is strictly more powerful
    than checking whether two separately-computed intervals overlap, and it is
    the test to use when claiming a model beats the rule baseline.
    """
    gold, pred_a, group_members = _encode(instances, predictions_a)
    _, pred_b, _ = _encode(instances, predictions_b)

    delta = _macro_f1(gold, pred_a) - _macro_f1(gold, pred_b)

    rng = np.random.default_rng(seed)
    deltas = np.empty(n_resamples, dtype=np.float64)
    for b in range(n_resamples):
        idx = _resample_indices(group_members, rng)
        g = gold[idx]
        deltas[b] = _macro_f1(g, pred_a[idx]) - _macro_f1(g, pred_b[idx])

    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(deltas, [tail, 1.0 - tail])
    p_value = float(np.count_nonzero(deltas <= 0) / n_resamples)
    return Comparison(
        system_a=system_a,
        system_b=system_b,
        delta=float(delta),
        low=float(low),
        high=float(high),
        p_value=p_value,
        n_resamples=n_resamples,
    )
