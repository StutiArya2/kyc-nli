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

## Phase-0 headline, 2026-09-06

5 languages (en, hi, ta, bn, ur) x 120 identities, seed 20260906, group-level language-stratified splits.

| OCR noise | exact_match macro-F1 (95% CI) | rule_engine macro-F1 (95% CI) | rule contrast | rule false-mismatch |
| --- | --- | --- | --- | --- |
| clean | 0.368 [0.341, 0.392] | 0.981 [0.971, 0.991] | 0.956 | 0.000 |
| light | 0.354 [0.326, 0.380] | 0.920 [0.900, 0.938] | 0.815 | 0.075 |
| moderate | 0.252 [0.231, 0.275] | 0.597 [0.552, 0.644] | 0.333 | 0.087 |
| heavy | 0.219 [0.206, 0.235] | 0.361 [0.315, 0.404] | 0.074 | 0.029 |

Interpretation and caveats: `docs/plan.md`.
