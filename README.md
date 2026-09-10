# KYC-NLI

Document-level natural language inference for identity-document field verification, across five scripts.

Identity verification ("KYC") systems check whether the name and dates on a
scanned passport match what someone typed into a form. Almost all of them do
this with string comparison, which fails in a predictable way: an Indian
passport prints `शर्मा` in its regional zone and `SHARMA` in its English zone,
two strings that share zero characters and describe the same person. This
project reformulates that check as three-way entailment — does the document
**support**, **refute**, or **not say** — so that cross-script equivalence,
format variation and OCR corruption are handled by inference instead of by
exact matching.

> **Read this before using any number from this repo.** The Phase-0 pilot found
> that a *deterministic rule engine* reaches 0.981 macro-F1 on noise-free input.
> The defensible contribution is therefore in the OCR-noise regime, not in clean
> cross-script matching. See [Phase-0 finding](#the-phase-0-finding) and
> [`docs/plan.md`](docs/plan.md).

---

## The problem, in three examples

These are the motivating cases. The last column is what a correct system does.

| Case | What the document shows | What the form says | Exact match returns | Correct answer |
| --- | --- | --- | --- | --- |
| **Cross-script name** | Regional zone `சுப்ரமணியன்` (Tamil), English zone `SUBRAMANIYAN` | `SUPRAMANIYAN` | ✗ mismatch → genuine holder rejected | **ENTAILMENT** — Tamil script does not mark voicing, so ப is P or B with equal legitimacy; both spellings are correct romanisations of one name |
| **Jointly impossible dates** | Issue `1995-06-02`, Expiry `2035-06-02`, Template `2020-polycarbonate` | `expires 2035-06-02` | ✓ match → forgery passes | **CONTRADICTION** — every field is individually valid, but a 40-year validity on a template introduced in 2020 cannot exist |
| **Cascading OCR failure** | VIZ surname reads `???????` (conf. 0.05); no other zone carries it | `SHARMA` | ✗ mismatch → treated as fraud | **NEUTRAL** — the document has the answer, this scan does not; route to a human |

The three answers are three different labels. That is the argument for a
three-way formulation over a binary match/no-match one.

## Labels

Full definitions with worked examples: [`docs/label-definitions.md`](docs/label-definitions.md).

- **ENTAILMENT** — the document's evidence, correctly interpreted (across scripts,
  formats and zones), supports the claim.
- **CONTRADICTION** — the evidence refutes it, either directly or by joint
  impossibility across fields.
- **NEUTRAL** — **the premise lacks the evidence to decide.** This is a property
  of the document, not of the model.

That last definition is the project's central commitment. If NEUTRAL meant "the
model isn't sure", the three-way formulation would collapse into binary
classification plus a confidence threshold, which is a solved problem and not a
contribution. See [decision 0002](docs/decisions/0002-neutral-is-evidence-insufficiency.md).

**The boundary everyone gets wrong:** contradiction requires positive evidence
*against*. A blank field is NEUTRAL. A field reading something else is
CONTRADICTION. A field too corrupted to read is NEUTRAL — "looks different after
corruption" is not evidence.

## Architecture

```mermaid
flowchart TD
    subgraph capture [Document capture]
        IMG[Document image] --> OCR[OCR engine<br/>off-the-shelf]
        OCR --> VIZ[VIZ observations<br/>native script]
        OCR --> MRZ[MRZ observations<br/>Latin, ICAO 9303]
    end

    FORM[Application form claim] --> HYP[Hypothesis]

    VIZ --> PREM[Premise:<br/>multi-zone, multi-script<br/>field observations]
    MRZ --> PREM

    PREM --> TR[Transliteration<br/>ICAO tables, variant sets]
    PREM --> CD[MRZ check digits]
    PREM --> TC[Cross-field<br/>temporal consistency]

    TR --> NLI[Document-level NLI<br/>NOT YET IMPLEMENTED]
    CD --> NLI
    TC --> NLI
    HYP --> NLI

    NLI --> DEC{Decision}
    DEC -->|ENTAILMENT| PASS[Accept<br/>+ supporting fields]
    DEC -->|CONTRADICTION| FAIL[Reject<br/>+ conflicting fields]
    DEC -->|NEUTRAL| HUM[Human review<br/>+ what evidence is missing]

    style NLI stroke-dasharray: 5 5
```

