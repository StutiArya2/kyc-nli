# v0 recovery and checkpoint provenance — 27 October 2026

The two conflicting wrong-name results are reproducible with **different XLM-R
checkpoints**. The preserved local weights reproduce the local prediction cache;
the weights in the downloaded historical archive reproduce the audit's severe
wrong-name failure. Neither result is a corrected-v1 evaluation.

## Preserved state and merge

The verified backup is `results/recovery_20261027T153518Z/`. Its
`backup_manifest.json` records 262 copied files, 5,118,754,234 bytes, and a SHA-256
for every copied file. All copy hashes matched their source before edits.
The snapshot includes the complete `.git` directory and original unmerged index,
working files, untracked notebooks, ignored datasets, reports, checkpoint copies
and original local ZIP/TAR archives. Rebuildable environments, node modules and
caches were excluded; the dependency freeze is retained.

Git cannot serialize the unmerged index with `git diff --cached --binary`.
That command's failure is recorded in the backup; the complete index itself is
preserved, alongside the unmerged entries, working-tree diff and status.

Resolved and staged the three conflicts:

- `tests/test_ocr_calibration.py`: retained optional FreeType/HarfBuzz guards and
  the required `script_of` import.
- `docs/m3-model-findings.md`: retained the completed local GPU run, the selective
  prediction workflow, outstanding uncertainty analysis, and synthetic-data limits.
- `docs/plan.md`: retained the completed GPU run and selective tooling while marking
  conflicting historical numerical claims for checkpoint-linked verification.

No unmerged index entries or conflict markers remain. **No merge commit was
created.** The existing staged work remains available to review. The active merge
parents at evaluation time were:

- HEAD: `382f52958e597f0c9a06a2d8b34b3d811965e1e4`
- MERGE_HEAD: `00116efd2eb7d9c59df6650061e6994b7d0b86f8`

## Primary evaluation: preserved local checkpoint

Output: `results/v0_trace/20261027T155356.047662Z/`.

The run verified its datasets, prediction cache and model files against the
pre-edit backup and checked their hashes again after evaluation. It saved exact
serialized inputs, predictions, source/configuration snapshots, dependency freeze,
working-tree patch, runtime details, metrics, and comparisons in a machine-written
manifest. This identifies the evaluated working tree even though HEAD alone does
not contain the uncommitted recovery code.

| Artifact | SHA-256 |
| --- | --- |
| `data/processed/synth_v0.test.jsonl` | `4f4475759dacfc5afedf799f9ed7fc58ff32abad80b4cb506aaa4bb70c3815bc` |
| `results/models/cross_encoder/model.safetensors` | `ae040c211cd20036ea1a610ee8decab193fa4738f10ec2f31c29f1723e805dad` |

Both local checkpoint copies have identical weight hashes. Their tokenizer files
and training summaries are also recorded in the run manifest.

Settings: CPU, float32, batch size 4, maximum length **192**, two PyTorch threads,
seed 20260906, deterministic algorithms, evaluation mode, no gradients or sampling,
local files only. Runtime: PyTorch 2.14.1+cpu, Transformers 5.20.2. Class indices
are 0=entailment, 1=contradiction, 2=neutral, following the same `LABELS` constant
used by training. The checkpoint config itself uses generic `LABEL_0/1/2` names;
it does not independently attest the original class semantics.

| Fresh local result | Value |
| --- | --- |
| Test cases | 1,050 |
| Macro-F1, 95% CI | **0.9759 [0.9669, 0.9843]** |
| CI method | Existing contrast-group percentile bootstrap, 1,000 draws, seed 20260906 |
| Accuracy | 1,024/1,050 = 97.52% |
| Wrong-name contradictions detected against original gold | 138/150 |
| Default review | 300/1,050 = 28.57% |
| Default automated errors | 26/750 = 3.47% |
| Fresh/cache label disagreements | **0/1,050** |
| Maximum absolute fresh/cache confidence difference | 0.00000303984 |

Fresh confusion matrix, gold rows and predicted columns in E/C/N order:

```text
286   14    0
 12  438    0
  0    0  300
```

The maximum serialized pair length is 184 tokens; the wrong-name maximum is 182.
No pair is truncated at 192, so changing the maximum length to 256 cannot change
these pairs' unpadded token IDs. This is not an inference rerun at 256.

