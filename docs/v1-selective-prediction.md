# V1 selective prediction — dev-selected policies, 28 October 2026

At a common requested 5% automation-error budget, the dev-selected local XLM-R
policy reviews 28.57% of test cases and makes 20 errors among 750 automated
decisions (2.67%). The rule policy reviews 93.05% and makes 0 errors among 73
automated decisions. The archived XLM-R policy misses this test target: 25/449
errors (5.57%) with 57.24% review.

These are empirical results on the frozen synthetic v1 benchmark. Meeting a
point-estimate target does not guarantee a population or deployment risk bound.

## Provenance and policy

Command and configuration:

```powershell
.\.venv\Scripts\python.exe -m kyc_nli.cli selective-v1 --config configs/experiments/v1_selective.yaml
```

Output: `results/v1_selective/20261027T184121.760526Z/`.

The command reuses the completed, fixed test predictions from
`results/v1_evaluation/20261027T181210.848535Z/` and performs new inference on
the 1,050-case v1 dev split. The prior test classification results had already
been inspected; this is not a new blind test. No test prediction was changed.
The reference predictions' complete classification metrics were reproduced as
an integrity check. Model, tokenizer, dataset, inference configuration and source
fingerprints were checked against the reference run, and input/source hashes
were verified again after completion.

Both models remain frozen: length 192, batch size 4, float32 CPU inference, two
threads, seed 20260906, evaluation mode and deterministic algorithms. No model
training, confidence recalibration, or label changes were performed.

| Artifact | SHA-256 |
| --- | --- |
| V1 dev | `1e9a3e159514435d332c65f4cd2d60f0bc88e8cf3405bce42c1661e02fe24c5c` |
| V1 test | `10ef67fe3247bbc3b5aea36c41c06aa1ff3c5d0c8403a27f1ecf4bd15221984c` |
| Local checkpoint | `ae040c211cd20036ea1a610ee8decab193fa4738f10ec2f31c29f1723e805dad` |
| Archived checkpoint | `469c1d7860f087b99ecd34f5f7dcc56218df66fd393729ebc8904d1a38b25144` |

Predicted NEUTRAL always goes to review. Other predictions are automated only
when confidence is at least the chosen threshold. For each predefined budget,
the threshold maximizes dev automation coverage subject to the empirical dev
error cap. All distinct confidence levels are searched; ties are indivisible.
Each system's choices are written to `dev_thresholds.json` before parsing and
scoring its test prediction rows. Test labels never enter threshold selection.
Confidence thresholds are not moved after observing test outcomes.

## Test outcomes at each requested budget

Each cell is **review % / automated errors divided by automated decisions**.
`MISS` marks a test point estimate over the requested budget.

| Requested maximum error | Rule engine | Local XLM-R | Archived XLM-R |
| --- | --- | --- | --- |
| 10% | 63.33% / 39/385 = 10.13% **MISS** | 28.57% / 20/750 = 2.67% | 52.10% / 50/503 = 9.94% |
| 5% | 93.05% / 0/73 = 0.00% | 28.57% / 20/750 = 2.67% | 57.24% / 25/449 = 5.57% **MISS** |
| 2% | 93.05% / 0/73 = 0.00% | 30.76% / 10/727 = 1.38% | 60.86% / 8/411 = 1.95% |
| 1% | 93.05% / 0/73 = 0.00% | 34.10% / 3/692 = 0.43% | 64.00% / 1/378 = 0.26% |

Exact matching has no non-empty dev operating point at any of these budgets.
This is reported as `NO_NONEMPTY_DEV_OPERATING_POINT`, not as a successful
zero-risk policy achieved by reviewing everything.

| Budget | Rule threshold | Local threshold | Archived threshold |
| --- | ---: | ---: | ---: |
| 10% | 0.4 | 0.5057051777839661 | 0.6116482019424438 |
| 5% | 1.0 | 0.5057051777839661 | 0.6426082849502563 |
| 2% | 1.0 | 0.9600021243095398 | 0.6931144595146179 |
| 1% | 1.0 | 0.9754278063774109 | 0.7662451267242432 |

The historical claim that the rule engine cannot reach a 5% target must not be
carried into v1. Its dev-selected threshold has zero observed test errors here,
at the cost of reviewing most cases. Conversely, the archived model cannot be
said to meet the 5% target on this test, regardless of its lower review load.

## Uncertainty and paired review-load comparisons

The frozen protocol is retained: 1,000 percentile bootstrap draws over contrast
groups, seed 20260906. Each draw uses the same groups for every system. Thresholds
remain fixed at their dev-selected values; this measures test-sample uncertainty
conditional on those choices, not uncertainty from resampling dev or retraining.

At the requested 5% budget:

- Local model test risk: 2.67%, contrast-group bootstrap 95% CI **[1.59%, 3.73%]**.
- Archived model test risk: 5.57%, corresponding CI **[3.49%, 7.57%]**.
- Rule risk: 0/73. The empirical nonparametric interval degenerates to [0, 0]
  because no observed errors can be resampled. It must not be interpreted as
  evidence that the true error probability is zero.

Wilson 95% intervals are provided separately as an **iid reference only**, not
as cluster-aware guarantees. The upper Wilson endpoint for 0/73 is about 5.00%.
For the local model's 1% target, its 3/692 point estimate is 0.43%, but the iid
Wilson upper endpoint is 1.27%. The report therefore explicitly marks every
operating point as providing no statistical guarantee.

For budgets where both the local and rule test point estimates meet the cap,
the paired review-load savings (rule minus local) are:

| Requested budget | Saving, percentage points | Paired bootstrap 95% CI |
| --- | ---: | --- |
| 5% | **64.48** | **[62.09, 66.76]** |
| 2% | 62.29 | [59.66, 64.98] |
| 1% | 58.95 | [55.79, 62.08] |

These compare policies selected at a common requested budget. Their realized
test error rates are not identical. The 10% comparison fails the two-system
attainment check because the rule test point is over budget. The archived
model's 5% comparison also fails that check. The machine-readable report retains
these flags rather than converting such cases into review-load success claims.

## Artifacts and validation

- `start.json`: configuration, input hashes, source snapshots and reference run.
- Per-system `dev_predictions.jsonl`: fresh dev predictions.
- Per-system `dev_thresholds.json`: locked dev choices and dev data hash.
- Per-system `selective.json`: test counts, coverage/review/risk, confidence
  intervals, target-attainment flags and diagnostic test curves.
- `summary.json`: completion, all system reports and paired review differences.

All frozen data, original predictions and checkpoints remain unchanged.
Tests: **413 passed, 7 skipped**; Ruff passed. Regression tests cover dev/test
separation, confidence ties, structural NEUTRAL review, empty automation sets,
Wilson behavior at zero errors, contrast-group resampling and exact case-ID joins.
Preparation backup and logs are in
`results/v1_selective_preparation_20261027T183531Z/`.

The main remaining limits are synthetic data, incomplete independent human label
validation, previously inspected test classification results, and the absence of
population-risk guarantees. No publication, manuscript replacement, data release,
commit or merge completion was performed.
