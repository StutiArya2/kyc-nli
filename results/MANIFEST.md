# Results manifest

`results/` is gitignored except this file. Reports are machine-written by
`kyc-nli run-baseline` and `kyc-nli compare`; never hand-edit one, regenerate it.

| Report | Produced by | Committed? |
| --- | --- | --- |
| `rule_engine.md` / `.json` | `kyc-nli run-baseline rule_engine` | no |
| `exact_match.md` / `.json` | `kyc-nli run-baseline exact_match` | no |
| noise ablation (stdout) | `scripts/run_noise_ablation.ps1` | no — the table lives in `docs/plan.md` |
| `ocr-calibration.md` | `kyc-nli calibrate-ocr` | no — analysis lives in `docs/m1-ocr-calibration-findings.md` |
| `transliteration.md` | `kyc-nli translit-eval` | no — analysis lives in `docs/m2-dakshina-findings.md` |
| `selective-prediction.json` | `kyc-nli risk-coverage` | no — analysis lives in `docs/m4-selective-prediction.md` |
| `noise_robustness.json` | `python scripts/noise_robustness.py` | no — feeds `paper/` via `scripts/make_figures.py` and `make_tables.py` |
| `models/cross_encoder/` | `scripts/train_cross_encoder.py` | no — 520 MB |
| `models/cross_encoder_LEAKED_SPLIT_invalid/` | an invalidated run, kept so nobody believes its 0.989 | no |

## Phase-0 headline, 2026-09-06

5 languages (en, hi, ta, bn, ur) x 120 identities, seed 20260906, group-level language-stratified splits.

| OCR noise | exact_match macro-F1 (95% CI) | rule_engine macro-F1 (95% CI) | rule contrast | rule false-mismatch |
| --- | --- | --- | --- | --- |
| clean | 0.368 [0.341, 0.392] | 0.981 [0.971, 0.991] | 0.956 | 0.000 |
| light | 0.354 [0.326, 0.380] | 0.920 [0.900, 0.938] | 0.815 | 0.075 |
| moderate | 0.252 [0.231, 0.275] | 0.597 [0.552, 0.644] | 0.333 | 0.087 |
| heavy | 0.219 [0.206, 0.235] | 0.361 [0.315, 0.404] | 0.074 | 0.029 |

Interpretation and caveats: `docs/plan.md`.

## M4 selective prediction, 2026-09-12

1,050 held-out instances, 150 identities never seen in training, measured
moderate noise. "Error" is the error rate among cases decided *without* a human.
Produced by `kyc-nli risk-coverage`; curves in `results/selective-prediction.json`.

Revised 2026-10-22: thresholds chosen on dev by exact search, applied to test.
Cells are test review load (test error); x = over budget on test.

| system | its own point | err <= 10% | err <= 5% | err <= 2% | err <= 1% |
| --- | --- | --- | --- | --- | --- |
| exact_match | 0% review @ 54.2% error | unreachable | unreachable | unreachable | unreachable |
| rule_engine | 63.4% review @ 11.2% error | 63.4% (11.2% x) | 92.7% (5.2% x) | unreachable | unreachable |
| cross_encoder | 28.6% review @ 4.0% error | 28.6% (4.0%) | 28.6% (4.0%) | 35.5% (1.8%) | 41.5% (1.1% x) |

## Noise robustness, 2026-10-21

The same 1,050 held-out instances at every noise level; only OCR damage varies.
Produced by `python scripts/noise_robustness.py`; full results in
`results/noise_robustness.json`. Macro-F1; the cross-encoder was trained at
moderate only.

| system | clean | light | moderate | heavy |
| --- | --- | --- | --- | --- |
| exact_match | 0.391 | 0.369 | 0.268 | 0.207 |
| rule_engine | 0.991 | 0.928 | 0.601 | 0.380 |
| cross_encoder | 0.986 | 0.984 | 0.972 | 0.911 |
| ours - rules (paired) | -0.005 (n.s.) | +0.056 | +0.371 | +0.531 |

Interpretation and caveats: `docs/m4-selective-prediction.md`.
