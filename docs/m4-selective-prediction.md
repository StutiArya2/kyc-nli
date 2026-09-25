# M4 — Selective prediction: what the review load actually buys

**Date:** 2026-09-12 · **Status:** complete · **Reproduce:** `kyc-nli risk-coverage`
· **Artefact:** `results/selective-prediction.json`

**The result:** at a fixed automation error budget of 5%, the rule engine cannot
operate at all and the cross-encoder runs at **28.6% review load**. The headline
macro-F1 comparison understates the gap, because it scores abstention and
decision on the same footing and the deployed system does not.

---

## Why macro-F1 is the wrong axis for this claim

The M3 table reports each system at its own operating point:

| system | macro-F1 | sent to a human |
| --- | --- | --- |
| rule engine | 0.601 | 63.4% |
| cross-encoder | 0.972 | 28.6% |

That is not a like-for-like comparison, and a reviewer is right to say so. A
system that abstains more buys a lower error rate with human labour, and macro-F1
charges it nothing for the labour. The honest question is the one a compliance
function asks: **hold the error rate fixed, and tell me what each system costs to
run there.**

Two curves answer it, and they are not the same curve.

- **Risk–coverage** ranks every prediction by confidence, keeps the most
  confident fraction, and reports the error rate among those kept. It answers
  *is this system's confidence worth anything*, and nothing else.
- **The selective curve** treats a NEUTRAL prediction as *sent to a human* —
  never as an error, never as coverage — and sweeps a confidence bar over the
  decisions the system does make. It answers *what does this cost to operate*.

The second is the shape of the project's claim. Charging a structural NEUTRAL as
an error would score the safest possible system as the worst one.

## Review load at a fixed automation error

1,050 held-out instances, 150 identities never seen in training, moderate
measured noise. "Error" is the error rate among cases decided **without** a
human; "review load" is the fraction of traffic routed to one.

| system | its own point | err ≤ 10% | err ≤ 5% | err ≤ 2% | err ≤ 1% |
| --- | --- | --- | --- | --- | --- |
| exact match | 0% review @ **54.2% error** | unreachable | unreachable | unreachable | unreachable |
| rule engine | 63.4% review @ 11.2% error | 91.9% | **unreachable** | unreachable | unreachable |
| **cross-encoder** | 28.6% review @ **4.0% error** | **28.6%** | **28.6%** | 42.3% | 48.7% |

Read the rule-engine row twice. It is already sending **63% of all traffic to a
human**, and the 37% it decides by itself is still **11.2% wrong**. To reach a
10% error budget it must review 91.9%. It never reaches 5% at any threshold — the
best it manages is 5.2% while reviewing 92.7% of traffic, which is not a system,
it is a queue with a cover sheet.

The cross-encoder meets the 10% and 5% budgets *at its own natural operating
point*: no threshold tuning is needed, because 28.6% review already delivers 4.0%
error. Tightening to a 1% error budget still leaves **51.3% of traffic
automated**.

The exact-match incumbent is on the table for scale. It never abstains, so it has
no operating curve at all: one point, 54.2% error, and no way to trade.

## The finding underneath: only the learned model's confidence means anything

The risk–coverage curves say why the rule engine cannot be tuned into the budget.
Risk at increasing coverage, most-confident first:

| coverage | 5% | 25% | 45% | 65% | 85% | 100% |
| --- | --- | --- | --- | --- | --- | --- |
| exact match | 0.542 | 0.542 | 0.542 | 0.542 | 0.542 | 0.542 |
| rule engine | 0.052 | 0.137 | 0.078 | 0.093 | 0.300 | 0.390 |
| cross-encoder | 0.000 | 0.000 | 0.000 | 0.000 | 0.007 | 0.029 |

- **The cross-encoder's curve is monotone and flat at zero to 65% coverage.** Its
  confidence genuinely ranks correctness, which is what makes a threshold a
  usable control.
- **The rule engine's is not monotone.** Risk rises from 0.052 to 0.137, falls to
  0.078, then climbs. Its confidences are hand-assigned constants — 0.99 for a
  check-digit verification, 0.85 for a literal mismatch, 0.5 for the
  indeterminate band — so they encode *which rule fired*, not *how likely that
  rule is to be right*. Sorting by them sorts by rule, and the rules are not
  ordered by reliability.
- **Exact match is exactly flat**, at its overall error rate, at every coverage.
  It reports 1.0 for every prediction; a flat line is the correct rendering of
  confidence that carries no information.

That last row is also a fixed bug. Ties used to be broken by the stable sort,
which falls back on dataset order, and the flat-confidence baseline was therefore
drawn a confidently *descending* curve — the most flattering possible reading of a
system with no confidence signal at all. Risk inside a tied block is now the
expectation over orderings within it. See `tests/test_metrics.py::
test_risk_coverage_is_flat_when_every_confidence_is_identical`.

**So the selective-prediction claim rests on calibration, not only on accuracy.**
A rule engine cannot be tuned to an error budget even in principle, because it has
nothing meaningful to threshold on. This is a sharper statement than "the model
scores higher" and it is the one the deployment argument needs.

## What this does and does not establish

It establishes the revised claim in the form the proposal stated it:

> Under OCR corruption, a learned entailment model recovers decisions a
> transliteration-aware rule engine must abstain on — reducing human review load
> at equal or better error rate.

Not merely at equal error: at **less than half** the rule engine's review load and
**under half** its automation error, simultaneously, with a further tightening
available on the curve.

It does not establish that the numbers transfer. Every caveat from M1 and M3
stands: the noise is measured on rendered text with no paper grain or glare, so it
is a lower bound on real-document error; no real identity document is involved;
and no human has annotated a label. **M5 remains the honest limit on all of it.**

One more limit specific to this milestone: the operating points are read off a
single test split with no confidence interval. Bootstrapping the *curve* — as
opposed to the point estimate of macro-F1, which M3 does bootstrap over contrast
groups — is outstanding. Until it is done, read "28.6% at 4.0%" as a point
estimate on 1,050 instances and not as a guarantee.
