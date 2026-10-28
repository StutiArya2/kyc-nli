# How KYC-NLI works, end to end

Written to be explained out loud. Every number here is reproducible from the
repo; every component named is a real file you can open.

---

## Part 1 — The problem

### What a KYC system actually does

When you open a bank account, an automated system reads your ID document and
compares it against what you typed into a form. Concretely it asks a series of
questions of the form:

> The form says the surname is CHATTERJEE. Does this document agree?

Almost every production system answers that by **comparing characters**, with
some fuzzy tolerance for typos. That works when the document and the form are in
the same script. It breaks in three specific ways when they are not.

### Failure 1 — Cross-script: the same name, zero characters in common

An Indian passport prints the holder's name **twice**: once in a regional script
in the Visual Inspection Zone (VIZ), and once in Latin in the English zone and
the Machine Readable Zone (MRZ).

| Zone | Content |
| --- | --- |
| VIZ (Devanagari) | `चटर्जी` |
| MRZ (Latin) | `CHATTERJEE` |

Those are the same surname on the same physical card. As byte sequences they
share **nothing**. Any character-based comparison returns "mismatch" and rejects
a real customer.

This is not an edge case. It happens on **every single document** in a
non-Latin script.

### Failure 2 — Romanisation is one-to-many, and we measured how badly

The natural fix is a lookup table: Devanagari → Latin. That fails because for
Indian languages **there is no single correct answer**.

