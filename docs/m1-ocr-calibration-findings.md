# M1 — What a real OCR engine actually does

**Date:** 2026-09-07 · **Engine:** Tesseract 5.4.0 (`fast` models) · **Reproduce:**
`kyc-nli calibrate-ocr --words 200 --write-tables`

This closes the obligation [decision 0004](decisions/0004-ocr-noise-is-simulated.md)
has carried since the first commit: the OCR confusion sets were hand-built, and
no noise-conditioned number could appear in the paper until they were measured.
They are now measured, and **the hand-built model was wrong in a way that
mattered**.

Method and its limits: [decision 0006](decisions/0006-ocr-calibration.md).
Short version — MIDV-2020 contains no Indic or Perso-Arabic document, so it
cannot calibrate four of our five languages. We render known text with correct
HarfBuzz shaping instead, degrade it, OCR it, and align. Rendered text has no
paper grain, glare or perspective, so **every rate below is a lower bound.**

---

## Finding 1 — The noise model had the wrong shape, not just the wrong size

| level | measured sub / del / ins | hand-built (wrong) |
| --- | --- | --- |
| clean | 0.000 / 0.000 / 0.000 | same |
| light | 0.008 / **0.025** / 0.001 | 0.030 / **0.005** / 0.005 |
| moderate | 0.096 / **0.170** / 0.024 | 0.080 / **0.010** / 0.010 |
| heavy | 0.270 / **0.363** / 0.032 | 0.180 / **0.040** / 0.030 |

The hand-built model made **substitution** the dominant error, 4.5–8× more
likely than deletion. Real Tesseract output on Indic scripts is the other way
round: **deletion exceeds substitution at every level, by 1.3–3.6×**, and the
hand-built deletion rate was **5–17× too low**.

> **Corrected 2026-10-21.** This paragraph previously said deletion ran "about
> 1.8× substitution at every level" and that the hand-built rate was "10–17× too
> low". Recomputed from the table above, the deletion/substitution ratio is
> 3.0×, 1.8× and 1.3× at light, moderate and heavy (and 2.3× and 3.6× at the two
> cleaner capture conditions), and the hand-built deletion rate was 5×, 17× and
> 9× too low. 1.8× was the moderate level alone. The finding -- deletion
> dominates at every level -- is unchanged; the constants were not.

That is a qualitative error, not a calibration offset. A substitution turns a
character into a different character, which a fuzzy matcher can often still
match through. A deletion removes evidence, which it cannot. Modelling OCR as
mostly-substitution made the corrupted documents systematically easier than real
ones.

## Finding 2 — Under realistic noise the rule engine collapses much further

Re-running the ablation with the measured model:

| OCR noise | rule engine, hand-built noise | rule engine, **measured** noise |
| --- | --- | --- |
| clean | 0.980 | **0.981** |
| light | 0.903 | **0.920** |
| moderate | 0.831 | **0.597** |
| heavy | 0.651 | **0.361** |

Clean and light barely move. Moderate and heavy fall off a cliff. The Phase-0
finding survives in its direction — a rule engine is at ceiling on clean input,
so there is nothing to win there — but **the headroom under corruption is far
larger than we had been claiming**: 0.40 at moderate rather than 0.17.

Contrast-group consistency tells the same story more sharply: 0.956 clean,
**0.333** at moderate, **0.074** at heavy. Under realistic corruption the rule
engine almost never gets a whole minimal-pair group right.

## Finding 3 — The failure mode is mass abstention, which is exactly our thesis

| OCR noise | human review load | over-abstention |
| --- | --- | --- |
| clean | 0.287 | 0.009 |
| light | 0.300 | 0.027 |
| moderate | 0.630 | **0.485** |
| heavy | 0.851 | **0.792** |

Over-abstention is the rate at which the system routes a case to a human that
**the document actually decides**. At heavy noise the rule engine gives up on
79% of decidable cases, and 85% of all traffic reaches a human.

