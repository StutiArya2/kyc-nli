# M3 — The cross-encoder, and the split bug it exposed

**Date:** 2026-09-07 · **Status:** pipeline complete; clean-split training in
progress · **Reproduce:** `python scripts/train_cross_encoder.py`

The headline of this milestone so far is not a model score. It is a data-splitting
bug that made the first score meaningless, and would have made every subsequent
one meaningless too.

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

## Status and what remains

Training on the corrected split is running. Until it finishes there is **no valid
model number for this project**, and the invalid one must not be quoted.

Still open:

- **The GPU run (M3b).** XLM-R rather than a distilled model, embeddings
  unfrozen, ~10 minutes on a free Colab T4. `notebooks/m3_colab.ipynb`. A
  distilled CPU model is a floor, not a ceiling.
- **The result that actually matters is not macro-F1.** The revised claim is
  about recovering decisions the rule engine abstains on. The number to report is
  **review load at a fixed error rate**, and the shape is the risk–coverage
  curve. M1 measured the rule engine abstaining on 49% of decidable cases at
  moderate noise; that is the work available to recover.
- **Per-phenomenon and contrast consistency, not the headline.** A model that
  wins only on the temporal cases has learned a rule engine.
