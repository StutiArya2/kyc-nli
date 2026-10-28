# Blinded v1 human-validation pilot — 28 October 2026

Status as of 28 October 2026: **pilot record finalized with unresolved cases and
limitations**. The preparation process below generated no human judgments. Returned
annotations and declarations have since been reconciled separately; the frozen
benchmark labels remain unchanged. This does not establish complete human
validation of the benchmark.

Final record: `results/v1_pilot_report/20261028T061540.433489Z/pilot_report.md`.
It contains 57 candidate human labels and three unresolved cases across the
60-case pilot. The VERMEY human-generator disagreement is retained. Initial A/B
agreement is conditional on only 29 definite pairs; neither initial annotator
used contradiction. Agreement on the selected follow-up cases must not replace
full-pilot reporting. Competence, independence and blinding are self-declared.

Regenerate a new, timestamped record with:

```powershell
.\.venv\Scripts\python.exe -m kyc_nli.cli pilot-report-v1 --config configs/experiments/v1_pilot_report.yaml
```

The report retains byte-preserved originals privately, input hashes, per-case
decision sources and per-language/per-class conditional agreement. Do not commit
the received personal declarations or generated records.

Batch: `results/v1_annotation/20261027T190125.316172Z/`.

Share **only** `annotator_A.zip` with annotator A and `annotator_B.zip` with
annotator B. Each ZIP contains its blank `sheet.csv`, instructions and the exact
existing label-definitions document. Keep the entire `ANALYST_ONLY` folder and
the full batch directory private from annotators. The answer key contains
generator labels, not human judgments.

The coordinator should recruit different people, record anonymized annotator IDs,
language/script competence, recruitment, dates, independence and blinding, and
retain their original returned files. Independent per-language panels can cover
the two A/B roles; each case must receive labels from two separate qualified
people. The coordinator must recombine language subsets into complete A/B sheets
before checking them. Do not ask annotators to guess scripts they cannot read.
Do not reveal the sampling quotas or generator key while labeling is underway.
No worksheets have been sent to anyone by this task.

## Pilot design

The analyst configuration is `configs/experiments/v1_annotation.yaml`, seed
20261028. Sampling uses the frozen v1 test data, hash
`10ef67fe3247bbc3b5aea36c41c06aa1ff3c5d0c8403a27f1ecf4bd15221984c`.
There are 60 cases: four per configured language and generator class, including
two wrong-name contradictions per language. All 60 identities are distinct.
The balanced pilot is not a prevalence-representative sample or a replacement
for the planned larger human-validation study.

Both sheets have the same opaque case IDs, with independently shuffled row order.
They show precisely the observed model-input serialization and claim. There are
no source instance IDs, generator labels, rationales, clean-value fields,
transliteration variant lists or model predictions in the worksheets. Ordinary
legible observed values remain visible. This is cooperative blinding, not an
adversarial cryptographic guarantee against reconstructing the sample from source.

The existing label definitions are copied unchanged. `uncertain` is an annotation
status, not a fourth NLI label. Annotators should explain unresolved ambiguity in
notes, including tensions in the written OCR/evidence definitions. No label
semantics are changed by the pack. Such issues require owner discussion and
independent adjudication, not private reinterpretation to match generator gold.

## Generate and check

```powershell
.\.venv\Scripts\python.exe -m kyc_nli.cli annotation-v1 --config configs/experiments/v1_annotation.yaml
.\.venv\Scripts\python.exe -m kyc_nli.cli check-annotation-v1 --batch results/v1_annotation/20261027T190125.316172Z --sheet-a <completed-A.csv> --sheet-b <completed-B.csv>
```

Generation creates a new timestamped batch. Checking creates a new report and
never overwrites the original sheets. Rows may be reordered, but the case IDs,
language, evidence, claims and column structure must be preserved. The validator
rejects duplicate/missing/extra IDs, altered evidence, unknown labels and invalid
confidence values. Blank labels and uncertainty without notes remain incomplete.
Reference worksheet/key/test hashes are checked before returned sheets are read.

Only when both sheets are complete can the checker calculate agreement. It
reports uncertainty counts, full-sample agreement including uncertainty status,
and explicitly conditional agreement/kappa on definite labels. A degenerate
single-label kappa is reported as undefined. File consistency does not establish
that independent humans supplied the labels: the report continues to mark
provenance unverified and adjudication pending, and human validation incomplete.

After both independent sheets are returned, review recruitment/blinding evidence,
audit agreement per language/class, and have a third qualified person adjudicate
disagreements and uncertainty. Do not copy generator labels into adjudication.
Those steps were pending when the package was prepared; their received records
and remaining limitations are documented in the final record linked above.

The included blank sheets were checked and correctly produced `INCOMPLETE`, with
no agreement metric. Tests cover blank packages, exclusion of private files from
ZIPs, reordered sheets, altered evidence, invalid labels, duplicate/missing cases,
and refusal to treat completed files as proof of independent annotation.