Dashed = not yet built. Everything else runs today, on CPU.

## The Phase-0 finding

The first thing built was not the model — it was the baseline the model has to
beat: a transliteration-aware rule engine with the ICAO Doc 9303 tables, MRZ
check digits, date-format normalisation, cross-field temporal rules and tuned
fuzzy thresholds. Then the benchmark was generated at four OCR-noise levels.

| OCR noise | `exact_match` macro-F1 (95% CI) | **`rule_engine` macro-F1 (95% CI)** | contrast consistency | false-mismatch |
| --- | --- | --- | --- | --- |
| clean | 0.368 [0.341, 0.392] | **0.981** [0.971, 0.991] | 0.956 | 0.000 |
| light | 0.354 [0.326, 0.380] | **0.920** [0.900, 0.938] | 0.815 | 0.075 |
| moderate | 0.252 [0.231, 0.275] | **0.597** [0.552, 0.644] | 0.333 | 0.087 |
| heavy | 0.219 [0.206, 0.235] | **0.361** [0.315, 0.404] | 0.074 | 0.029 |

*(5 languages, 120 identities each, seed 20260906. **Noise rates are measured**
from Tesseract on shaped renders — milestone M1, see
[docs/m1-ocr-calibration-findings.md](docs/m1-ocr-calibration-findings.md) —
and are a lower bound on real-document error. Intervals are percentile
bootstrap, 1000 resamples over **contrast groups** — not instances: members of a
group share a premise, so resampling instances treats correlated observations as
independent and yields intervals ~7% too narrow. Every pairwise difference is
significant under a paired bootstrap. Reproduce with
`scripts/run_noise_ablation.ps1`.)*

**A rule engine gets 0.981 on clean input.** There is no room for a neural
contribution there. It degrades steeply under corruption — human review load
rises from 29% to **85%** between clean and heavy, with the engine abstaining on
79% of cases the document actually decides — so that is where the
contribution has to live. The revised claim is about **selective prediction
under input corruption**, and it is falsifiable by the risk–coverage curve.

Caveat: the noise model is hand-built from documented per-script OCR failure
modes, not calibrated against a real engine. The direction of this finding is
robust; the magnitude is not yet trustworthy. Calibration is milestone M1 and
the project's single point of failure —
[decision 0004](docs/decisions/0004-ocr-noise-is-simulated.md).

## Languages

Five scripts from the **Indian document context** — Latin, Devanagari, Tamil,
Bengali and Perso-Arabic. All five are official Indian languages, and all five
appear on documents issued by one state, so the cross-script comparison is
*in-document* rather than across two countries' records: an Indian identity
document prints the holder's name in English and a regional script on the same
card. [Decision 0005](docs/decisions/0005-indian-language-set.md) has the full
rationale.

| code | script | romanisation | normative | probes |
| --- | --- | --- | --- | --- |
| `en` | Latin | identity | full | Control — the English zone the other four are compared *against*, not an artificial baseline |
| `hi` | Devanagari | ITRANS / IAST / ad-hoc | **none** | The same holder romanises their own name differently on different forms |
| `ta` | Tamil | none | **none** | **The script does not mark voicing at all** — க is K or G, ப is P or B, equally correctly. A lookup table cannot be right even in principle |
| `bn` | Bengali | none | **none** | Inherent vowel nearer /o/ (BASU/BOSE), no /v/, ya-phala shares a letter with /dʒ/ (BANDYOPADHYAY/BANDOPADHYAY) |
| `ur` | Perso-Arabic | ICAO 9303 Arabic, extended | partial | Short vowels unwritten: the script gives a skeleton (SDYQY), a lexicon supplies the rest (SIDDIQUI) |

Four of five are non-normative or partial — the set is concentrated on the regime
where the project's claim could be true.

