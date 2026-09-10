# 0006 — OCR calibration is render-based, because MIDV-2020 has no Indian documents

**Status:** accepted · **Date:** 2026-09-07 · **Relates to:** [0004](0004-ocr-noise-is-simulated.md), [0005](0005-indian-language-set.md)

## Context

Decision 0004 created an obligation: the OCR confusion sets in
`kyc_nli.ocr.noise` were hand-built from documented failure modes, and **no
noise-conditioned number may appear in the paper until they are replaced with
rates measured from a real engine.** The plan named this milestone M1 and called
it the project's single point of failure, because every headline result is
conditional on it.

The plan specified the method: *"Noise-model calibration vs. Tesseract/EasyOCR on
MIDV-2020 crops."*

## The problem with that plan

**MIDV-2020 contains no document in any of our four non-Latin scripts.**

Its ten document types come from Albania, Azerbaijan, Spain, Estonia, Finland,
Greece, Latvia, Russia, Serbia and Slovakia — Latin, Greek and Cyrillic
throughout. There is no Devanagari, Tamil, Bengali or Perso-Arabic document in
it at all.

This is not a flaw in MIDV-2020. It is a consequence of decision 0005 changing
the active language set from en/ru/ar/hi/zh to the Indian context, without
anyone revisiting M1. Under the old set MIDV-2020 was a good fit — it has Russian
passports, and Russian was in the set. Under the new set it can calibrate exactly
one of our five languages, and that one is English.

Discovering this at the start of M1 rather than in the middle of it is the
entire value of naming M1 as the critical path.

## Decision

Calibrate by **rendering**: generate images of known text in each script, degrade
them to approximate capture conditions, OCR them, and align the output against
the known input.

### What this buys

- **Exact ground truth.** We know precisely what was rendered, so every OCR error
  is attributable to a specific character. A scanned corpus requires aligning
  against transcriptions that may themselves be wrong.
- **All five scripts.** The only requirement is a font, and Noto covers every one.
- **A controlled corruption axis.** We can hold everything fixed and vary only
  blur, or only resolution. That is what "robustness to OCR noise" needs in order
  to be a measurement rather than an anecdote.
- **Reproducibility.** Fonts are pinned and downloaded, not taken from whatever
  the operating system happens to have installed.

### What it does not buy, stated plainly

Rendered text has no paper grain, no print texture, no glare, no perspective
distortion, no security overlay or hologram, and no guilloche background. Real
identity documents have all of these, and some of them exist specifically to
defeat reproduction — which means they also degrade OCR.

**Therefore: the measured rates are a lower bound on real-world error.** Real
documents will be at least this hard, probably harder. Any claim of the form
"our model is robust at CER x" must say that x was measured on rendered text.

This limitation is the honest cost of the language set being Indian, and it is a
better trade than either alternative: calibrating four languages on nothing, or
changing the language set back to fit a dataset.

## Implementation notes

**Shaping had to be solved first.** Pillow only shapes complex scripts when built
against Raqm, and the standard Windows wheel is not. Without shaping, Devanagari
vowel signs do not reorder, Bengali and Tamil conjuncts do not form, and Arabic
letters do not join — every glyph renders in isolated form. Calibrating against
that would have measured how Tesseract handles text no document has ever
contained, while looking entirely successful.

Layout therefore goes through **HarfBuzz** (`uharfbuzz`) and rasterisation through
**FreeType** (`freetype-py`), with Pillow used only as a canvas.
`tests/test_ocr_calibration.py::test_devanagari_vowel_sign_reorders` asserts that
कि shapes with the vowel glyph *before* the consonant, and fails the build if
shaping ever silently stops working.

**Words come from Dakshina where available** — real vocabulary in each script,
from the test split — falling back to the embedded name pool.

## Consequences

- New commands: `kyc-nli calibrate-ocr`.
- New dependencies in the `ocr` extra: `pillow`, `uharfbuzz`, `freetype-py`.
- Fonts land in `data/external/fonts/`, gitignored, fetched by
  `kyc-nli calibrate-ocr --fetch`.
- **Tesseract with the `hin`, `tam`, `ben`, `urd` and `eng` language packs is a
  hard prerequisite** and must be installed manually — it needs administrator
  rights, which the agent session could not obtain.
- The MIDV-2020 line in `docs/plan.md` M1 is superseded by this record.

## Still worth doing later

MIDV-2020 remains useful for what it can do: it can calibrate the *English* zone
of a real identity document under real capture conditions, which gives a
correction factor between rendered and real degradation for at least one script.
If that factor is large, it is evidence the render-based rates need adjusting for
the others too. That is a smaller, well-scoped follow-up rather than a blocker.
