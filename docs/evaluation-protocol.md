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
it is compared on a **risk–coverage curve**, not on accuracy
(`kyc_nli.evaluation.risk_coverage`).

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

With n ≈ 1000 test instances, report bootstrap 95% confidence intervals
(1000 resamples) on macro-F1. Differences smaller than the interval width are
not differences. Not yet implemented; required before M3 results are written up.

## Reproducibility

Every number in the paper must be regenerable by one command from
`kyc_nli.cli` plus a config in `configs/` plus a seed. If a number came out of a
notebook, it does not go in the paper until it comes out of a script.