**How one-to-many is romanisation, really?** Measured on Dakshina (~30k words per
language, romanisations written by native speakers):

| | Hindi | Tamil | Bengali | Urdu |
| --- | --- | --- | --- | --- |
| spellings per word | 1.79 | 2.71 | 3.67 | **4.20** |
| words with >1 spelling | 57.0% | 74.6% | 90.2% | **97.6%** |
| our engine finds the most-attested spelling | 0.727 | 0.672 | 0.626 | **0.150** |

A system assuming one correct Latin form is wrong on almost every Urdu word
before it starts. Full analysis, including two real bugs this surfaced, in
[docs/m2-dakshina-findings.md](docs/m2-dakshina-findings.md).

Nothing hardcodes a language. Adding a sixth is a block in
`configs/languages.yaml` plus a name pool. Russian and Chinese are retained in
code as contrast conditions — a normative-table language and a false-*match*
language — so "does this generalise beyond India?" is a config edit.

## Installation

From a clean machine. No GPU required for anything in this repo.

```bash
git clone <your-remote-url> kyc-nli
cd kyc-nli
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -e ".[dev]"
```

On macOS/Linux use `.venv/bin/python` instead. Python 3.10+ (developed on 3.13).

Optional extras: `.[nli]` for the Phase-1 GPU work (install on Colab, not
locally), `.[ocr]` for the OCR calibration harness (Pillow + HarfBuzz +
FreeType), `.[translit]` for pypinyin and indic-transliteration.

The OCR calibration also needs **Tesseract** with the `eng`, `hin`, `tam`, `ben`
and `urd` language packs, installed as a system package.

## Quickstart

**To see what this is, in one minute:**

```powershell
.\demo.ps1
```

A live walkthrough: the cross-script problem on a real document, the three
labels with worked examples, how one-to-many romanisation actually is, the
baselines scored on the spot, and the finding that reframed the project. No
network, no GPU, and it degrades gracefully if the model or corpus is missing.
Presenter notes and fallbacks: [docs/DEMO.md](docs/DEMO.md).

**To reproduce the headline numbers:**

```bash
.venv/Scripts/kyc-nli generate && .venv/Scripts/kyc-nli compare
```

**To read actual benchmark instances** before trusting any number:

```bash
.venv/Scripts/kyc-nli inspect --language ta --phenomenon cross_script_name_icao -n 2
```

Other commands: `kyc-nli languages`, `run-baseline`, `translit-eval`,
`calibrate-ocr`, `fetch-dakshina`.

## Data

**No real identity document, and no real person's data, is stored in this
repository or produced by it.** Every generated instance asserts
`provenance.contains_real_pii = False`, and the test suite fails if that is ever
untrue. `.gitignore` blocks `data/`, `results/` and all image and PDF extensions
repo-wide as a second guard.

| Source | Used for | License | Status |
| --- | --- | --- | --- |
| `kyc_nli.data.name_pools` (embedded) | fabricated names for all 5 languages | MIT (this repo) | ✅ in use |
| Dakshina | **all four** non-English languages: native/romanised lexicon pairs for hi, ta, bn, ur | CC BY-SA 4.0 | planned (M2) |
| MIDV-2020 | document templates, mock identities; OCR noise calibration | free for research — **redistribution terms must be confirmed before releasing derived annotations** | planned (M1) |

The embedded pools pair common given names with common surnames at random. A
randomly paired name carries no identifying information, and this is what lets
the repo run on a clean checkout with zero downloads.

## Reproducing the results

