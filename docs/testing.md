# Testing: what is verified, and what the verification found

**Date:** 2026-09-12 · **Run it:** `.venv/Scripts/python -m pytest`
· **With coverage:** `.venv/Scripts/python -m pytest --cov=kyc_nli --cov-report=term-missing`
· **Including the slow fine-tuning test:** `.venv/Scripts/python -m pytest -m slow`

| | before the edge-case pass | after |
| --- | --- | --- |
| tests | 94 | **389** |
| statement coverage | 75% | **87%** (90% with the slow test) |
| modules with no test at all | 6 | **0** |
| defects found | — | **9** |

The nine defects are the substance of this document. A test suite that finds
nothing is a suite that was written to agree with the code.

---

## The defects the edge-case pass found

None of them changes a published number — that was checked by re-running
`kyc-nli compare` and `kyc-nli risk-coverage` after every fix, and the results in
`docs/m3-model-findings.md` are unchanged. Several of them would have changed a
future one.

### 1. The MRZ check digit accepted any Unicode letter, and scored it

`check_digit` classified characters with `ch.isdigit()` and `ch.isalpha()`. Both
are true of far more than `[0-9A-Z]`: `'É'` is alphabetic, so it was weighted as
`ord('É') - ord('A') + 10 = 146`, and `'٣'` — Arabic-Indic three — is a digit. The
function returned a number in 0–9 that looked entirely plausible and verified
against nothing.

This matters more than a wrong string. **The rule baseline treats a check-digit
failure as decisive evidence of corruption**, so a silently meaningless digit
hands the baseline we are trying to beat a false signal.

Now ASCII-only, raising on anything else.
`tests/test_mrz.py::test_check_digit_rejects_characters_outside_the_mrz_alphabet`

### 2. Accented Latin names were mutilated rather than folded

`transliterate_to_mrz_charset("JOSÉ")` returned `"JOS<"`. The É was not
recognised as ASCII-alphanumeric, so it fell through to the separator branch and
became filler.

ICAO Doc 9303 Part 3 mandates the fold to the base letter — É→E, Ü→U. Dropping it
produces **a different name in the one zone the rule baseline trusts most**, and
every downstream comparison then sees a genuine holder whose MRZ and VIZ
disagree. That is precisely the false-mismatch rate this project measures, and we
were manufacturing it.

Now NFKD-decomposes and discards combining marks. No current name pool contains
an accented Latin form, which is why no published number moved — and is also why
nothing else would have caught this.
`tests/test_mrz.py::test_accented_latin_letters_fold_to_their_base_letter`

### 3. A small dataset silently produced empty dev and test splits

`int(n * 0.15)` is 0 for any `n` below 7. A language with six identities
therefore contributed **nothing** to dev or test, without a warning, and
`kyc-nli generate --identities 5` wrote a test split that was an empty file. Every
metric downstream was then computed over nothing or crashed in a way that pointed
at the metric rather than at the split.

Each split now gets at least one identity per language wherever three exist to
share out, and fractions that would starve the training set are rejected by name
instead of returning an empty `train`.

The realistic split is byte-for-byte unchanged — asserted, not assumed:
1000 identities per language still gives exactly 700 / 150 / 150.
`tests/test_io.py::test_a_language_with_only_three_identities_still_reaches_every_split`
`tests/test_io.py::test_the_documented_split_proportions_are_unchanged_at_realistic_size`

### 4. The risk–coverage curve flattered systems whose confidence means nothing

Predictions were ranked by confidence with a stable sort, so ties kept **dataset
order**. The exact-match baseline reports confidence 1.0 for every prediction, so
every one of its 1,050 predictions was one tie block — and the curve it produced
was a confidently descending line that was purely an artefact of the order
instances happened to sit in the file. The most flattering possible reading of a
system with no confidence signal at all.

Risk within a tied block is now the expectation over orderings inside it. Exact
match renders as what it is: flat at 0.542 across the whole curve.

This one is load-bearing. The entire M4 argument is read off these curves, and the
first thing it says is which systems can be thresholded at all.
`tests/test_metrics.py::test_risk_coverage_is_flat_when_every_confidence_is_identical`

### 5. "What are the Latin renderings of an empty field?" had five answers