This is the strongest empirical support the project has for its revised claim.
The rule engine does not fail by guessing wrong — its overconfidence on NEUTRAL
stays at 0.000 throughout, which is to its credit. It fails by *not being able to
read*, and handing the work to a person. Recovering those decisions is precisely
what the learned model is for, and there is now a measured number on how much
work is available to recover.

## Finding 4 — Tesseract's Urdu is bimodal, and a character model cannot express it

Urdu behaves unlike every other script. A size sweep with no degradation at all:

| font size | CER | blank reads | substitutions |
| --- | --- | --- | --- |
| 48px | 0.362 | 0.350 | 0.003 |
| 32px | 0.282 | 0.250 | 0.010 |
| 24px | 0.249 | 0.233 | 0.003 |
| 16px | 0.143 | 0.100 | 0.033 |

**Almost all of Urdu's error is whole-word read failure, not misreading.** When
Tesseract reads an Urdu word at all it reads it nearly perfectly (substitution
0.003–0.033); it simply returns nothing for 10–35% of words, on pristine input.

Two consequences:

1. **A character-substitution noise model is the wrong model for Urdu.** The
   right one is a per-field read-failure probability. `MEASURED_BLANK_RATES` in
   the generated module records it per language and level.
2. **This maps directly onto the NEUTRAL class.** A blank read is evidence
   absence — exactly the structural definition NEUTRAL was given in
   [decision 0002](decisions/0002-neutral-is-evidence-insufficiency.md), arrived
   at independently and for different reasons. Real Urdu OCR failure *produces*
   the category the project defined on semantic grounds.

**Caveat, stated because it is load-bearing:** we render Urdu in Naskh
(NotoNaskhArabic). Urdu is conventionally set in **Nastaliq**, and Tesseract's
`urd` model may expect it. Some of this blank rate may be a font mismatch of our
making rather than a property of Urdu OCR. Re-running against
NotoNastaliqUrdu is a cheap, worthwhile check and is not yet done.

## Two measurement bugs found and fixed

**Zero-width characters were being counted as OCR errors.** Tesseract appends
U+200C after Tamil words ending in a pure consonant — a rendering convention,
invisible, carrying no information. It put a constant **0.071** floor under every
Tamil CER and filled the confusion tables with ZWNJ entries. After normalising
them away, pristine Tamil CER is **0.001**. Arabic diacritics are deliberately
*not* stripped: losing a kasra is a real read error.

**The degradation ladder was wrong twice, in opposite directions.** The first
version was flat — Latin read at 0.000 CER through three of four levels, so
three quarters of the axis measured one condition. The second overcorrected into
a cliff, with the hardest levels returning blank output (CER 1.0), which is total
failure rather than degraded reading. A sweep then showed the actual structure:
**at fixed blur, font size barely matters down to 16px; at fixed size, blur
drives CER from ~0 to ~0.6 between 1.0 and 2.2.** Blur is the lever. Neither
earlier ladder was built on that.

Both broken ladders passed a pixel-difference monotonicity test. The test that
caught them measures OCR output instead, and now guards the axis.

## What this licenses

**Can now be claimed:** measured per-script character error rates and confusion
matrices for five scripts across four capture conditions; that OCR error on
Indic scripts is deletion-dominated; that a transliteration-aware rule engine
degrades from 0.981 to 0.361 macro-F1 across that range, failing by abstention
rather than by error.

**Cannot be claimed:** that these are real-document rates. Rendered text is a
lower bound. Any headline must say so.

## Still open

- **Nastaliq for Urdu**, to separate font mismatch from engine limitation.
- **A real-document correction factor.** MIDV-2020 can still calibrate the
  *English* zone of a real captured document, which would give a ratio between
  rendered and real degradation for one script — evidence for whether the other
  four need adjusting. Small, well-scoped, not a blocker.
- **EasyOCR or PaddleOCR as a second engine.** Every number here is one engine's
  behaviour; a second would separate "OCR is hard here" from "Tesseract is bad
  here", which matters most for Urdu.