| Output | Command |
| --- | --- |
| Baseline comparison table | `kyc-nli generate && kyc-nli compare` |
| Live demo | `.\demo.ps1` |
| Full report for one system | `kyc-nli run-baseline rule_engine` |
| Noise ablation (README table) | `scripts/run_noise_ablation.ps1` |
| Fetch Dakshina (~2 GB, once) | `.venv/Scripts/kyc-nli fetch-dakshina` |
| Calibrate the OCR noise model | `.venv/Scripts/kyc-nli calibrate-ocr --fetch` (needs Tesseract) |
| Train the cross-encoder (CPU, ~2h) | `.venv/Scripts/python scripts/train_cross_encoder.py` |
| Train it properly (GPU, ~10 min) | [`notebooks/m3_colab.ipynb`](notebooks/m3_colab.ipynb) |
| Score engines vs. human romanisations | `.venv/Scripts/kyc-nli translit-eval` |
| Test suite | `.venv/Scripts/python -m pytest` |
| Rebuild the mid-review deck | `node scripts/build_midreview_deck.js` (needs `npm install pptxgenjs`) |
| Regenerate the corrected Review 1 deck | `python scripts/fix_review1_citations.py "docs/proposal/NLP review 1.pptx" "docs/proposal/NLP review 1 (corrected).pptx"` |
| Lint | `.venv/Scripts/ruff check src tests` |

Every number is reproducible from a config plus a seed. Results land in
`results/`, which is gitignored except its manifest.

## Repository layout

```
configs/          experiment + language configs (languages.yaml is the source of truth)
data/             all datasets — GITIGNORED, never committed
docs/
  plan.md         the project plan, feasibility gates, risk register
  label-definitions.md    ground truth for annotation
  evaluation-protocol.md  frozen reporting protocol
  decisions/      numbered architecture decision records
  proposal/       Review 1 deck, its corrected version, and the mid-review deck
  literature/     citation-audit.md -- all 12 references checked against source
  DEMO.md         presenter notes for the live walkthrough
notebooks/        exploratory only, numbered, outputs stripped
src/kyc_nli/
  schema.py       the data model — start here
  languages.py    language registry loaded from config
  data/           name pools, MRZ construction, instance generator, IO + splits
  ocr/            script-aware corruption model
  translit/       ICAO + non-normative transliteration engines
  consistency/    cross-field rules (currently inside baselines/rules.py)
  nli/            cross-encoder: serialisation, model wrapper, training loop
  baselines/      exact match (weak) and rule engine (the one that matters)
  evaluation/     metrics, risk-coverage
  cli.py          every experiment entry point
tests/            dataset-integrity and correctness tests
scripts/          one script per reproducible experiment
results/          metrics + figures, gitignored except MANIFEST.md
```

## Status and roadmap

- [x] **M0** Schema, generator, MRZ encoder, transliteration engines, OCR noise model, rule baseline, evaluation harness
- [x] Phase-0 pilot and go/no-go signal
- [x] Bootstrap confidence intervals and paired significance testing
- [x] **M1** Noise model calibrated against Tesseract ([findings](docs/m1-ocr-calibration-findings.md)). The hand-built model had deletion 10–17× too low; measured rates are now in `kyc_nli.ocr.measured`
- [ ] **M1b** Re-run Urdu in Nastaliq, and a second OCR engine, to separate font/engine limits from script difficulty
- [x] **M2** Dakshina integrated — engines measured against human romanisations ([findings](docs/m2-dakshina-findings.md))
- [ ] **M2b** A *name*-shaped corpus (Wikidata person labels); Dakshina is general vocabulary
- [x] **M3a** Cross-encoder pipeline, leakage guards, and a fixed split bug ([findings](docs/m3-model-findings.md)) — clean-split training in progress
- [ ] **M3b** The GPU run — XLM-R via [`notebooks/m3_colab.ipynb`](notebooks/m3_colab.ipynb)
- [ ] **M4** Selective-prediction analysis: risk–coverage, review-load reduction
- [ ] **M5** Human-labelled 500-instance validation subset, inter-annotator agreement
- [ ] **M6** Ablations and error analysis
- [ ] **M7** Write-up
- [ ] TD1 (ID-card) MRZ support; currently TD3 passport only

## Citation

```bibtex
@misc{arya2026kycnli,
  title  = {KYC-NLI: Document-Level Natural Language Inference for Identity Verification},
  author = {Arya, Stuti},
  year   = {2026},
  note   = {Work in progress}
}
```

## License

MIT — see [LICENSE](LICENSE). Note that this covers the code and the embedded
synthetic name pools only; external corpora carry their own licenses, listed in
the Data section above.