The Latin engine returned `{""}`. The four native-script engines returned the
**empty set** — which a caller reads as *no Latin string is an acceptable
rendering of this name*, not as *there is no name here*. The same disagreement
appeared for a field of spaces, and for a field whose entire content is a
zero-width non-joiner (the character M1 traced the phantom Tamil 0.071 CER floor
to).

M1 measured the whole word coming back blank as roughly 97% of all Urdu OCR
error. The inconsistency therefore sat directly on the commonest damaged input
in the project, and made the rule engine's behaviour depend on which language it
had been handed.

`variants()` now returns `{""}` for input that carries no romanisable content, in
every engine. A real surname falling back to that is asserted to be impossible,
so the fix cannot hide an engine that has silently stopped generating.
`tests/test_translit_edge_cases.py::test_an_empty_field_has_exactly_one_rendering_in_every_language`
`tests/test_translit_edge_cases.py::test_a_real_name_never_falls_back_to_the_empty_rendering`

### 6. One reported rate used a different denominator from all the others

`review_load` divided by `len(predictions)`; every other rate in `evaluate()`
divided by the instances actually scored. A caller scoring a subset while holding
the full prediction list — which is exactly what the demo's sampling does —
got a review load computed over a larger population than its own error rates.
`tests/test_metrics.py::test_extra_predictions_do_not_change_any_denominator`

### 7. Scoring an empty split divided by zero instead of naming the problem

`evaluate([], [])` and `risk_coverage([], [])` both raised `ZeroDivisionError`
from inside the metric. An empty split is essentially always a splitting bug, and
a zero-division traceback sends the reader to the wrong file. Both now refuse by
name.
`tests/test_metrics.py::test_evaluating_an_empty_split_raises_rather_than_returning_zero`

### 8. `kyc-nli inspect --language ta` never showed the language

The section rule was built as `f"{id}  [{lang}]  {phenomenon}"`, and rich parses
`[ta]` as a markup tag. The language code — the single thing the filter exists to
confirm — was silently removed from the output of every `inspect` call ever run.
`tests/test_cli.py::test_inspect_filters_to_one_language`

### 9. `mypy` was checking nothing at all

CLAUDE.md lists `.venv/Scripts/mypy` as a standing command. Run, it printed:

> Package 'kyc_nli' cannot be type checked due to missing py.typed marker

and exited **0**. An installed package without the PEP 561 marker is invisible to
mypy, so the command had been reporting success on zero files. Adding
`src/kyc_nli/py.typed` got past that and straight into a second wall: the
installed numpy stubs use `type X = ...`, which mypy refuses to parse under the
configured `python_version = "3.10"` target and which aborts the entire run on
the first file.

With both fixed, mypy checks 31 source files and is clean. What it found on its
first real run:

- **`demo.py` dereferenced two `Optional`s without narrowing.** The enclosing
  filter does guarantee they are present, so it was latent rather than live — but
  the demo is the one artefact run in front of an audience, where CLAUDE.md's rule
  is that no optional component may raise. Now narrowed explicitly.
- **`render.py` used `Image.BICUBIC`**, a deprecated Pillow alias that will be
  removed. Now `Image.Resampling.BICUBIC`.
- **Every scorable system was typed `object`.** There was no written-down
  interface for "a thing `kyc-nli compare` can score", so nothing checked that the
  cross-encoder exposes the same one as the baselines — which is the property that
  makes the comparison checkable at all. Now a `NLISystem` Protocol in
  `kyc_nli.baselines`.

---

## What each suite guards