The stored train/dev/test files contain 4,900/1,050/1,050 cases and
700/150/150 identities, respectively, with zero cross-split identity-ID overlap.
The serializer and model wrapper were unchanged from HEAD. No generator, labels,
splits, bootstrap protocol or thresholds were changed.

The cache does not record its historical weight hash, data hash or inference
settings. Its historical origin remains unproven even though all labels reproduce.
The original training files' byte identity is also not established merely by the
paths in `training_summary.json`.

## Controlled diagnostic: historical archived checkpoint

Output: `results/v0_trace_investigation/20261027T174038.177466Z/`.

Source archives, read without modifying them:

- `D:/Downloads/KYC_NLI_ALL_RESULTS.zip`
- `D:/Downloads/KYC_NLI_urgent_audit.zip`

The diagnostic fingerprints both archives, extracts their model to a new output
directory, saves its own source/configuration, and runs only the original
150-case `cross_script_name_mismatch` subset. It retains case-level comparisons
and checks its inputs again after inference. The primary run is not overwritten.

| Check | Finding |
| --- | --- |
| Archived weight SHA-256 | `469c1d7860f087b99ecd34f5f7dcc56218df66fd393729ebc8904d1a38b25144` |
| Weight comparison | Identical safetensors headers; different tensor payload hashes |
| Tokenizer files | Byte-identical to the local checkpoint |
| Architecture config | Same except saved Transformers version metadata |
| Training histories | Different, despite matching recorded training hyperparameters |
| Archived audit input pairs | All 150 exactly match the primary wrong-name subset |
| Archived regenerated-test hash | Matches the preserved local test hash |
| Local weights on those cases | 138 contradiction, 12 entailment |
| Archived weights on those cases | **8 contradiction, 142 entailment** |

The archived weights therefore reproduce the audit's 8/150 result under the same
length-192 inference pipeline and inputs. This establishes the checkpoint
difference behind that subset discrepancy. The historical full-test result is
macro-F1 **0.8441 [0.8273, 0.8619]**, as stored in the archive; **the archived
checkpoint's full 1,050-case score was not rerun here**.

The input join deliberately restricts matching to the wrong-name subset. Some v0
E/C cases have identical serialized inputs because of the known generator defect;
joining all cases by text alone can select the wrong instance ID. A regression
test now guards that join. The original v0 labels were retained in both runs.

## Reproduction and checks

From the repository environment:

```powershell
.\.venv\Scripts\python.exe -m kyc_nli.cli trace-v0 --config configs/experiments/v0_trace.yaml
.\.venv\Scripts\python.exe -m kyc_nli.cli investigate-v0 --config configs/experiments/v0_trace_investigation.yaml
```

Each command creates a new timestamped output directory. The investigation config
names the completed primary run above; to investigate a new trace, supply a new
config naming that trace. Preserve the backup and external archives referenced by
these configurations. Historical result files must not be replaced with new scores.

Final validation: **395 passed, 7 skipped**; Ruff passed for `src`, `tests` and the
new investigation script. The optional fine-tuning smoke test remains excluded by
the default test configuration. Skips cover the missing optional OCR rendering
dependencies and absent extracted Dakshina corpus. The raw JUnit and lint logs are
in the recovery directory as `pytest_final_after_diagnostic.xml` and
`ruff_final.txt`.

CLI/demo unit tests now use explicit baseline registries so an ignored user
checkpoint cannot silently turn them into neural benchmark runs. The OCR-specific
CLI test uses the same optional-dependency guards as the resolved calibration tests.
Real frozen-model inference is exercised by the two trace commands above.

The initial primary attempt stopped before inference because the sandbox blocked
Git's configured diff helper; it was rerun with approval. An initial investigation
stopped at its input-matching guard and was rerun after the subset-join correction.
Those incomplete output directories are retained, and are not result records.

## Limits on interpretation

These are synthetic **v0** results, with known label defects. They establish which
checkpoint reproduces which output; they do not validate corrected v1 data, real
documents, independent human annotation, or a guaranteed automation-risk budget.
No training, calibration, threshold selection, v1 generation, manuscript rewrite,
release or publication was performed.
