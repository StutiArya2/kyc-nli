# Corrected v1 freeze and separate frozen-checkpoint evaluations

The surname-negative generator is corrected, `synth_v1` is frozen, and both
XLM-R checkpoints have been evaluated independently on its 1,050-case test split.
These are new v1 results; the historical v0 records are preserved.

## What changed

The default generator now produces `synthetic_v1` provenance. It rejects negative
claims that match the holder's clean canonical surname, the transliterator's
accepted clean renderings, or alternate Latin spellings paired with the same
normalized native surname in the embedded pool. Comparison uses Unicode NFKC,
case folding and removal of non-alphanumeric separators. It never uses corrupted
OCR text to decide whether a surname is a valid negative.

Only a colliding proposed negative is replaced. Replacement uses a separate RNG,
seeded by the master seed and identity ID; it consumes no identity or OCR RNG
state. Exhausting the eligible pool raises an error. The rule baseline is unchanged.

An explicit `GeneratorConfig(dataset_version="synth_v0")` retains the historical
generator for reproduction. It was checked against the preserved full v0 file:
byte-identical output. The old noise-robustness script explicitly selects that
legacy version, preventing an accidental mixture of corrected and historical data.

`kyc-nli generate` now defaults to a v1 filename and refuses existing dataset,
split or manifest targets. Use the dedicated freeze command below for the
full versioned audit.

## Frozen dataset

Manifest: `data/processed/synth_v1.manifest.json`.

Configuration: `configs/experiments/v1_freeze.yaml`, seed 20260906, measured
moderate noise, 200 identities per configured language, alternative romanisation
rate 0.4. Languages are loaded from the registry rather than hardcoded.

| Split | Instances | Entailment | Contradiction | Neutral |
| --- | ---: | ---: | ---: | ---: |
| Train | 4,900 | 1,400 | 2,100 | 1,400 |
| Dev | 1,050 | 300 | 450 | 300 |
| Test | 1,050 | 300 | 450 | 300 |

There are 7,000 cases and 1,000 surname contradictions in total. Exactly **56**
invalid negative claims were repaired, including **6** test claims. Their original
v0 claims exactly match the clean-alias collision set. No valid negative was
replaced. Apart from the v1 provenance stamp, only those negative hypotheses and
their rationales changed. All premises, identity IDs, labels and split membership
are unchanged. Repeat generation was identical.

The six changed test IDs are:

```text
bn-00027-name-c
en-00057-name-c
en-00139-name-c
hi-00023-name-c
ta-00064-name-c
ur-00023-name-c
```

The freeze checks found zero clean-name alias collisions under the configured
engine/pool equivalence, zero identity or contrast-group overlap across splits,
zero ground-truth serialization flags, and no real PII. Name contrast groups
retain exactly one E/C/N case each. Both evaluations also verified zero identity-ID
and clean document-number overlap with the preserved v0 training split.

| JSONL file | SHA-256 |
| --- | --- |
| All | `cfe397f6c3dc71abc0200a34a83877e589e466fcfb15eb23dcbc2d10ac9bc6ef` |
| Train | `15b62576a90945bb277cf6a2ebee6d1d4229d2dfd617557de8b04f482676d398` |
| Dev | `1e9a3e159514435d332c65f4cd2d60f0bc88e8cf3405bce42c1661e02fe24c5c` |
| Test | `10ef67fe3247bbc3b5aea36c41c06aa1ff3c5d0c8403a27f1ecf4bd15221984c` |

## Separate evaluation results

Run directory: `results/v1_evaluation/20261027T181210.848535Z/`.
Configuration: `configs/experiments/v1_evaluate.yaml`.

Both checkpoints were evaluated frozen, without training, at maximum length 192,
batch size 4, float32 on CPU, two threads, seed 20260906 and deterministic
algorithms. The label order is entailment, contradiction, neutral. The same
repository scorer and 1,000-draw contrast-group bootstrap were used for every
system; the frozen evaluation protocol was not changed.

