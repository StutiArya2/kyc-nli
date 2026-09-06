# 0004 — OCR noise is simulated, and must be calibrated before publication

**Status:** accepted, with an open obligation · **Date:** 2026-09-06

## Context

The revised central claim (see `docs/plan.md`) is that a learned model beats a
rule engine **under OCR corruption**. Every number supporting that claim is
therefore conditional on the corruption model being a fair proxy for real OCR.

The current model is hand-built: per-script confusion sets derived from
documented failure modes (Latin 0/O and 1/I, Cyrillic cross-script homoglyphs,
Arabic dot-count and diacritic loss, Devanagari matra loss). It has NOT been
estimated from a real OCR engine's output.

## Decision

Simulate rather than run a real engine, **for now**, because the pilot needs
controlled noise: to claim robustness we must hold everything else fixed, vary
only the corruption rate, and know exactly which character was corrupted. A real
engine gives none of that, and it also gives no ground truth for error analysis.

The obligation this creates is explicit: **before any noise-conditioned number
appears in the paper, the confusion sets must be replaced with rates measured
from a real engine (Tesseract and/or EasyOCR) on MIDV-2020 crops, per script.**

## Consequences

- Milestone M1 in the plan, and the identified single point of failure.
- Until M1 lands, the *direction* of the Phase-0 finding (rule engine at ceiling
  when clean, degrading under noise) may be cited; the *magnitude* may not.
- If measured CER differs from the simulated rate by more than roughly 2x, the
  Phase-0 numbers get regenerated and the plan's table is rewritten.
- Fallback if calibration proves expensive: the calibration itself — a per-script
  OCR error characterisation for identity documents — is a publishable
  contribution on its own.
