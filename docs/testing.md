# Testing: what is verified, and what the verification found

**Date:** 2026-09-12 · **Run it:** `.venv/Scripts/python -m pytest`
· **With coverage:** `.venv/Scripts/python -m pytest --cov=kyc_nli --cov-report=term-missing`
· **Including the slow fine-tuning test:** `.venv/Scripts/python -m pytest -m slow`

| | before the edge-case pass | after |
| --- | --- | --- |
| tests | 94 | **409** |
| statement coverage | 75% | **87%** (90% with the slow test) |
| modules with no test at all | 6 | **0** |
| defects found | — | **15** (9 in the edge-case pass, 6 while building the paper) |

The fifteen defects are the substance of this document. A test suite that finds
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

## Found while building the paper (2026-10-21)

Writing a paper means recomputing every number from scratch and putting it in
front of a reader who will recompute it again. That turned up six more defects.
**None changes a published headline** -- each was checked by re-running the
published comparison, which reproduces every macro-F1, interval and paired test
to the digit.

### 10. The text renderer silently dropped glyphs that overhung the canvas

`ocr/render.py` sized its canvas from advance widths, then **skipped** -- did not
clip, skipped -- any glyph whose bitmap did not fit. Marks like the Devanagari
reph and ी overhang their advance by an amount that grows with font size, so at
160px with 4px padding चटर्जी rendered as चटज: 23% of its ink gone, no error.

This renderer produces the ground-truth images for the M1 OCR calibration, so the
first question was whether M1 was affected. If it had been, Tesseract would have
been scored as "deleting" characters that were never drawn -- inflating exactly
the deletion rate M1's finding rests on. It was not: all 4,200 calibration
renders were re-rendered with padding large enough that nothing could overhang,
and **0 of 4,200 had lost ink**. At calibration sizes (22-32px, padding 16) the
overhang never exceeds the padding.

The canvas now grows to fit an overhanging glyph. Because it grows only when
something overhangs, all 4,200 calibration renders are **byte-identical** to
before -- verified pixel for pixel against the committed version -- so
`ocr/measured.py` and every noise-conditioned result stand.
`tests/test_ocr_calibration.py::test_no_glyph_is_ever_dropped_for_overhanging_the_canvas`
fails on the old renderer and passes on the new one.

### 11. A confidence interval depended on the order the data arrived in

The bootstrap resamples contrast groups by position, and built the group list in
arrival order. The same split, the same predictions and the same seed therefore
gave **[0.566, 0.637]** when evaluated straight from the generator (shuffled) and
**[0.565, 0.640]** when read back from disk (sorted). A confidence interval that
moves when a file is reordered is not reproducible.

Groups are now sorted by id. Group ids are fixed-format, so sorted order is the
order an id-sorted file always produced, and **every published interval is
unchanged** -- confirmed by re-running `kyc-nli compare`. The existing
determinism test held the order fixed, which is exactly why it never saw this.
`tests/test_significance.py::test_the_interval_does_not_depend_on_the_order_instances_arrive_in`
fails on the old code.

### 12. The review-load search stepped over the optimal threshold

`review_load_at_error` searched thresholds on a 0.01 grid. The cross-encoder's
confidences cluster just below 1.0, and the grid lumped that whole cluster
together: it reported **42.3%** review at a 2% error budget where the true
optimum is **35.4%**, and 48.7% at 1% where it is 43.8%. The search is now exact,
over every distinct confidence (`operating_points`). The rule engine's numbers,
and every "unreachable" verdict, were unaffected -- re-checked by exhaustive
sweep over all 37 of its distinct confidences.
`tests/test_metrics.py::test_the_exact_search_finds_a_threshold_a_grid_steps_over`.

### 13. Abstention thresholds were tuned on the test set

Both the grid and the exact search choose the threshold on the split they then
report on. That is the most favourable setting possible -- fine for a claim that
something is **impossible** ("the rule engine cannot reach 5% error even with a
test-tuned threshold"), and wrong for a claim that a system **meets** a budget.
`kyc-nli risk-coverage` now chooses thresholds on dev and applies them unchanged
to test (`operating_point_at`), and reports the error that actually results,
including when it overshoots. See `docs/m4-selective-prediction.md`.

### 14. Stale and miscomputed numbers in the findings documents

Recomputing every figure for the paper exposed five numbers in the docs that did
not match the data they described:

| Claim | Was | Is | Why it was wrong |
| --- | --- | --- | --- |
| deletion ÷ substitution | "about 1.8× at every level" | **1.3–3.6×** | 1.8× was the moderate level alone |
| hand-built deletion error | "10–17× too low" | **5–17×** | the doc's own table gives 5×, 17×, 9× |
| hand-built sub ÷ del | "roughly 8×" | **4.5–8×** | 8× was the moderate level alone |
| Bengali spellings per word | 3.67 | **3.77** | a 2,000-word sample mean in a row of full-corpus counts |
| Urdu transliteration recall | 0.303 | **0.295** | from an earlier engine version; current code reproduces 0.295 |

Each is corrected in place with a dated note. No conclusion moves: deletion
still dominates at every level, and Urdu is still the weakest script.

### 15. The noise-ablation datasets leak identities -- unusable for a trained model

The `abl_{clean,light,moderate,heavy}` datasets predate the identity-level split
fix: they carry no `identity_id`, and **253 of their 616 test instances (41%)
share a document number with the cross-encoder's training set**. The rule
baselines are untrained, so their published ablation numbers stand. A trained
model must never be scored on those files.

`scripts/noise_robustness.py` measures the model across noise levels instead by
regenerating synth_v0's exact config at each preset. The generator's identity
sampling is independent of the noise preset, so every level yields the
**identical** 1,050 held-out instances -- same ids, same gold labels, same
document numbers, zero training overlap -- asserted in the script, not assumed.

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