| System | Macro-F1, 95% CI | Wrong-name contradictions detected |
| --- | --- | ---: |
| Exact match | 0.2686 [0.2488, 0.2881] | 150/150 |
| Rule engine | 0.6059 [0.5693, 0.6447] | 147/150 |
| Local XLM-R | **0.9814 [0.9739, 0.9890]** | **144/150** |
| Archived XLM-R | **0.8441 [0.8273, 0.8619]** | **8/150** |

| Checkpoint | Weight SHA-256 |
| --- | --- |
| Local | `ae040c211cd20036ea1a610ee8decab193fa4738f10ec2f31c29f1723e805dad` |
| Archived | `469c1d7860f087b99ecd34f5f7dcc56218df66fd393729ebc8904d1a38b25144` |

Local confusion matrix (gold rows, predicted columns, E/C/N):

```text
286   14    0
  6  444    0
  0    0  300
```

Archived confusion matrix (same order):

```text
271   29    0
146  304    0
  0    0  300
```

The archived full-test matrix happens to equal its historical v0 matrix. This
was confirmed by new inference on v1, not copied from the historical report.
Its 142/150 wrong-name over-entailments remain after the generator correction.
For the local model, the only v0-to-v1 prediction-label changes are the six
repaired test hypotheses; each now receives contradiction. This is an input-change
audit, not a statistical comparison across benchmark versions.

Within v1, paired-bootstrap macro-F1 differences versus the unchanged rule engine:

- Local XLM-R: +0.3755, 95% CI [0.3362, 0.4137].
- Archived XLM-R: +0.2382, 95% CI [0.1885, 0.2896].

The default policy sends predicted neutral to review. It produces 300/1,050
reviews for either learned checkpoint, with 20/750 automated errors for the local
weights and 175/750 for the archived weights. These are descriptive default-policy
counts, not dev-selected operating points, risk guarantees or equal-error
review-load comparisons. No threshold was selected on test.

Each system has its own `predictions.jsonl`, `metrics.json` and `errors.csv`.
Metrics include class F1, language results with confidence intervals, phenomenon
accuracy, contrast consistency, confusion, wrong-name counts and default-policy
counts. `start.json` records every input hash, source/configuration snapshots,
checkpoint/tokenizer files, runtime and label-index mapping; `summary.json`
records completion and successful post-run input/source hash verification.

## Commands and validation

```powershell
.\.venv\Scripts\python.exe -m kyc_nli.cli freeze-v1 --config configs/experiments/v1_freeze.yaml
.\.venv\Scripts\python.exe -m kyc_nli.cli evaluate-v1 --config configs/experiments/v1_evaluate.yaml
```

The freeze command deliberately refuses to overwrite an existing frozen file.
To reproduce generation into a new location, copy the freeze YAML and change its
output path; retain the preserved v0 reference. To evaluate that new freeze, point
a copied evaluation config at its manifest. Every evaluation creates a new
timestamped directory. Both checkpoints remain v0-trained; neither was retrained.

Validation: **406 passed, 7 skipped; Ruff passed**. Tests cover exact collisions,
full-width/case/separator-normalized variants, embedded-pool aliases, exhausted
pools, RNG preservation, deterministic repair, immutable output targets and freeze
hashes. Skips are for absent optional OCR rendering dependencies and the extracted
Dakshina corpus; the optional fine-tuning smoke test remains excluded by default.

The pre-v1 source backup, JUnit/lint logs, freeze checks, original-artifact integrity
checks and evaluation console log are in
`results/v1_preparation_20261027T174835Z/`. All 21 original protected v0 artifacts
were verified unchanged. No commit, merge completion, publication, manuscript
rewrite or data release was performed.

This fixes a specific generator defect. It does not independently validate all
remaining labels under OCR damage, establish real-document performance or replace
human validation. Accepted-name equivalence is limited to the implemented engines
and embedded pools. Original training-data byte hashes are not available, so
training provenance retains the limits described in the v0 trace report.