Measured on the [Dakshina dataset](https://github.com/google-research-datasets/dakshina)
(Google Research; romanisations written by native speakers, ~30,000 words per
language):

| Language | Spellings per word | Words with **more than one** spelling |
| --- | --- | --- |
| Hindi | 1.79 | 57.0% |
| Tamil | 2.71 | 74.6% |
| Bengali | 3.67 | 90.2% |
| **Urdu** | **4.20** | **97.6%** |

**In Urdu, 98% of words have more than one human romanisation.** A system that
assumes one right answer is wrong before it starts.

The reasons are structural, not sloppiness:

- **Tamil does not write voicing at all.** The letter க is read *K* or *G*
  depending on position, ப is *P* or *B*. கண்ணன் is legitimately KANNAN **or**
  GANNAN. There is no fact of the matter to look up.
- **Urdu does not write short vowels.** The script gives you a consonant
  skeleton — صدیقی yields `SDYQY` — and the vowels come from knowing the name.
  It is SIDDIQUI.
- **Bengali's inherent vowel is nearer /o/ than /a/**, and the language has no
  /v/. So বসু is BASU or BOSE; বন্দ্যোপাধ্যায় is BANDYOPADHYAY or BANDOPADHYAY.
- **Hindi has no normative table at all.** ITRANS, IAST and ad-hoc spellings
  coexist, and the same person romanises their own name differently on different
  forms.

### Failure 3 — OCR damages the text before anyone compares it

Documents are photographed on phones. We **measured** what a real OCR engine
(Tesseract 5.4) does to each script by rendering known text, degrading it to
approximate camera capture, reading it back, and aligning the result:

| Capture quality | Substitutions | **Deletions** | Insertions |
| --- | --- | --- | --- |
| clean | 0.005 | 0.011 | 0.002 |
| light | 0.008 | 0.025 | 0.001 |
| moderate | 0.096 | **0.170** | 0.024 |
| heavy | 0.270 | **0.363** | 0.032 |

**OCR deletes more characters than it substitutes, at every level — by 1.3× to
3.6×, depending on capture quality.** That matters: a
substitution leaves something to match on, a deletion removes the evidence
entirely.

### Why two answers are not enough

Given all three failures, a system comparing a claim against a document can be
in three genuinely different situations:

| Situation | Correct response |
| --- | --- |
| The document supports the claim | Accept |
| The document refutes the claim | Reject |
| **The document cannot say** | **Send to a human** |

Production systems have the first two. The third is the contribution.

---

## Part 2 — The reformulation

We recast the check as **three-way Natural Language Inference**:

- **Premise** = everything readable on the document
- **Hypothesis** = one claim about the holder
- **Label** = ENTAILMENT / CONTRADICTION / NEUTRAL

### The definition everything turns on

**NEUTRAL means the premise lacks the evidence to decide. It is a property of
the document, not of the model.**

This is the project's central commitment, and it exists because the obvious
alternative is indefensible. If NEUTRAL meant *"the model isn't confident"*, the
three-way task would collapse into two-way classification plus a confidence
threshold — a solved problem, and not a contribution.

A claim is NEUTRAL when, and only when:

1. **The field is absent from the document type.** A passport MRZ carries no
   place of birth, so a claim about it is structurally undecidable.
2. **The field is present but unreadable**, and no other zone carries it.
3. **The claim is strictly more specific than the document.** The card says
   MOHAMMAD ANSARI; the claim asserts a middle name the card never records.

**The boundary everyone gets wrong:** contradiction requires *positive evidence
against*. A blank field is NEUTRAL. A field reading something else is
CONTRADICTION. A field too damaged to read is NEUTRAL — "looks different after
corruption" is not evidence.

Enforced in code: `tests/test_generate.py` fails the build if any NEUTRAL
instance carries a legible observation of the claimed field.

---

## Part 3 — The five languages, and why those five

`configs/languages.yaml` — nothing in the codebase hardcodes a language.

| Code | Script | Romanisation | What it uniquely probes |
| --- | --- | --- | --- |
| `en` | Latin | identity | Control. Every Indian document has an English zone, so this is what the others are compared *against*. |
| `hi` | Devanagari | **none** | No authority fixes the answer; holders spell their own name differently across forms. |
| `ta` | Tamil | **none** | The script does not mark voicing. A lookup table cannot be right *even in principle*. |
| `bn` | Bengali | **none** | Inherent-vowel and ya-phala alternations — tests whether a model learns a *script-level rule* rather than per-name memorisation. |
| `ur` | Perso-Arabic | partial | Short vowels unwritten; RTL; diacritics OCR drops. The internal contrast case. |

Two design points worth stating:

- **Four of five are non-normative.** The set is deliberately concentrated where
  a lookup table cannot win.
- **All five appear on documents issued by one state.** So the cross-script
  comparison is *within one document*, not across two countries' records. That
  is what makes "document-level" inference the honest framing.

---

## Part 4 — The system, component by component

### 4.1 The data model — `src/kyc_nli/schema.py`

```
Instance
├── identity_id          which fabricated holder this came from
├── contrast_group_id    which minimal-pair group
├── language, phenomenon what this instance probes
├── premise: [FieldObservation]
│     ├── field          surname | date_of_birth | ...  (closed schema)
│     ├── zone           viz | mrz | barcode | chip | form
│     ├── value          what OCR READ  (may be corrupted)
│     ├── clean_value    what was PRINTED  (analysis only — never an input)
│     ├── script, language
│     └── confidence     OCR confidence
├── hypothesis           field + value + natural-language text
├── label                ENTAILMENT | CONTRADICTION | NEUTRAL
├── rationale            why this label, in words
└── provenance           generator, seed, contains_real_pii (always False)
```

Two fields carry most of the design:

- **`zone`** — the same logical field appears in several zones in different
  scripts and formats. Cross-zone comparison is where the whole problem lives.
- **`clean_value`** — ground truth kept *only* for error analysis. It never
  reaches any system. Guarded by `leaks_ground_truth()` and a test.

### 4.2 The generator — `src/kyc_nli/data/generate.py`

Real identity documents cannot be legally collected, so we fabricate them.

**Step 1 — invent a holder.** Draw a `(native_script, attested_latin)` name pair,
dates constrained to be *jointly possible* (issued within its template era, a
10-year validity, born before issue), a document number, sex, place of birth.

**Step 2 — print the document.** Write the VIZ in the native script and the MRZ
in Latin, including a **real ICAO 9303 TD3 machine-readable zone** with working
check digits. (`src/kyc_nli/data/mrz.py` — validated against the standard's own
worked example: `D23145890734` → check digit `9`.)

**Step 3 — damage it.** Apply the measured OCR noise model.

**Step 4 — pose claims.** For each holder, generate **minimal-pair contrast
groups**: instances sharing a premise that differ by one controlled edit.

| Phenomenon | Label | What it tests |
| --- | --- | --- |
| `cross_script_name_icao` | E | Standard romanisation across scripts |
| `cross_script_name_alt_romanisation` | E | An *alternative* legitimate spelling |
| `cross_script_name_mismatch` | C | A different person's name |
| `temporal_consistent` | E | Dates that hang together |
| `impossible_date_triple` | C | Each field valid, jointly impossible |
| `date_off_by_one` | C | Legible, and different |
| `field_absent_from_document` | N | The document type has no such field |
| `field_illegible` | N | Present but unreadable, no other zone |

**Why contrast groups matter.** A system that has learned "these two strings look
similar" will get one member of a group right and the others wrong. Reporting
per-group accuracy exposes that; reporting aggregate accuracy hides it.

### 4.3 Transliteration engines — `src/kyc_nli/translit/`

Each engine maps native script to **a set of acceptable Latin renderings**, never
a single string. That is the entire point — modelling a one-to-many relation as a
function manufactures false mismatches.

- `DevanagariTransliterator`, `TamilTransliterator`, `BengaliTransliterator`
  share a `BrahmicTransliterator` base: consonants carry an inherent vowel, a
  vowel sign replaces it, a virama deletes it. Each subclass declares its own
  legitimate alternations.
- `UrduTransliterator` extends the ICAO Doc 9303 Arabic table with the letters
  Urdu adds — and, critically, treats **ی and و as both consonants and long
  vowels** (*matres lectionis*). Adding that one linguistic fact took Urdu recall
  from 0.086 to about 0.30.

**Measured against Dakshina's held-out split** — romanisations we did not choose:

| Language | Finds *a* human spelling | Finds the *most common* one |
| --- | --- | --- |
| Hindi | 0.800 | 0.725 |
| Tamil | 0.833 | 0.662 |
| Bengali | 0.860 | 0.625 |
| Urdu | 0.295 | 0.146 |

### 4.4 The OCR noise model — `src/kyc_nli/ocr/`

Script-aware, because scripts break differently: Latin confuses `0/O`; Devanagari
loses matras; Perso-Arabic loses dots (and losing a dot *changes the letter*);
Cyrillic has cross-script homoglyphs that are visually identical.

**These rates are measured, not guessed** (`kyc-nli calibrate-ocr`):

1. Render known text with **correct complex-script shaping** — HarfBuzz for
   layout, FreeType for glyphs. (Pillow alone does not shape: Devanagari matras
   would not reorder, Arabic would not join, and we would have calibrated against
   text no document contains.)
2. Degrade it — blur, sensor noise, JPEG, rotation, contrast.
3. OCR it with Tesseract.
4. Align output against input with Levenshtein backtrace to attribute *which
   character became which*.

**Honest limit:** rendered text has no paper grain, glare or perspective, so
these rates are a **lower bound** on real-document error.

### 4.5 The rule baseline — `src/kyc_nli/baselines/rules.py`

**This is deliberately built to win**, and it is the most important component.
Every reviewer will ask whether the neural model does anything a rulebook could
not. This file is the answer, so it is given every advantage:

1. **Evidence check** — no observation of the field, or all illegible → NEUTRAL.
2. **Cross-field temporal consistency** — validity > 10 years, expiry before
   issue, birth after issue, issue predating the template era → CONTRADICTION.
   Runs *before* field matching: a jointly impossible document is contradicted
   regardless.
3. **Transliteration-aware name matching** — generate every Latin variant of
   every observation, take the best fuzzy score. Above threshold → ENTAILMENT;
   below → CONTRADICTION; **in between → NEUTRAL** (its own abstention band).
4. **Date matching** with format normalisation across `17 SEP 2011`,
   `2011-09-17`, MRZ `110917`. Unparsable → NEUTRAL, not mismatch.
5. **Literal matching** with MRZ check-digit verification.

A hard rule in `CLAUDE.md`: never weaken this to make the model look better.

### 4.6 The neural model — `src/kyc_nli/nli/`

A **cross-encoder**: both texts go into one transformer together, so it can
attend across them.

`distilbert-base-multilingual-cased`, 135M parameters, fine-tuned for 3-way
classification. Embeddings frozen (92M of 135M params), 2 epochs, **136 minutes
on a 4-thread CPU**.

**The input.** The document is flattened to one line, the claim to another:

```
A: dob:mrz=53091 | dob:viz=1 S 93 | doe:mrz=210917 | ... | sur:mrz=CHTTERJBF | sur:viz=चटर्ी
B: The holder's surname is CHATTERJEE.
```

Design choices, each with a reason:

- **Field names abbreviated, script tag dropped, exact confidence dropped.** The
  first version ran to a median of **347 tokens**; this one is **159**, encoding
  the same facts. On a CPU that is a three-hour epoch versus a one-hour one.
- **Unreadable fields become `=?`**, not their garbage characters. Passing the
  garbage through invites pattern-matching on noise; `?` states the thing that
  actually decides the NEUTRAL cases.
- **The model never sees `clean_value`**, and **never sees the transliteration
  variant sets.** The second is the important one: handing it the ICAO tables
  would make any win over the rule baseline uninterpretable. It has to learn the
  cross-script relationship from raw observations.

### 4.7 The evaluation harness — `src/kyc_nli/evaluation/`

Four mandatory reporting levels. Reporting only the first is how a weak result
gets past a skim:

1. **Macro-F1 and per-class F1** — macro, never accuracy, because NEUTRAL is the
   rarest and most consequential class.
2. **Per language** — a headline driven by English says nothing about the
   cross-script claim.
3. **Per phenomenon** — a win on easy temporal cases must not hide a loss on
   cross-script matching.
4. **Contrast-group consistency** — the fraction of minimal-pair groups where
   *every* member is right. **This is the metric that catches surface matching.**

Plus operational metrics a KYC team actually pays for: false-mismatch rate,
over-abstention, over-confidence on NEUTRAL, and human review load.

**Statistics.** Every macro-F1 carries a bootstrap 95% CI; every system
comparison uses a **paired** bootstrap. Two subtleties:

- **The resampling unit is the contrast group, not the instance.** Members of a
  group share a premise, so their outcomes correlate. Resampling instances treats
  correlated observations as independent and yields intervals measurably **~7%
  too narrow** — which makes differences look significant when they are not.
- **Paired, not overlapping intervals.** Two overlapping CIs can still be a
  significant paired difference. The overlap heuristic is weaker and commonly
  misread.

**Splitting.** By **identity**, stratified by language. One holder generates
three contrast groups sharing a surname and dates, so splitting by group let 94%
of test identities appear in training. (See Part 6.)

---

## Part 5 — One instance, all the way through

Real instance `hi-00000-name-e` from the test split.

**The card, as printed:**

| Zone | Field | Value |
| --- | --- | --- |
| VIZ (Devanagari) | surname | `चटर्जी` |
| MRZ (Latin) | surname | `CHATTERJEE` |
| VIZ | date of birth | `17 SEP 1953` |

**After OCR damage — what the system actually receives:**

| Zone | Field | Read as | Confidence |
| --- | --- | --- | --- |
| VIZ | surname | `चटर्ी` — lost the ज | 0.83 |
| MRZ | surname | `CHTTERJBF` — lost A, E→B, E→F | 0.70 |
| VIZ | date of birth | `1 S 93` | 0.55 |
| MRZ | date of birth | `53091` | 0.83 |

**The claim:** *The holder's surname is CHATTERJEE.*
**Gold label:** ENTAILMENT.

So the system must conclude that a damaged Devanagari string and a damaged Latin
string both denote CHATTERJEE. Three problems stacked at once.

**How the rule engine attacks it:** transliterate `चटर्ी` through the Devanagari
engine → a variant set (CHATARJI, CHATARJEE, CHATTARJI…); fuzzy-match each
against CHATTERJEE and against the MRZ's `CHTTERJBF`; take the best score; compare
against thresholds. On this class of case it gets **0.915** accuracy.

**How the model attacks it:** it sees both damaged strings side by side in one
sequence and has learned, from training, that this pattern of damage over this
pair of scripts denotes that name. **0.915** on this phenomenon too — the two
systems are closest exactly here, and the model's advantage comes from the cases
where OCR damage has destroyed what the rule engine needs to parse.

---

## Part 6 — The experimental method

Two methodological commitments did more for this project than any modelling
choice.

### We built the strongest counter-argument first

Before training anything, we built the rule baseline and ran it. Result:

| Scan quality | Exact match | **Rule engine** | Sent to a human |
| --- | --- | --- | --- |
| clean | 0.368 | **0.981** | 29% |
| light | 0.354 | 0.920 | 30% |
| moderate | 0.252 | 0.597 | 63% |
| heavy | 0.219 | 0.361 | **85%** |

**A rulebook gets 0.981 on a clean scan.** There is nothing for a model to win
there — and the original claim ("NLI beats string matching") was therefore true
but not a contribution.

But under realistic damage it collapses, and *it fails by giving up*: at heavy
noise it abstains on **79% of cases the document actually decides**, and 85% of
all traffic reaches a human.

That reframed the project:

> **Under OCR corruption, a learned entailment model recovers decisions a
> transliteration-aware rule engine must abstain on — reducing human review load
> at equal or better error rate.**

Narrow, hard, testable, and not already solved.

### We assumed our own results were wrong until proven otherwise

Three findings survived only because something checked them:

- **The first model scored 0.989. It was meaningless.** One identity generates
  three contrast groups sharing a surname and dates; splitting by *group* put
  **359 of 383 test identities (94%) into training too**. The model was
  memorising. The function was *named* `split_by_identity` while splitting by
  contrast group — the name asserted the property, nothing tested it. Now there
  is a test.
- **The hand-built noise model had the wrong shape.** It made substitution
  dominant; real OCR deletes 1.3–3.6× more than it substitutes, and the
  hand-built deletion rate was **5–17× too low**. Correcting it moved the rule engine from
  0.831 to 0.597 at moderate noise.
- **Tamil had a phantom 0.071 error floor.** Tesseract appends an invisible
  zero-width character after Tamil words ending in a pure consonant. After
  normalising it away: **0.001**.

---

## Part 7 — Results

Held-out: 1,050 instances from 150 identities that never appear in training.

| System | Macro-F1 (95% CI) | Whole groups right | Genuine customers rejected | Sent to a human |
| --- | --- | --- | --- | --- |
| Exact match | 0.268 [0.248, 0.287] | 0.000 | 89.3% | 0% |
| Rule engine | 0.601 [0.565, 0.640] | 0.307 | 9.3% | 63.4% |
| **Cross-encoder** | **0.972** [0.962, 0.982] | **0.936** | **5.7%** | **28.6%** |

Paired bootstrap, 1000 resamples over contrast groups:
**model − rule engine = +0.371 [0.329, 0.409], significant.**

**Better on every axis at once**, which was not guaranteed. After *one* epoch the
model beat the baseline on macro-F1 but rejected *more* genuine customers (16.7%
vs 9.3%) — it had bought accuracy by being willing to decide. The second epoch
closed that.

### The table above is still not a fair comparison, so here is the fair one

Each system is reported at *its own* operating point, and they abstain at
different rates. Macro-F1 charges nothing for the human labour that abstention
buys, and a reviewer is right to press on it. So fix the error rate instead and
ask what each system costs to run there — `kyc-nli risk-coverage`, milestone M4.
Each threshold is chosen on the dev split and applied unchanged to test; cells are
test review load with the test error it produced (✗ = over budget):

| System | err ≤ 10% | err ≤ 5% | err ≤ 2% | err ≤ 1% |
| --- | --- | --- | --- | --- |
| Exact match | unreachable | unreachable | unreachable | unreachable |
| Rule engine | 63.4% (11.2% ✗) | 92.7% (5.2% ✗) | unreachable | unreachable |
| **Cross-encoder** | **28.6% (4.0%)** | **28.6% (4.0%)** | **35.5% (1.8%)** | 41.5% (1.1% ✗) |

The rule engine cannot be operated at a 5% automation-error budget *at any
threshold* — not even one tuned on the test set itself, where an exhaustive
sweep bottoms out at 5.19% error while sending 93% of traffic to a human. The
reason is visible in its risk–coverage curve, which is **not monotone** — its
confidences record which rule fired, not how likely that rule is to be right, so
there is nothing usable to threshold on. The cross-encoder's curve is monotone
and flat at zero error to 65% coverage.

That is the sharper form of the claim: not "the model scores higher", but "only
one of these systems can be tuned to an error budget at all".
[Full write-up](m4-selective-prediction.md).

### Where it is still wrong

| Phenomenon | Accuracy | | Language | Macro-F1 |
| --- | --- | --- | --- | --- |
| cross_script_name_alt_romanisation | **0.839** | | English | 0.982 |
| cross_script_name_mismatch | 0.913 | | Hindi | 0.982 |
| cross_script_name_icao | 0.915 | | Bengali | 0.977 |
| *five structural phenomena* | 1.000 | | Tamil | 0.972 |
| | | | **Urdu** | **0.949** |

Every error is on the three cross-script name phenomena — the genuinely hard
ones. A model that had learned only the date rules would show the opposite
pattern, and this breakdown exists to catch that. Urdu is weakest, consistent
with M1 measuring Tesseract failing on it hardest and M2 measuring it as the most
one-to-many.

---

## Part 8 — What to say before you are asked

**"NEUTRAL scores exactly 1.000 — isn't that suspicious?"**
Yes, and it is a property of the *benchmark*, not an achievement. NEUTRAL
instances are built by removing or destroying evidence, so the serialised premise
shows the field missing or marked `?`. Detecting that is a surface pattern — the
rule engine also scores 1.000 there. It confirms the generator does what it
claims and nothing more. Real judgement on NEUTRAL needs human annotation.

**"It's all synthetic."**
Correct, and unavoidable: real identity documents cannot be legally collected.
But be precise about what *is* real — the romanisations are human-written
(Dakshina), and the OCR error rates are measured from Tesseract across five
scripts. What is *not* real: no document image, and no human-annotated label.

**"The OCR rates are a lower bound."**
Rendered text has no paper grain, glare or perspective. Real documents are at
least this hard, probably harder.

**"It's a distilled model on a CPU."**
A floor, not a ceiling. The GPU run with XLM-R and unfrozen embeddings is a
10-minute Colab job (`notebooks/m3_colab.ipynb`) and is not done.

---

## Reproducing everything

```powershell
.\demo.ps1                       # the walkthrough, ~1 min
kyc-nli generate                 # rebuild the benchmark from a seed
kyc-nli compare                  # score every system, with CIs and paired tests
kyc-nli run-baseline cross_encoder   # full per-language/per-phenomenon breakdown
kyc-nli translit-eval            # engines vs. real human romanisations
kyc-nli calibrate-ocr            # re-measure the OCR noise model
python scripts/train_cross_encoder.py   # retrain
```

Every number in this document comes from one of those commands plus a seed.
