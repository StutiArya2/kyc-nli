# KYC-NLI ACL review draft

The current draft reports frozen synthetic v1 at moderate noise, two separately
identified recovered XLM-R checkpoints and the completed pilot record with
unresolved cases. It does not claim clean-to-heavy generalization, authenticated
training provenance, complete human validation or deployment-risk guarantees.

## Rebuild

```powershell
.\.venv\Scripts\python.exe -m kyc_nli.cli paper-v1 --config configs/experiments/paper_v1.yaml
.\.venv\Scripts\python.exe scripts/check_paper.py
.\.venv\Scripts\python.exe scripts/package_paper.py
```

`scripts/make_tables.py` and `scripts/make_figures.py` are compatibility entry
points to the same v1 builder. Both regenerate all current outputs. Do not edit
generated tables, figures or `numbers.tex`. The five result inputs are hash-pinned;
changing an input without explicitly updating its provenance fails the build.
Historical unreferenced figures/tables remain for recovery and are excluded from
the current source package. A full pre-revision backup is retained under results.

`main.tex` inputs generated prose macros as well as tables. Classification and
policy intervals come directly from completed runs; the paper build performs no
new inference and changes no frozen labels. Paper build inventories are written
to separate timestamped directories under `results/paper_v1_build/`.

## Compile

For an author-visible preprint, copy `authors.example.tex` to local `authors.tex`,
enter author-approved details, run `scripts/build_author_version.py` and compile
`author_version.tex`. Both author files remain local and ignored by Git. The
anonymous `main.tex` and review source ZIP exclude this author block.

Official `acl.sty` and `acl_natbib.bst` are included. Compile `main.tex` with
pdfLaTeX/BibTeX, Tectonic, or Overleaf. Review mode anonymizes the author block.
The anonymous source ZIP is generated under `output/paper/`; do not upload the
whole repository or private result directories as supplementary material.

The bibliography uses canonical ACL metadata and audited primary-source records.
See `docs/literature/paper-citation-audit-2026-10-28.md` for the distinction between
verified metadata, removed claims and the retired unresolved book-edition entry.
`scripts/prepare_paper_sources.py` can fetch primary metadata and official style
files again; this requires network access and may retrieve a newer style revision.

## Submission and release decisions

The owner selected ACL review format for now and planned code/synthetic-data
release subject to licensing review. No upload, submission or release is implied.
See `docs/paper-submission-status.md` for component licensing, private records and
author-controlled submission steps. The paper-only ZIP contains no reviewer
identities, attestations, external corpora or model weights.
