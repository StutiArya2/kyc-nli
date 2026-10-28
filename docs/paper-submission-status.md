# ACL review preparation — 28 October 2026

The owner selected ACL review format and a planned code/synthetic-data release,
subject to licensing review. This is a local review package, not a submission or
public release. The manuscript's contribution is a diagnostic v1 comparison;
historical clean-to-heavy generalization claims are explicitly excluded.

## Completed local verification

- Exported `output/pdf/kyc_nli_acl_review.pdf`: seven pages total, including
  references and appendix, within the eight-page content ceiling conservatively
  even if every page were counted. Main prose reaches Limitations on page four;
  a results figure floats to page five. This is not a venue acceptance check.
- Rendered and visually inspected all pages. Repaired sparse appendix float pages.
  No unresolved references, overfull boxes, reviewer names or local machine paths
  were detected in the final PDF. Ordinary underfull-spacing compiler warnings
  remain. The portable Tectonic compiler exported the final PDF after the built-in
  compiler timed out during resource download.
- `scripts/check_paper.py`: 15 cited primary-source entries, zero cited unverified
  entries, structural checks passed. The bibliography no longer contains the
  unresolved bootstrap-book edition as an active reference.
- Full tests passed with localhost access; paper provenance guards and lint passed.
- Created `output/paper/kyc_nli_acl_review_sources.zip` with only referenced sources,
  two current figures, generated tables/macros, official styles and deidentified
  aggregate evidence plus full artifact hashes. Archive CRC and text anonymity
  checks passed. No private reviewer records, weights or external corpora included.
- Frozen source-result hashes remain unchanged. The pre-revision paper is preserved
  at `results/paper_revision_backup_20261028T062214Z/`.

To repeat PDF QA, use a Python runtime with `pypdf` to run
`scripts/check_paper_pdf.py`. The local bundled document runtime provides it.

## Evidence and manuscript

- Replaced historical DistilBERT results with separately named local and archived
  XLM-R artifacts and documented recovered-training provenance limits.
- The common requested 5% automation-error target is selected on development data.
  Both local XLM-R and rules meet the test point estimate, with review 28.57% and
  93.05%, respectively; archived XLM-R misses it. Conditional uncertainty and the
  zero-error rule-bootstrap caveat are reported.
- Paper tables, figures and prose macros use `configs/experiments/paper_v1.yaml`.
  Five source records are SHA-256 pinned; no legacy cache fallback is permitted.
- Pilot reporting includes 57 candidate labels, three unresolved statuses and one
  human-generator disagreement. It does not claim full human validation.
- The citation audit distinguishes metadata verification from full standards
  verification, and documents the retired bootstrap-book edition uncertainty.

## Planned release inventory

| Component | Current evidence | Release disposition |
| --- | --- | --- |
| Repository code | Existing root MIT notice; includes named copyright holder | Retain attribution in any public code release; exclude this identifying notice from an anonymous paper-only source package |
| Synthetic v1 | Generated from embedded pools; no real identity inputs | Planned release; owner must approve final data license and provenance documentation before publishing |
| Embedded name pools / transliteration tables | Repository provenance claims and some explicitly unverified entries | Review provenance and applicable upstream terms; do not label all tables standards-verified |
| Dakshina | Distributor states CC BY-SA 4.0 | Keep separate; do not include downloaded corpus in this review package or relicense it under MIT |
| OCR fonts and tools | Third-party components with their own terms | Distribute acquisition instructions rather than bundling fonts or tools until their exact licenses are inventoried |
| Model checkpoints/tokenizer | Recovered XLM-R-derived artifacts | Exclude weights and tokenizer from the paper source package; inspect upstream terms and original run provenance before any planned model release |
| Human-review records | Personal declarations and self-reported competence | Keep raw attestations and names private. Only deidentified aggregate results belong in this package |
| ACL style files | Official files retained without modification | Preserve upstream notices; the paper's data/code licensing statement does not relicense the template |

This inventory identifies what must be checked; it is not a legal finding that
all planned redistribution is cleared. The owner authorized a conditional plan,
not publication. No blanket new license was applied to data or dependencies.

## Author-controlled steps before actual submission

1. Confirm authorship, affiliations and contribution statements outside the anonymous PDF.
2. Complete the final data/component licensing review and approve any public release.
3. Confirm the chosen ARR cycle, OpenReview profiles and current reviewer-service eligibility.
4. Complete applicable responsible-NLP and human-participant disclosures, including
   actual recruitment, compensation and consent information; these were not supplied
   by the CSV declarations and must not be invented.
5. Approve the final paper and submit it through the venue's system.

Primary guidance: [ARR call](https://aclrollingreview.org/cfp),
[ARR authors](https://aclrollingreview.org/authors),
[Dakshina distributor](https://github.com/google-research-datasets/dakshina),
[official ACL style](https://github.com/acl-org/acl-style-files).
