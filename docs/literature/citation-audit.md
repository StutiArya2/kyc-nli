# Citation audit — Review 1 deck

**Date:** 2026-09-06 · **Scope:** all 12 papers in `docs/proposal/NLP review 1.pptx`
· **Method:** each entry located via web search and checked against the published
record (ACL Anthology, arXiv, ACM DL, Springer, ScienceDirect).

Every claim below is grounded in a source retrieved during the audit. Where a
stated figure could not be confirmed, the row says **CANNOT VERIFY** rather than
guessing — an unverified number is a submission risk whether or not it is real.

A corrected deck is at `docs/proposal/NLP review 1 (corrected).pptx`. Twenty-one
edits were applied; see [What was changed](#what-was-changed-in-the-corrected-deck).

## Summary

| # | Paper | Verdict |
| --- | --- | --- |
| 1 | FakeIDet2 | **WRONG METADATA** — wrong year, four wrong figures |
| 2 | Voerman et al. | Verified; title subtitle and author list corrected |
| 3 | Toprak & Turan | Exists; **figures CANNOT VERIFY** |
| 4 | Adam & Kliegr | **WRONG VENUE AND YEAR** — it is a journal paper, not a preprint |
| 5 | SGER | Verified exactly |
| 6 | CDCL-NLI | Verified; cite the full title |
| 7 | Entailed Between the Lines | Verified; 63rd meeting, not 64th |
| 8 | MultiOCR-QA | Verified; 50K pairs, not 50–60K |
| 9 | Marchesin et al. | **MISCHARACTERISED** — it is an editorial, not a survey |
| 10 | Tsaneva et al. | Metadata verified; description materially incomplete |
| 11 | Syauqi & Wibawa | Verified exactly |
| 12 | González & Tapia | **WRONG METHOD DESCRIPTION**; dataset size is public |

Four papers needed substantive correction. Two were cited with a wrong year.

---

## 1. FakeIDet2 — wrong year and four wrong figures

The single worst entry. A reviewer who checks one of these numbers finds all of them.

| Field | Deck said | Source says |
| --- | --- | --- |
| Year | 2026 | **2025** |
| Composite-attack EER | 1.69% vs 54.25% baseline | **2.09% vs 54.08%** |
| Cross-DB EER, DLC-2021 | 9.56% | **8.90%** |
| Cross-DB EER, KID34K | 14.47% | **13.84%** |
| GAN-generated fakes EER | 37.51% | **39.41%** (Benalcazar et al. synthetic DB) |

Correct citation:

> Muñoz-Haro, J., Tolosana, R., Fierrez, J., Vera-Rodriguez, R., & Morales, A.
> (2025). Privacy-aware detection of fake identity documents: methodology,
> benchmark, and improved algorithms (FakeIDet2). *Information Fusion*.
> arXiv:2508.11716.

The published title puts the acronym **last**; the deck had it first.

**Confirmed correct, keep as-is:** 922,057 patches from 2,000 ID images, 47
subjects; DINOv2 (ViT-S/14) backbone with AdaFace loss.

**Still unverified:** the "4.05% → 16.54% as anonymization increases" figure. The
corrected deck now states the trend without the specific numbers. Confirm from the
full text or drop it.

- <https://arxiv.org/abs/2508.11716> · <https://www.sciencedirect.com/science/article/pii/S1566253525010310>

---

## 2. Voerman et al. — verified, citation tightened

> Voerman, J., Al-Ghadi, M., Sidere, N., Coustaty, M., & Lessard, O. (2025).
> Optimizing identity documents classification in online systems: **A comparative
> analysis**. *IJDAR*. DOI 10.1007/s10032-025-00555-5. Published 8 Sept 2025.

Year and venue correct. Two fixes: the deck omitted the subtitle, and listed
Coustaty third when he is fourth (Sidere was missing).

**CANNOT VERIFY:** 96.42% / 56.52% ProtoNet accuracies, 0.07s/doc, 17s/doc.
Plausible and unchallenged, but not confirmed from the accessible record.

- <https://link.springer.com/article/10.1007/s10032-025-00555-5>

---

## 3. Toprak & Turan — figures CANNOT VERIFY

> Toprak, T., & Turan, M. (2023). Enhanced Named Entity Recognition algorithm for
> financial document verification. *The Journal of Supercomputing*, 79,
> 19431–19451. DOI 10.1007/s11227-023-05371-4.

Paper, venue, year and page range confirmed. **But** the deck's headline figures —
88.80% verification accuracy, 81.80% without regex, 89.81% Azure baseline, ~2.4s
processing — could not be confirmed, and one source describes a **94.2%** accuracy
figure for this work.

**Action before Review 2:** get the PDF and check those four numbers. Correct them
or mark CANNOT VERIFY. This is the highest-priority remaining verification task.

- <https://link.springer.com/article/10.1007/s11227-023-05371-4>

---

## 4. Adam & Kliegr — wrong venue and year, in your favour

The deck listed this as "2024, arXiv / KG venue". It is a **peer-reviewed journal
paper** in a strong venue:

> Adam, D., & Kliegr, T. (2025). Traceable LLM-based validation of statements in
> knowledge graphs. *Information Processing & Management*. arXiv:2409.07507.

Correcting this **strengthens** the review — a preprint became an IPM paper.

**Confirmed:** 88% precision, 44% recall. Note the method compares triples against
chunks retrieved by web search or Wikipedia, and deliberately avoids the LLM's own
internal knowledge — worth stating, since it is the design choice that makes the
result traceable.

- <https://www.sciencedirect.com/science/article/abs/pii/S0306457325000706> · arXiv:2409.07507

---

## 5. SGER — verified exactly

> Chourasia, S., Kapoor, H., & Patil, N. (2026). Structure-Guided Entity
> Resolution: Fine-Tuning LLMs for Robust Name Matching in Complex Linguistic
> Contexts. *ACL 2026* (**Industry Track**). arXiv:2605.23597.

All figures confirmed: 99.02% accuracy, F1 0.994, 50,000 held-out pairs, Dream11,
250M+ users, two-phase curriculum fine-tuning.

**Add:** it is the Industry Track, and the arXiv version is the author preprint
pending the final proceedings version. State both.

**This is the closest prior work.** SGER is Indian KYC name matching — the same
domain as our five-language set (decision 0005). Its stated limitations (binary
label space, no "insufficient evidence" judgement, personal names only) are
precisely what this project extends. Position against it directly.

- <https://arxiv.org/abs/2605.23597>

---

## 6. CDCL-NLI — verified

> Yuan, M., Wang, W., Wang, Z., Huang, Y., Wei, K., Li, F., Teng, C., & Ji, D.
> (2025). Cross-Document Cross-Lingual NLI via RST-Enhanced Graph Fusion and
> Interpretability Prediction. *EMNLP 2025*, Suzhou.

25,410 instances, 26 languages, RST + graph fusion, lexical-chain alignment,
EDU-level interpretability: all confirmed. Cite the full title, not the short form.

- <https://aclanthology.org/2025.emnlp-main.1611/> · arXiv:2504.12324

---

## 7. Entailed Between the Lines — verified

> Havaldar, S., Alvari, H., Palowitch, J., Hosseini, M. J., Buthpitiya, S., &
> Fabrikant, A. (2025). Entailed Between the Lines: Incorporating Implication into
> NLI. *ACL 2025* (Vol. 1: Long Papers), Vienna.

Author list matches exactly. INLI confirmed, released by google-deepmind.

**Two corrections:** it is the **63rd** Annual Meeting (2026's SGER is the 64th —
do not copy that number here). INLI is built from **Ludwig, Circa, NormBank and
SocialChem**, which is more precise than "existing implicature-frame datasets".

- <https://aclanthology.org/2025.acl-long.1552/> · arXiv:2501.07719

---

## 8. MultiOCR-QA — verified, one figure loosened

> Piryani, B., Mozafari, J., Abdallah, A., Doucet, A., & Jatowt, A. (2025).
> Evaluating Robustness of LLMs in Question Answering on Multilingual Noisy OCR
> Data. *CIKM '25* (34th ACM CIKM). DOI 10.1145/3746252.3761295.

**Correction:** the deck says "50K–60K QA pairs". The published figure is **50K**.
Drop the range — a widened range reads as not having checked.

The arXiv v1 carries a different title ("MultiOCR-QA: Dataset for…"); cite the
CIKM version.

- <https://dl.acm.org/doi/10.1145/3746252.3761295> · arXiv:2502.16781

---

## 9. Marchesin et al. — it is an editorial, not a survey

> Marchesin, S., Silvello, G., & Alonso, O. (2025). Large Language Models and Data
> Quality for Knowledge Graphs. *Information Processing & Management*, 62(6).
> DOI 10.1016/j.ipm.2025.104281.

The deck described this as a "Survey / position analysis" that "systematically
categorizes LLM roles across KG data-quality pipelines and compares reported
performance and failure patterns across studies".

It is a **guest editorial introducing an IPM special issue**. The three named
authors are the special issue's guest editors. There is no stated search protocol,
no systematic categorisation, and no cross-study synthesis of its own.

**Why this matters:** the deck presents 2–3 surveys against 9–10 primary papers.
One of those "surveys" is a 3–5 page editorial. Citing it as a systematic review
overstates the evidence base, and a reviewer who opens it will see that
immediately. Either cite it honestly as a pointer into the special issue, or
replace it with one of the issue's actual contributed papers.

- <https://www.sciencedirect.com/science/article/pii/S0306457325002225>

---

## 10. Tsaneva et al. — metadata right, description materially incomplete

> Tsaneva, S., Dessì, D., Osborne, F., & Sabou, M. (2025). Knowledge graph
> validation by integrating LLMs and human-in-the-loop. *Information Processing &
> Management*, 62(5), 104145. DOI 10.1016/j.ipm.2025.104145.

Metadata correct. The description is not.

| Deck said | Source says |
| --- | --- |
| "LLM proposes validity judgments; human reviewers verify/correct a sampled subset" | **Nine workflows** combining GPT-4 / Claude screening with human-in-the-loop checks |
| "Scholarly/domain KG triples (full composition behind paywall)" | A **3,600-triple science knowledge graph** — the size is public |
| *(no Evaluation Metrics row at all)* | LLMs are **weak standalone validators**; combined with other automated methods they reach **human-level quality** |

**That missing finding is the most useful sentence in the paper for this project.**
"LLMs alone are weak; LLM + another automated validator reaches human level" is
direct support for a hybrid design, and for routing only the hard cases to a human.
It belongs in the deck and in the related-work section.

- <https://www.sciencedirect.com/science/article/pii/S030645732500086X>

---

## 11. Syauqi & Wibawa — verified exactly

> Syauqi, A., & Wibawa, A. P. (2025). Advances in machine transliteration methods,
> limitations, challenges, applications and future directions. *Natural Language
> Processing Journal*, June 2025.

73 studies via PRISMA: confirmed. Additional detail worth adding — **37** studies
cover transliteration methods and **32** cover downstream NLP applications.

- <https://www.sciencedirect.com/science/article/pii/S2949719125000342>

---

## 12. González & Tapia — wrong method description

> González, S., & Tapia, J. E. (2025). Forged presentation attack detection for ID
> cards on remote verification systems. *Pattern Recognition*, 162, 111352.
> DOI 10.1016/j.patcog.2025.111352.

Metadata correct. The method and dataset descriptions were both wrong.

| Field | Deck said | Source says |
| --- | --- | --- |
| Method | "CNN-based, **modality-decoupled** architecture — separate detection branches per attack type" | **Hybrid two-stage multiclass network** on **MobileNetV2**; a **serial** two-stage architecture trained from scratch |
| Dataset | "Private Chilean DB (composition unknown)" | **190K real-case Chilean ID card images**, plus new fakes from synthetic and PVC cards |
| Evaluation Metrics | *(row absent)* | Among the first end-to-end PAD evaluations on ID cards |

A wrong architecture is worse than a wrong number: it means the "Advantages" and
"Research Gap" rows were reasoning about a method the paper does not use.

- <https://www.sciencedirect.com/science/article/abs/pii/S0031320325000123>

---

## What was changed in the corrected deck

`docs/proposal/NLP review 1 (corrected).pptx` — 21 edits, applied by
`scripts/fix_review1_citations.py`, schema-validated against the original.

| Slide | Change |
| --- | --- |
| 4 | Year 2026 → 2025; four EER figures corrected; Paper Title → published title |
| 5 | Author list → Voerman, Al-Ghadi, Sidere, Coustaty, Lessard |
| 7 | Year 2024 → 2025; venue "arXiv / KG venue" → Information Processing & Management |
| 12 | Method, Evaluation Metrics, Advantages, Disadvantages → described as an editorial |
| 15 | Method → MobileNetV2 serial two-stage; dataset → 190K images; advantages rewritten |
| 16 | Comparative table: both years, method and dataset cells for papers 9 and 12 |

The slide *heading* on slide 4 was deliberately left short — the full published
title is long, and the heading is a heading, not the citation. The **Paper Title
row** carries the exact published title.

### Still to do by hand

**Add the two missing Evaluation Metrics rows** (slides 13 and 15). Papers 10 and
12 have no Evaluation Metrics row while every other paper does, and a reviewer
reads a missing row as the author not having read the paper. I did not add these
programmatically: both tables already fill the slide, and without the ability to
render the deck on this machine I could not confirm a new row would not overflow.
It is a 30-second edit in PowerPoint where you can see the layout.

Suggested content:

- **Slide 13 (Tsaneva):** "Nine LLM + human-in-the-loop workflows evaluated on a
  3,600-triple science KG. LLMs weak as standalone validators; combined with other
  automated validators they reach human-level quality."
- **Slide 15 (González & Tapia):** "Among the first end-to-end PAD evaluations on
  ID cards; evaluated on 190K real-case Chilean ID card images."

---

## Structural problems, independent of correctness

From `docs/review-prompts.md`, Prompt 2. These hold regardless of the citations.

**Unearned claims in the comparative table.** The "How My Idea Improves" column
asserts improvements over methods that have not been run. Rewrite each cell as a
hypothesis: "NLI replaces string equality with entailment" becomes "we hypothesise
that entailment recovers matches string equality misses, and test this against a
rule baseline". After the Phase-0 finding this matters more, not less — we now know
a rule engine reaches 0.980 on clean input, so several of those cells are simply
not true as written.

**Strawman risk in the "Research Gap" column.** Criticising a computer-vision
forgery-detection paper (Papers 1, 12) for having "no semantic text layer" judges
it against a task it never claimed to address. Rewrite as a scope statement:
"vision-only by design; complementary to, not competing with, a text-layer check".

**Venue concentration.** Papers 4, 9 and 10 are all *Information Processing &
Management* — and one of the three is an editorial. Three of twelve from one
journal is thin sourcing for a related-work section.

**Coverage gaps.** Absent, and needed for the revised claim:

| Area | Why it now matters |
| --- | --- |
| Selective prediction / abstention / calibration | The literature behind the NEUTRAL → human-review mechanism. The revised claim *is* a selective-prediction claim. Biggest single gap. |
| Dakshina; NEWS transliteration shared tasks | The data source for four of five languages. Must be cited and positioned. |
| MIDV-500 / 2019 / 2020, MIDV-Holo, DocXPand-25k | The benchmark must be positioned against existing identity-document datasets. |
| DocNLI, TabFact, INFOTABS, FEVEROUS | NLI over structured data — the nearest formulation to ours. |
| Post-OCR correction (ICDAR competitions) | The alternative fix for the noise problem, so a baseline a reviewer will ask for. |

---

## How to reproduce this audit

Run Prompt 2 in `docs/review-prompts.md` in a fresh session with web search on.

Prompt 1 (novelty audit) must be run **in a session that had no hand in building
this**, per the note at the top of that file: a model that helped shape the idea
will defend it. This audit was produced by a session that did help build the
repository, which is acceptable for factual citation verification — every claim
here is checkable against a linked source — and is *not* acceptable for a novelty
judgement.
