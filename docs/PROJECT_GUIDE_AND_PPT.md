# KYC-NLI: Complete Project Documentation & Review Presentation Guide

**Project Title:** KYC-NLI: Document-Level Natural Language Inference for Identity Verification  
**Author:** Stuti Arya  
**Target Domain:** Multi-script Identity Document Field Verification (Indian Document Ecosystem)  
**Date:** September 2026  

---

# Table of Contents
1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [Task Formulation & Semantic Label Definitions](#2-task-formulation--semantic-label-definitions)
3. [Linguistic Scope: Five Scripts, One Document](#3-linguistic-scope-five-scripts-one-document)
4. [The Governing Finding (Phase-0 Discovery)](#4-the-governing-finding-phase-0-discovery)
5. [End-to-End System Architecture & Codebase Layout](#5-end-to-end-system-architecture--codebase-layout)
6. [Dataset Engineering & Generation Methodology](#6-dataset-engineering--generation-methodology)
7. [OCR Noise Modeling & Empirical Calibration (Milestone M1)](#7-ocr-noise-modeling--empirical-calibration-milestone-m1)
8. [Transliteration Engines & Dakshina Evaluation (Milestone M2)](#8-transliteration-engines--dakshina-evaluation-milestone-m2)
9. [Neural Cross-Encoder & The Data Leak Fix (Milestone M3a)](#9-neural-cross-encoder--the-data-leak-fix-milestone-m3a)
10. [Evaluation Protocol & Statistical Rigor](#10-evaluation-protocol--statistical-rigor)
11. [Project Milestones & Critical Path](#11-project-milestones--critical-path)
12. [Complete Slide-by-Slide PPT Content for Reviews](#12-complete-slide-by-slide-ppt-content-for-reviews)
13. [Reviewer Defense Q&A Cheat Sheet](#13-reviewer-defense-qa-cheat-sheet)

---

# 1. Executive Summary & Problem Statement

Identity verification ("Know Your Customer" / KYC) systems are tasked with validating whether personal identity claims submitted in an onboarding application match the physical document presented by the applicant (e.g., passport, national ID card).

### The Failure of Conventional Verification Systems
Virtually all existing KYC pipelines compare extracted OCR strings against application forms using **exact character matching** or heuristic **fuzzy string similarity** (such as Levenshtein distance). In multilingual societies like India, this approach fails predictably:

1. **Cross-Script In-Document Equivalence**: An Indian passport prints the holder's name in a regional Indic script in the Visual Inspection Zone (VIZ) (e.g., Tamil `சுப்ரமணியன்`) and in Latin script in the Machine Readable Zone (MRZ) (`SUBRAMANIYAN`). If an applicant submits `SUPRAMANIYAN`, string matching fails. Because Tamil script does not mark phonemic voicing (`ப` represents /p/ and /b/), both romanizations are valid transliterations of the exact same individual.
2. **Multi-Field Joint Temporal Impossibility**: An applicant presents a document with Date of Issue `1995-06-02`, Date of Expiry `2035-06-02`, and a template era of `2020-polycarbonate`. Every single field in isolation is syntactically well-formed, but a 40-year validity on a card design introduced in 2020 is physically impossible. Exact matching passes the document; inference detects the fraud.
3. **OCR Degradation & Evidence Insufficiency**: When OCR fails on a noisy camera capture (e.g., reading `???????` with confidence 0.05), string matching flags it as a mismatch, rejecting genuine citizens. The correct operational decision is routing the scan to human review because the document lacked readable evidence.

### The KYC-NLI Solution
KYC-NLI reformulates identity document verification as **three-way document-level Natural Language Inference (NLI)**:
$$\text{Premise (Document Observations)} + \text{Hypothesis (User Claim)} \longrightarrow \{\text{Entailment, Contradiction, Neutral}\}$$

---

# 2. Task Formulation & Semantic Label Definitions

```
                     ┌────────────────────────────────────────────────────────┐
                     │                 Document Premise                       │
                     │  VIZ (Native), MRZ (Latin TD3), Template, Check Digits │
                     └──────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │   Claim Hypothesis (Form) │
                                  └─────────────┬─────────────┘
                                                │
                        ┌───────────────────────┼───────────────────────┐
                        ▼                       ▼                       ▼
                 [ ENTAILMENT ]         [ CONTRADICTION ]          [ NEUTRAL ]
                 Evidence supports      Evidence refutes or       Premise lacks
                 the claim across       jointly contradicts       evidence to
                 scripts/formats        the claim                 decide
                        │                       │                       │
                        ▼                       ▼                       ▼
                  Accept User             Reject Document         Human Review
```

### The Central Commitment: What `NEUTRAL` Means
In KYC-NLI, **`NEUTRAL` is an objective property of the premise document, NOT model uncertainty or low confidence**:

* **`ENTAILMENT`**: The document evidence, correctly interpreted across scripts, zones, and formats, validates the hypothesis claim.
* **`CONTRADICTION`**: The document evidence directly refutes the claim, or the document's internal fields are jointly impossible (e.g., expiry preceding issue, checksum failure, issue date outside template manufacturing window).
* **`NEUTRAL`**: The premise **physically lacks the evidence** to decide the hypothesis (e.g., field is omitted from that document type, or was rendered completely illegible by OCR noise).

> **Crucial Distinction:** Contradiction requires positive evidence *against*. A blank or unreadable field is `NEUTRAL`, never `CONTRADICTION`. "Looks corrupted after OCR" is lack of evidence, not proof of mismatch.

---

# 3. Linguistic Scope: Five Scripts, One Document

KYC-NLI focuses on the **Indian document ecosystem**, spanning 5 official languages across 5 distinct writing scripts:

| Code | Language | Script | Normative Romanization | Linguistic Failure Mode Probed |
| :---: | :---: | :---: | :---: | :--- |
| **`en`** | English | Latin (`Latn`) | Full | **Control** — English zone against which other scripts are matched |
| **`hi`** | Hindi | Devanagari (`Deva`)| **None** | No single authority; holders romanize their own names differently |
| **`ta`** | Tamil | Tamil (`Taml`) | **None** | **Unvoiced script**: `க` is K/G, `ப` is P/B with equal legitimacy |
| **`bn`** | Bengali | Bengali (`Beng`) | **None** | Inherent vowel /o/ (BASU/BOSE), ya-phala overlaps with /dʒ/ |
| **`ur`** | Urdu | Perso-Arabic (`Arab`)| **Partial** | Short vowels unwritten: script gives skeleton (`SDYQY`), form has `SIDDIQUI` |

### In-Document Cross-Script Comparison
Unlike cross-border translation benchmarks, Indian identity cards display both English and a regional script on the **same physical card**. Therefore, cross-script reconciliation is an internal document validation problem, not a multi-country alignment problem.

---

# 4. The Governing Finding (Phase-0 Discovery)

To prevent building a neural model against a weak "strawman", we first built the strongest possible deterministic rule engine (`RuleBaseline`) equipped with:
* Complete ICAO Doc 9303 transliteration tables
* Multi-script romanization variant sets
* MRZ 7-3-1 check digit algorithms
* Cross-field temporal consistency rules
* RapidFuzz similarity thresholds with dedicated abstention bands

### The Phase-0 Benchmark Results:

| OCR Noise Preset | Exact Match Macro-F1 | **Rule Engine Macro-F1 (95% CI)** | Rule Engine Contrast Consistency | Rule Engine Review Load |
| :--- | :---: | :---: | :---: | :---: |
| **Clean** | 0.368 [0.341, 0.392] | **0.981 [0.971, 0.991]** | 0.956 | 28.6% |
| **Light** | 0.354 [0.326, 0.380] | **0.920 [0.900, 0.938]** | 0.815 | 36.2% |
| **Moderate** | 0.252 [0.231, 0.275] | **0.597 [0.552, 0.644]** | 0.333 | **63.4%** |
| **Heavy** | 0.219 [0.206, 0.235] | **0.361 [0.315, 0.404]** | 0.074 | **85.1%** |

### The Core Research Implication:
1. **Zero Headroom on Clean Data**: On clean scans, a deterministic rule engine reaches **0.981 Macro-F1**. There is no room for a neural NLI contribution on clean text.
2. **Rule Collapse Under Noise**: As optical noise corrupts text, strings fail strict parsing rules, causing the rule engine to over-abstain, driving manual review load from **28.6% up to 85.1%**.
3. **The Refined Research Claim**:
   > *"Under realistic OCR corruption, a learned document-level entailment model recovers decisions that a transliteration-aware rule engine must abstain on, reducing human review load at equal or better error rate."*

---

# 5. End-to-End System Architecture & Codebase Layout

```
kyc-nli/
├── configs/
│   └── languages.yaml             # Single source of truth for language specs
├── src/kyc_nli/
│   ├── schema.py                  # Core Pydantic data model (Instance, Observation, Label)
│   ├── languages.py               # Language configuration loader
│   ├── cli.py                     # CLI entry points (generate, compare, inspect, demo)
│   ├── demo.py                    # Presentation interactive walkthrough engine
│   ├── data/
│   │   ├── name_pools.py          # Embedded synthetic name pools (Zero PII)
│   │   ├── mrz.py                 # ICAO Doc 9303 TD3 MRZ generator & checksum validator
│   │   ├── generate.py            # Minimal-pair contrast group generator
│   │   ├── io.py                  # Dataset serialization & leak-free identity splitting
│   │   └── corpora.py             # External corpus interfaces (Dakshina)
│   ├── ocr/
│   │   ├── noise.py               # Script-aware OCR corruption models
│   │   ├── render.py              # HarfBuzz / FreeType text rendering & font shaper
│   │   ├── calibrate.py           # Empirical OCR error rate alignment pipeline
│   │   └── measured.py            # Frozen empirical Tesseract error rate tables
│   ├── translit/
│   │   ├── engine.py              # Multi-script Brahmic & Arabic transliteration engines
│   │   └── tables.py              # ICAO 9303 transliteration lookup tables
│   ├── baselines/
│   │   ├── exact.py               # Weak baseline: Exact string matching
│   │   └── rules.py               # Strong baseline: Transliteration + Rules + Fuzzy
│   ├── nli/
│   │   ├── dataset.py             # Compact serialization & ground-truth shielding
│   │   ├── model.py               # Cross-encoder PyTorch model wrapper
│   │   └── train.py               # Fine-tuning loop (CPU & GPU)
│   └── evaluation/
│       ├── metrics.py             # Macro-F1, Review Load, False Mismatch rates
│       ├── significance.py        # Group-level percentile bootstrap & paired tests
│       └── transliteration.py     # Transliteration recall evaluation against Dakshina
├── tests/                         # 91 automated test suites enforcing all invariants
├── scripts/                       # Reproducible experiment runners
└── docs/                          # Architecture Decision Records (ADRs) & research notes
```

---

# 6. Dataset Engineering & Generation Methodology

### Scale & Split Specifications
* **Default Benchmark**: 1,000 fabricated identities (200 per language) yielding **7,000 total instances**.
* **Partitioning**: 70% Train (4,900 instances / 700 identities), 15% Dev (1,050 instances / 150 identities), 15% Test (1,050 instances / 150 identities).
* **Class Balance**: 42.8% Entailment, 28.6% Contradiction, 28.6% Neutral.

### The 8 Probed Phenomena Across 3 Contrast Groups
Every identity generates 7 instances organized into 3 minimal-pair contrast groups:

1. **`-name` Contrast Group (3 instances)**:
   * `cross_script_name_icao` (**ENTAILMENT**): Hypothesis asserts the standard ICAO Latin romanization.
   * `cross_script_name_alt_romanisation` (**ENTAILMENT**): Hypothesis asserts an attested alternative romanization.
   * `cross_script_name_mismatch` (**CONTRADICTION**): Hypothesis asserts a different surname from the pool.
2. **`-time` Contrast Group (3 instances)**:
   * `temporal_valid` (**ENTAILMENT**): Hypothesis asserts the correct Expiry Date from a valid temporal chain.
   * `date_mismatch` (**CONTRADICTION**): Hypothesis asserts an incorrect expiry date.
   * `impossible_date_triple` (**CONTRADICTION**): Premise has an internally impossible date relationship (e.g., issue after expiry).
3. **`-evidence` Contrast Group (2 instances)**:
   * `field_absent` (**NEUTRAL**): Hypothesis asserts Place of Birth against an MRZ-only premise (MRZ does not carry POB).
   * `field_unreadable` (**NEUTRAL**): Premise field is destroyed by OCR corruption below the legibility threshold ($<0.35$).

---

# 7. OCR Noise Modeling & Empirical Calibration (Milestone M1)

Instead of relying on synthetic noise guesses, Milestone M1 measured actual Tesseract OCR behavior:
1. Pinned open-licensed **Noto fonts** were rendered with **HarfBuzz** complex text shaping and **FreeType** rasterization.
2. Text was degraded across 4 optical presets (`clean`, `light`, `moderate`, `heavy`).
3. Tesseract OCR extractions were aligned against source text via Levenshtein edit distance.

### Measured Character Error Rates (CER):

| Script / Language | Clean CER | Light CER | Moderate CER | Heavy CER | Characteristic Failure Mode |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Latin (`en`)** | 0.000 | 0.012 | 0.045 | 0.120 | Homoglyph confusions (`0/O`, `1/I`, `5/S`, `8/B`) |
| **Devanagari (`hi`)** | 0.000 | 0.028 | 0.089 | 0.245 | Matra vowel loss, conjunct splitting |
| **Tamil (`ta`)** | 0.000 | 0.035 | 0.110 | 0.280 | Pulli virama dot loss |
| **Bengali (`bn`)** | 0.000 | 0.032 | 0.098 | 0.260 | Hasant loss, ya-phala fusion |
| **Perso-Arabic (`ur`)**| 0.002 | 0.065 | **0.185** | **0.410** | Nuqta (diacritic dot) loss (`ب/ت/ث/ن`) |

---

# 8. Transliteration Engines & Dakshina Evaluation (Milestone M2)

To evaluate non-neural transliteration limits, we evaluated our transliteration engines against the **Google Dakshina Dataset** (~30k native/Latin word pairs per language written by native speakers):

```
Dakshina Multiplicity Analysis:
Urdu:      4.20 spellings/word · 97.6% words with >1 spelling · Rule engine recall: 0.150
Bengali:   3.67 spellings/word · 90.2% words with >1 spelling · Rule engine recall: 0.626
Tamil:     2.71 spellings/word · 74.6% words with >1 spelling · Rule engine recall: 0.672
Hindi:     1.79 spellings/word · 57.0% words with >1 spelling · Rule engine recall: 0.727
```

**Key Finding**: In Urdu and Bengali, single-string romanization lookup tables fail on the vast majority of words because native speakers naturally spell their names in multiple valid ways.

---

# 9. Neural Cross-Encoder & The Data Leak Fix (Milestone M3a)

### The Splitting Bug & Fix
* **The Bug**: `split_by_identity` initially partitioned on `contrast_group_id`. Because one identity produces 3 contrast groups, **94% of test identities leaked into training**, falsely inflating initial scores to 0.989.
* **The Fix**: Partitioning was rewritten to split strictly on `identity_id`. Overlap is now **0.0%**, enforced by unit tests.

### Model Architecture & Serialization
* **Model**: `distilbert-base-multilingual-cased` / XLM-RoBERTa cross-encoder.
* **Compact Serialization**:
  ```text
  Premise: sur:viz=शर्मा | sur:mrz=SHARMA | dob:mrz=850602 | doe:mrz=250601 | era:viz=2020-polycarbonate
  Hypothesis: surname is SHARMA
  ```
* Token budget compressed from median 347 tokens $\rightarrow$ **159 tokens** per instance.
* `clean_value` is strictly shielded from model input.

### Benchmark Results (Held-Out Test Identities under Moderate Noise):

| System | Macro-F1 (95% CI) | Contrast Consistency | False Mismatch (Rejection of Genuine Users) | Human Review Load |
| :--- | :---: | :---: | :---: | :---: |
| **Exact Match** | 0.268 [0.248, 0.287] | 0.000 | 89.3% | 0.0% |
| **Rule Baseline** | 0.601 [0.565, 0.640] | 0.307 | 9.3% | 63.4% |
| **Cross-Encoder (Ours)**| **0.972 [0.962, 0.982]**| **0.936** | **5.7%** | **28.6%** |

* **Paired Bootstrap Difference**: **+0.371 [0.329, 0.409]** ($p < 0.001$).
* **Review Load**: Halved from **63.4% $\rightarrow$ 28.6%**, while false rejections dropped from **9.3% $\rightarrow$ 5.7%**.

---

# 10. Evaluation Protocol & Statistical Rigor

1. **Macro-F1**: Evaluated across all 3 classes (unweighted by class size to ensure `NEUTRAL` performance is preserved).
2. **Contrast-Group Consistency**: Proportion of minimal-pair groups where **all instances** are classified correctly.
3. **Resampling Unit for Bootstrap CIs**: Resampling is performed over **contrast groups**, never individual instances. (Resampling instances ignores intra-group correlations and narrows confidence intervals by ~7%).
4. **Paired Significance Testing**: Paired bootstrap tests resample the exact same contrast groups for both systems to compute rigorous difference intervals.

---

# 11. Project Milestones & Critical Path

```
[M0] Schema, Synthetic Generator, Rule Engine, Eval Harness ──────── [COMPLETED]
[M1] Tesseract Empirical OCR Noise Calibration (HarfBuzz) ─────────── [COMPLETED]
[M2] Dakshina Corpus Transliteration Evaluation ───────────────────── [COMPLETED]
[M3a] Cross-Encoder CPU Training & Split-Leak Bug Fix ─────────────── [COMPLETED]
[M3b] XLM-RoBERTa / mDeBERTa GPU Run (Colab / Kaggle) ─────────────── [IN PROGRESS]
[M4] Selective Prediction Risk–Coverage Curves ────────────────────── [PLANNED]
[M5] Human-Annotated 500-Instance Validation Subset ────────────────── [PLANNED]
[M6] Multi-Dimensional Noise Ablations & Error Analysis ────────────── [PLANNED]
[M7] Final Paper & Thesis Write-Up ─────────────────────────────────── [PLANNED]
```

---

# 12. Complete Slide-by-Slide PPT Content for Reviews

### Slide 1: Title & Abstract
* **Title:** KYC-NLI: Document-Level Natural Language Inference for Identity Verification
* **Subtitle:** Multi-Script Indian Document Verification under Measured Optical Corruption
* **Presenter:** Stuti Arya
* **Key Numbers:** 0.972 Macro-F1 vs 0.601 Baseline · Review Load Halved (63% $\rightarrow$ 29%)

### Slide 2: Motivation & Incumbent Failures
* **Title:** The Failure of Exact Matching in Indian KYC
* **Points:**
  * Indian cards print names in English and regional scripts on the same document.
  * Exact matching fails on unvoiced consonants (Tamil `சுப்ரமணியன்` $\rightarrow$ `SUPRAMANIYAN`).
  * Exact matching passes impossible multi-field combinations (40-year validity on 2020 polycarbonate card).
  * Exact matching treats illegible scans as fraud instead of routing to review.

### Slide 3: Task Formulation & The Meaning of `NEUTRAL`
* **Title:** Three-Way Document-Level NLI Formulation
* **Points:**
  * `ENTAILMENT`: Document evidence validates the claim across zones and scripts.
  * `CONTRADICTION`: Evidence refutes the claim or fields are jointly impossible.
  * `NEUTRAL`: Premise physically lacks evidence to adjudicate the claim.
  * *Design Rule:* `NEUTRAL` is evidence insufficiency in the scan, not model uncertainty.

### Slide 4: Scope & Linguistic Analysis (5 Scripts)
* **Title:** Linguistic Scope & Transliteration Multiplicity
* **Points:**
  * 5 Scripts: Latin (`en`), Devanagari (`hi`), Tamil (`ta`), Bengali (`bn`), Perso-Arabic (`ur`).
  * Dakshina dataset shows Urdu has 4.20 spellings/word (97.6% multi-spelling rate).
  * Tamil lacks voicing distinctions; static lookup tables are mathematically incomplete.

### Slide 5: The Strong Non-Neural Baseline (Rule Engine)
* **Title:** Methodological Discipline: Building the Baseline First
* **Points:**
  * Rule engine equipped with ICAO 9303 tables, variant sets, MRZ check digits, temporal logic, and RapidFuzz thresholds.
  * Clean scan score: **0.981 Macro-F1**.
  * Finding: There is zero headroom for neural NLI on clean text.

### Slide 6: The Pivotal Finding & Revised Research Claim
* **Title:** The Finding That Reframed the Project
* **Points:**
  * Rule engine collapses under OCR corruption (0.981 $\rightarrow$ 0.597 Macro-F1).
  * Review load spikes to 63.4% as corrupted strings fail regex/parsing rules.
  * **Revised Claim:** Learned NLI recovers decisions under OCR corruption, slashing review load.

### Slide 7: Dataset Design & Minimal-Pair Contrast Groups
* **Title:** 7,000-Instance Multi-Script Benchmark (Zero PII)
* **Points:**
  * 1,000 fabricated identities $\rightarrow$ 3,000 contrast groups $\rightarrow$ 7,000 instances.
  * 3 Contrast Groups per identity (`-name`, `-time`, `-evidence`) probing 8 specific phenomena.
  * Group-level metric: `contrast_consistency` tests whether whole triples are predicted correctly.

### Slide 8: Empirical OCR Calibration via Tesseract (M1)
* **Title:** Calibrating Physical Document Degradation
* **Points:**
  * Text rendered with HarfBuzz/FreeType across 5 Noto fonts and degraded across 4 presets.
  * Tesseract OCR extractions aligned to measure empirical substitution, deletion, and insertion rates.
  * Synthetic hand-built deletion rates were 10–17× too low; empirical rates now frozen in `kyc_nli.ocr.measured`.

### Slide 9: Data Integrity & The Split-Leak Fix (M3a)
* **Title:** Leak-Free Partitioning & Serialization
* **Points:**
  * Fixed earlier split bug that leaked 94% of test identities by splitting strictly on `identity_id`. Overlap is 0.0%.
  * Compact serialization compressed inputs from 347 to 159 tokens.
  * Model strictly shielded from `clean_value` and rule engine lookup tables.

### Slide 10: Model Results & Review Load Reduction
* **Title:** Benchmark Results: Cross-Encoder vs. Rule Engine
* **Points:**
  * Cross-Encoder reaches **0.972 Macro-F1** vs **0.601 Baseline** (+0.371 paired bootstrap gain, $p < 0.001$).
  * Whole-group consistency reaches **93.6%** vs **30.7%**.
  * Human review load halved from **63.4% $\rightarrow$ 28.6%**.
  * False customer rejections reduced from **9.3% $\rightarrow$ 5.7%**.

### Slide 11: Roadmap, Status & Risk Register
* **Title:** Milestones & Critical Path
* **Points:**
  * Completed: M0 (Schema/Harness), M1 (OCR Calibration), M2 (Dakshina Eval), M3a (Cross-Encoder CPU).
  * Next: M3b (GPU Run on Colab), M4 (Selective Prediction Risk-Coverage Curves), M5 (Human Validation Subset).
  * Acknowledged Risk: Synthetically rendered text serves as a lower bound on physical wear.

### Slide 12: Live Demonstration & Conclusion
* **Title:** Reproducibility & Live System
* **Points:**
  * Clean checkout to running scoreboard in $<1$ minute via `.\demo.ps1`.
  * Complete test coverage (91 tests passing, lint clean).
  * All metrics reproducible via `kyc-nli compare`.

---

# 13. Reviewer Defense Q&A Cheat Sheet

### Q1: *"Why use Natural Language Inference instead of character-level edit distance?"*
> **Answer:** *"Edit distance operates strictly on surface string syntax. It cannot handle unvoiced phonemic equivalence in Tamil (where `க` legitimately represents /k/ and /g/), cannot verify multi-field joint constraints (e.g., an issue date after an expiry date), and cannot recognize when OCR corruption has destroyed evidence—requiring an evidence-insufficient `NEUTRAL` routing rather than a fraud rejection."*

### Q2: *"Why is synthetic data acceptable? Why not evaluate on real Indian passports?"*
> **Answer:** *"Real identity cards contain sensitive PII that cannot be legally collected or distributed. We address synthetic bias through three empirical anchors: (1) OCR noise is empirically calibrated against real Tesseract extractions across 5 scripts (M1), (2) transliteration multiplicity is measured against Dakshina's 30k human romanizations (M2), and (3) Milestone M5 will benchmark against a 500-instance human-annotated validation subset."*

### Q3: *"Your model achieves 1.000 F1 on the NEUTRAL class. Is this an artifact?"*
> **Answer:** *"Yes, and we state this transparently. In our generator, NEUTRAL instances are constructed by removing evidence or marking unreadable fields (`?`). Detecting missing fields in structured serialization is straightforward for both rule engines and neural models. Milestone M5's human-annotated split will evaluate real-world edge cases with subtle evidence ambiguity."*

### Q4: *"How did you verify there is no data leakage between training and testing?"*
> **Answer:** *"We partition data strictly at the `identity_id` level. Because one identity produces three contrast groups (`-name`, `-time`, `-evidence`), all groups from an identity remain within the same split. A unit test (`test_splits_do_not_share_identities`) enforces 0.0% identity overlap."*
