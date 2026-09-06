# Results manifest

`results/` is gitignored except this file. Reports are machine-written by
`kyc-nli run-baseline` and `kyc-nli compare`; never hand-edit one, regenerate it.

| Report | Produced by | Committed? |
| --- | --- | --- |
| `rule_engine.md` / `.json` | `kyc-nli run-baseline rule_engine` | no |
| `exact_match.md` / `.json` | `kyc-nli run-baseline exact_match` | no |
| noise ablation (stdout) | `scripts/run_noise_ablation.ps1` | no — the table lives in `docs/plan.md` |

## Phase-0 headline, 2026-09-06

5 languages x 120 identities, seed 20260906, group-level language-stratified splits.

| OCR noise | exact_match macro-F1 | rule_engine macro-F1 | rule contrast consistency | rule false-mismatch |
| --- | --- | --- | --- | --- |
| clean | 0.425 | 0.977 | 0.944 | 0.000 |
| light | 0.411 | 0.899 | 0.782 | 0.119 |
| moderate | 0.373 | 0.801 | 0.633 | 0.216 |
| heavy | 0.289 | 0.650 | 0.385 | 0.136 |

Interpretation and caveats: `docs/plan.md`.
