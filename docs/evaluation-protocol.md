# Evaluation protocol

Frozen for v1. Changing anything here means every previously reported number is
no longer comparable, so changes go through a decision record.

## Mandatory reporting axes

A result is not reportable unless all four are present. Reporting only the first
is how a weak result gets past a skim.

1. **Overall** — macro-F1 plus per-class F1. Macro, never accuracy: the classes
   are not balanced in deployment and NEUTRAL is the rarest and most costly.
2. **Per language** — macro-F1 for each of the five. A headline driven by English
   says nothing about the cross-script claim.
3. **Per phenomenon** — accuracy on each probed phenomenon
   (`cross_script_name_icao`, `cross_script_name_alt_romanisation`,
   `cross_script_name_mismatch`, `temporal_consistent`,
   `impossible_date_triple`, `date_off_by_one`, `field_absent_from_document`,
   `field_illegible`). Without this, a win on the easy temporal cases hides a
   loss on cross-script matching.
4. **Contrast-group consistency** — the fraction of minimal-pair groups where
   *every* member is correct. A model exploiting surface string similarity
   scores well on (1) and badly here. This is the metric that catches it.

## Deployment-facing metrics

The system's purpose is to route work to humans, so it is also judged on:

- **false-mismatch rate** — genuine holders rejected because two spellings
  differ. The incumbent system's headline failure; the number the project exists
  to reduce.
- **overconfident-on-NEUTRAL rate** — decisions made on insufficient evidence.
  The failure mode that costs money and creates regulatory exposure.
- **over-abstention rate** — cases sent to a human that the document actually
  decided.
- **human review load** — the fraction routed to review. Meaningless without an
  error rate beside it; always report the pair.

## Selective prediction

The NEUTRAL-to-human-review mechanism is operationally an abstention policy, so
it is compared on a curve rather than on accuracy. Run it with
`kyc-nli risk-coverage`; the measured result is in
[m4-selective-prediction.md](m4-selective-prediction.md).

**Two curves, and they answer different questions.**

- `risk_coverage` ranks predictions by confidence, keeps the most confident
  fraction, and reports the error rate among those kept. It asks whether a
  system's confidence is worth anything. Ties are averaged over orderings within
  the tied block, not broken by input order — a system that reports the same
  confidence for everything must render as a flat line, and breaking ties by
  dataset order drew it a descending one instead.
- `selective_curve` counts a NEUTRAL prediction as **sent to a human**: never an
  error, never coverage. It asks what the system costs to operate. This is the
  one the project's claim is stated in, because charging a structural abstention
  as an error scores the safest possible system as the worst one.

**Never compare two systems at their own operating points when the claim is about
review load.** They abstain at different rates and macro-F1 charges nothing for
the labour that buys. Use `review_load_at_error`: fix the automation error rate,
report what each system costs to run there, and report "unreachable" rather than
"100% review" when a system cannot meet the budget at any threshold — declining
to answer is not meeting a target.

This is also the diagnostic for decision 0002: a system whose NEUTRAL class is
really a confidence threshold produces a curve indistinguishable from
thresholding on confidence directly. A system whose NEUTRAL is structural does
not. If our curves are indistinguishable, the three-way formulation is not
earning its place and we must say so.

## Baselines that must be beaten

| Baseline | Purpose | Status |
| --- | --- | --- |
| `exact_match` | Quantifies the incumbent problem. **A win over this alone is strawmanning and must never be the headline.** | ✅ implemented |
| `rule_engine` | Transliteration-aware rules + ICAO tables + MRZ check digits + fuzzy thresholds. **This is the baseline that matters.** | ✅ implemented |
| zero-shot LLM | Reference point, one table row | not implemented |
| fine-tuned cross-encoder | The method | not implemented |

The rule engine is deliberately built to win. Do not weaken it to make a model
look better; add the weakening to the ablation table instead.

## Splits

Split by **contrast group**, stratified by **language**.

- Group-level splitting: members of a group share a premise, so a group
  straddling train/test lets a model memorise the document instead of reasoning.
- Language stratification: an earlier lexical sort of group ids put 100% of the
  test set in one language. Both properties are asserted in `tests/test_generate.py`.

Default fractions: 70 / 15 / 15. Thresholds are tuned on **dev only**.

## Noise conditions

Every headline table is reported at all four noise levels (`clean`, `light`,
`moderate`, `heavy`). A single-noise-level result is not interpretable, because
the Phase-0 finding is precisely that the ranking of methods depends on the
noise level.

## Significance

Every reported macro-F1 carries a percentile bootstrap 95% confidence interval,
1000 resamples. Implemented in `kyc_nli.evaluation.significance`; on by default
in `kyc-nli compare` and `kyc-nli run-baseline`.

**The resampling unit is the contrast group, not the instance.** Members of a
group share a premise and differ only in the hypothesis, so their outcomes are
correlated. Resampling instances independently treats correlated observations as
independent, understates the variance, and produces intervals that are too narrow
— measured at about 7% too narrow on the current test set. Too-narrow intervals
make differences look significant when they are not, which is precisely the error
a reviewer is looking for. This is the same correlation that forces group-level
train/test splitting, handled consistently.
`tests/test_significance.py::test_group_resampling_gives_wider_intervals_than_instance_resampling`
fails the build if the unit is ever changed back.

**Compare two systems with the paired bootstrap**, not by eyeballing whether two
intervals overlap. One resample, both systems scored on it, the difference
recorded. Two overlapping intervals can still correspond to a significant paired
difference, so the overlap heuristic is both weaker and commonly misread. Use
`paired_bootstrap` for any claim that one system beats another.

A difference whose paired interval includes zero is not a difference, however
large the point estimate looks.

## Reproducibility

Every number in the paper must be regenerable by one command from
`kyc_nli.cli` plus a config in `configs/` plus a seed. If a number came out of a
notebook, it does not go in the paper until it comes out of a script.
