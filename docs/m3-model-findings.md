# M3 — The cross-encoder, and the split bug it exposed

**Date:** 2026-09-10 · **Status:** complete (CPU run). GPU run M3b outstanding · **Reproduce:** `python scripts/train_cross_encoder.py`

**The result:** the cross-encoder reaches **0.972 macro-F1** against the rule
engine's 0.601, cuts human review load from 63% to 29%, and *lowers* the
false-rejection rate while doing it. The project's revised claim is met.
[Jump to the numbers](#the-result).

**Read the next section first anyway.** The first version of that result was
0.989, and it was meaningless — a data-splitting bug had put 94% of the test
identities into training. The number that survives is the one measured after the
fix, and the bug is more instructive than the score.

---

## The bug: 94% of test identities were also in training

`split_by_identity` split on `contrast_group_id`. But **one fabricated identity
produces three contrast groups** — `-name`, `-time` and `-evidence` — that share a
surname, a date of birth, a date of issue and a document number. Splitting on the
group therefore scattered a single document across train, dev and test.

Measured on the affected dataset:

| split | instances | contrast groups | **distinct identities** |
| --- | --- | --- | --- |
| train | 4,905 | 2,100 | 973 |
| test | 1,037 | 450 | 383 |

**Identity overlap between train and test: 359 of 383 — 94%.**

A model could memorise "the document with surname বন্দ্যোপাধ্যায় has date of birth
1959-01-02" from the `-name` group in training and recall it from the `-time` group
in test. That is memorisation scored as inference.

The function was *named* `split_by_identity` while splitting by contrast group.
The name asserted the property; nothing tested it.

### What the invalid run reported

The first cross-encoder run, on the leaked split:

| system | macro-F1 | contrast consistency | false-mismatch |
| --- | --- | --- | --- |
| rule engine | 0.805 | 0.624 | 0.246 |
| **cross-encoder (INVALID)** | **0.989** | 0.973 | 0.010 |

Per-language it was ≥0.98 everywhere, NEUTRAL F1 was exactly 1.000, and the
paired bootstrap said the +0.184 gap was significant. Every one of those numbers
is unusable. They are recorded here so that nobody finds the checkpoint later and
believes them; it is kept on disk as
`results/models/cross_encoder_LEAKED_SPLIT_invalid/`.

The tell, in hindsight, was NEUTRAL F1 of exactly 1.000 on a class the rule
engine also finds easy but not that easy. It looked like a good model. It was a
model that had seen the answers.

### The fix

- `Instance` now carries an explicit `identity_id`, set by the generator, rather
  than the split parsing a key out of a string.
- `split_by_identity` splits on it, and genuinely does what its name says.
- Three new tests in `tests/test_generate.py`, including
  `test_splits_do_not_share_identities`, which fails the build on any overlap,
  and `test_one_identity_spans_several_contrast_groups`, which asserts the
  precondition that makes the identity-level split necessary in the first place.

After the fix: train 700 identities, dev 150, test 150, **overlap zero**.

---

## What the corrected bar looks like

Regenerating with the identity-level split *and* the M1 measured noise model
puts the rule engine at:

| system | macro-F1 | contrast | false-mismatch | review load |
| --- | --- | --- | --- | --- |
| exact match | 0.268 [0.248, 0.289] | 0.000 | 0.893 | 0.000 |
| **rule engine** | **0.601** [0.565, 0.636] | 0.307 | 0.093 | 0.634 |

0.601 matches the M1 ablation's moderate-noise figure of 0.597 exactly, which is
the consistency check that says the regenerated dataset is the dataset the
ablation described.

**That 0.601 is the number to beat**, and the rule engine is sending 63% of all
traffic to a human to achieve it.

---

## The pipeline

| Piece | What it does |
| --- | --- |
| `nli/dataset.py` | Serialises a document into text; guards what the model may see |
| `nli/model.py` | Same `predict()` interface as the rule baselines |
| `nli/train.py` | Fine-tuning loop, CPU or GPU |
| `notebooks/m3_colab.ipynb` | The GPU run: XLM-R, ~10 min on a free T4 |

The model joins `kyc-nli compare` automatically once a checkpoint exists, and is
scored by the same harness with the same bootstrap CIs and paired tests. A model
scored by a different code path than its baseline is a model whose comparison
nobody can check.

### What the model is not allowed to see

Two rules, both enforced by tests:

1. **`clean_value`** — the pre-corruption ground truth, kept for error analysis.
   If it reached the model the failure would be invisible; it would simply look
   like a very good model.
2. **The transliteration variant sets** — the rule baseline's central advantage.
   Handing the model the ICAO tables would make any win over that baseline
   uninterpretable.

The leakage guard for (1) took three attempts, and the wrong ones are instructive:

- **v1** flagged 1086/4905 instances. All false positives: it compared each field
  against its own corrupted value, and an insertion corruption necessarily
  contains the clean value — `23 SEP 2011` is inside `23 SEP 2011I`.
- **v2** flagged 4570/4905, and the concept was wrong. It treated a value
  appearing in another *zone* as leakage. Identity documents repeat the same
  value across zones by design; recovering a corrupted VIZ field from an intact
  MRZ field is exactly the cross-zone inference the project is about. Calling it
  leakage would forbid the model from doing the thing the project exists to do.
- **v3** asserts the property that actually matters, and it is a property of the
  serialiser rather than of the data: each observation is rendered from its own
  `value`, never from `clean_value`. Result: zero, by construction.

### Making CPU training possible

The first serialisation ran to a **median of 347 subword tokens** per instance.
Compressing field names, dropping the script tag (recoverable from the
characters) and dropping exact confidence (what matters is legible or not) got it
to **159** while encoding the same facts.

Combined with freezing the embedding table — 92M of 135M parameters in
`distilbert-base-multilingual-cased` — that is the difference between a
three-hour epoch and a one-hour one.

**Even so, the real CPU run took 9.2 hours for three epochs, not the two I
estimated.** That estimate was 4.5x optimistic and the plan should not repeat it.

---

## The result

Trained on the corrected identity-level split, with the M1 measured noise model.
`distilbert-base-multilingual-cased`, embeddings frozen, 2 epochs, 136 minutes on
a 4-thread CPU. Scored on 1,050 held-out instances from 150 identities that never
appear in training.

| system | macro-F1 (95% CI) | whole-group correct | genuine customers rejected | sent to a human |
| --- | --- | --- | --- | --- |
| exact match | 0.268 [0.248, 0.287] | 0.000 | 89.3% | 0% |
| rule engine | 0.601 [0.565, 0.640] | 0.307 | 9.3% | 63.4% |
| **cross-encoder** | **0.972** [0.962, 0.982] | **0.936** | **5.7%** | **28.6%** |

Paired bootstrap, 1000 resamples over contrast groups:
**model − rule engine = +0.371 [0.329, 0.409], significant.**

**The model is better on every axis simultaneously**, which was not guaranteed and
did not happen at epoch 1. After one epoch it beat the rule engine on macro-F1
(0.949) but *rejected more genuine customers* than the rule engine did (16.7% vs
9.3%) — it had bought accuracy by being willing to decide. The second epoch closed
that: 5.7%, now better than the baseline, while still halving the review load.

That is the project's revised claim, met:

> Under OCR corruption, a learned entailment model recovers decisions a
> transliteration-aware rule engine must abstain on — reducing human review load
> at equal or better error rate.

Review load 63.4% → 28.6%, and the error rate went *down*, not merely held.

### Where it is still wrong, and where that is suspicious

| class | F1 | | language | macro-F1 |
| --- | --- | --- | --- | --- |
| entailment | 0.950 | | English | 0.982 |
| contradiction | 0.967 | | Hindi | 0.982 |
| **neutral** | **1.000** | | Bengali | 0.977 |
| | | | Tamil | 0.972 |
| | | | **Urdu** | **0.949** |

| phenomenon | accuracy |
| --- | --- |
| cross_script_name_alt_romanisation | **0.839** |
| cross_script_name_mismatch | 0.913 |
| cross_script_name_icao | 0.915 |
| everything else (5 phenomena) | 1.000 |

Two things to read here, and one to be sceptical of.

**The residual error is concentrated exactly where it should be.** The three
cross-script name phenomena are the hard ones and carry every mistake; the five
structural phenomena are perfect. A model that had learned only the temporal
rules would show the opposite pattern, and that is the failure this breakdown
exists to catch. Urdu is the weakest language, consistent with M1 measuring
Tesseract failing on it hardest and M2 measuring it as the most one-to-many.

**NEUTRAL F1 of 1.000 is a property of the benchmark, not an achievement.**
Say this before a reviewer does. NEUTRAL instances are constructed by *removing*
or *destroying* evidence, so the serialised premise shows the field missing or
marked `?`. Detecting that is a surface pattern, and the rule engine also scores
1.000 on both NEUTRAL phenomena. It confirms the generator does what
[decision 0002](decisions/0002-neutral-is-evidence-insufficiency.md) says, and
nothing more. A NEUTRAL class that required real judgement would need human
annotation — milestone M5.

Earlier in this milestone, NEUTRAL F1 of 1.000 was the tell that exposed the
split leak. It is not that here — the split is verified leak-free and the other
classes sit at 0.95-0.97 rather than at ceiling — but it is the same number, and
it deserves the same scepticism every time it appears.

## Status and what remains


Still open:

- **The GPU run (M3b).** XLM-R rather than a distilled model, embeddings
  unfrozen, ~10 minutes on a free Colab T4. `notebooks/m3_colab.ipynb`. A
  distilled CPU model is a floor, not a ceiling.
- ~~The risk–coverage curve~~ — **done in [M4](m4-selective-prediction.md).**
  Holding the automation error fixed rather than comparing operating points
  sharpens the result considerably: the rule engine cannot reach a 5% error
  budget at *any* threshold, and its risk–coverage curve is not monotone,
  because its confidences encode which rule fired rather than how likely that
  rule is to be right. Bootstrapping the curve itself is still outstanding.
- **Everything here is still synthetic.** Real romanisations (M2) and real OCR
  rates (M1) feed the generator, but no real identity document does, and no human
  has annotated a single label. M5 remains the honest limit on all of this.
