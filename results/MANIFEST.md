# Results manifest

`results/` is gitignored except this file. Reports are machine-written by
`kyc-nli run-baseline` and `kyc-nli compare`; never hand-edit one, regenerate it.

| Report | Produced by | Committed? |
| --- | --- | --- |
| `rule_engine.md` / `.json` | `kyc-nli run-baseline rule_engine` | no |
| `exact_match.md` / `.json` | `kyc-nli run-baseline exact_match` | no |
| noise ablation (stdout) | `scripts/run_noise_ablation.ps1` | no — the table lives in `docs/plan.md` |

## Phase-0 headline, 2026-09-06

5 languages (en, hi, ta, bn, ur) x 120 identities, seed 20260906, group-level language-stratified splits.

| OCR noise | exact_match macro-F1 (95% CI) | rule_engine macro-F1 (95% CI) | rule contrast | rule false-mismatch |
| --- | --- | --- | --- | --- |
| clean | 0.371 [0.345, 0.395] | 0.980 [0.969, 0.989] | 0.952 | 0.000 |
| light | 0.359 [0.331, 0.384] | 0.903 [0.877, 0.925] | 0.793 | 0.098 |
| moderate | 0.353 [0.327, 0.377] | 0.831 [0.798, 0.860] | 0.652 | 0.133 |
| heavy | 0.285 [0.257, 0.312] | 0.649 [0.602, 0.694] | 0.396 | 0.156 |

Interpretation and caveats: `docs/plan.md`.