| suite | tests | what would break without it |
| --- | --- | --- |
| `test_schema.py` | 24 | A confidence outside [0,1] sorting above genuine certainty; a mutated observation leaking between contrast-group members; Devanagari lost in a JSON round-trip |
| `test_mrz.py` | 31 | Check digits that verify against nothing; a 43-character line shifting every field after it; the ICAO specimen silently drifting |
| `test_io.py` | 25 | **The split leak.** Identities straddling train and test, a contrast group cut in half, a language missing from the test set, a digest that changes with dict ordering |
| `test_metrics.py` | 26 | A NaN propagating from an absent class; contrast consistency diluted by singletons; a selective curve that is not monotone in the threshold |
| `test_cli.py` | 27 | Every reproducibility claim. Same seed → byte-identical dataset; an unknown noise preset silently treated as clean; a missing Dakshina or Tesseract crashing instead of instructing |
| `test_noise.py` | 77 | The clean ablation corrupting its control arm; a preset ladder that is flat or inverted; the module-level RNG making a run irreproducible; deletion stopping dominating substitution, which is the M1 finding |
| `test_translit_edge_cases.py` | 51 | An engine returning nothing for a damaged field; a lowercase variant that never matches; Urdu silently getting the Arabic tables |
| `test_baselines_edge_cases.py` | 22 | The baseline being made easy to beat. Destroyed evidence read as CONTRADICTION rather than NEUTRAL is the single way to inflate the model's apparent win |
| `test_train.py` | 8 | The hand-rolled `_macro_f1` disagreeing with sklearn, so the training log and the results table measure different things; a checkpoint that will not load after nine hours of CPU |
| `test_generate.py` | 12 | Real PII entering the benchmark; NEUTRAL instances that are not structurally neutral; a non-deterministic generator |
| `test_nli_dataset.py` | 10 | **The model seeing `clean_value` or the transliteration variant sets**, either of which makes a win over the rule baseline uninterpretable |
| `test_translit.py` | 24 | Engine recall regressing below measured floors |
| `test_ocr_calibration.py` | 21 | Zero-width marks counted as OCR errors; a degradation ladder that does not degrade; a generated `measured.py` that fails to import and silently reverts the noise model to the hand-built one |
| `test_baselines.py` | 7 | The rule engine quietly weakening, which CLAUDE.md forbids |
| `test_significance.py` | 7 | Bootstrap resampling over instances instead of contrast groups, which narrows every interval by treating correlated observations as independent |
| `test_corpora.py` | 9 | The Dakshina lexicon loader silently returning nothing |
| `test_demo.py` | 8 | The live demo crashing in front of an audience because an optional component is absent |

## The slow test, and why it is worth its minute

`test_train.py::test_a_few_steps_of_real_fine_tuning_produce_a_loadable_checkpoint`
really fine-tunes a transformer — 16 instances, one epoch, about a minute — then
loads the checkpoint back through `CrossEncoderNLI` and scores four instances
with it. It is deselected by default (`-m slow` to run it) because the suite must
stay fast enough to run on every change.

It exists because `train()` had **zero** test coverage while having produced the
project's headline number, and because the real run takes 9.2 hours. A change
that breaks the loop, the freezing, the tokenisation, or the checkpoint format
should not be discovered on hour nine.

## What is deliberately not tested, and why

- **OCR accuracy itself.** `test_ocr_calibration.py` skips when Tesseract is
  absent, because Tesseract is a system package. What is tested without it: the
  alignment, the normalisation, the confusion-table shape, and the generated
  `measured.py`.
- **The Dakshina download.** A 2 GB network fetch. The loader, the lexicon
  construction and the graceful-degradation path are tested; the transfer is not.
- **Whether the rule engine's thresholds are the right thresholds.** They are a
  design choice, measured in the ablations, not a property a unit test can
  settle. What *is* tested is the boundary the thresholds implement: destroyed
  evidence must reach NEUTRAL, never CONTRADICTION.
- **The exact values of the measured noise rates.** They come from a calibration
  run, and pinning them in a test would mean a recalibration fails the build. The
  *shape* is pinned instead — deletion above substitution, the ladder monotone —
  because the shape was the M1 finding and getting it backwards was the M1 bug.

## Known gaps

| gap | coverage | why it is still open |
| --- | --- | --- |
| `ocr/calibrate.py` OCR paths | 89% | The remaining lines shell out to Tesseract with hin/tam/ben/urd packs; CI has none. The alignment, the confusion tables and the `measured.py` generator are covered |
| `data/corpora.py` download paths | 78% | Needs the 2 GB Dakshina transfer |
| `cli.py` long-running commands | 62% | `calibrate-ocr` and `translit-eval` bodies need those same two dependencies. Their argument parsing and both failure paths are covered |
| `nli/train.py` inner loop | 34% by default | Covered end to end by the `slow` test; the default run only reaches the pure helpers |
| Bootstrap CIs on the M4 curves | — | M4 reports point estimates on 1,050 instances. Resampling the *curve* over contrast groups is outstanding; see `docs/m4-selective-prediction.md` |
| Human-annotated labels | — | Milestone M5. Everything above verifies that the code does what it says; none of it verifies that the labels are what a human would assign |
