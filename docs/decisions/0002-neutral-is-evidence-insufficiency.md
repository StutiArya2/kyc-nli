# 0002 — NEUTRAL means evidence insufficiency, not model uncertainty

**Status:** accepted · **Date:** 2026-09-06

## Context

The proposal routes NEUTRAL cases to human review. A reviewer will immediately
ask whether NEUTRAL is a principled semantic category or an abstention threshold
wearing a semantic label. If it is the latter, the three-way formulation
collapses into binary classification plus a confidence cutoff — a solved problem
in the selective-prediction literature, and not a contribution.

## Decision

NEUTRAL is defined as a property of the **premise**: the document does not carry
the evidence needed to adjudicate the hypothesis. Three constructions qualify:
the field is absent from the document type; the field is present but unreadable
and no other zone carries it; the hypothesis is strictly more specific than
anything the document records.

Model confidence never determines a gold label. A hard-to-match cross-script
name pair is ENTAILMENT, however low its string similarity.

## Consequences

- The generator constructs NEUTRAL by *removing* or *destroying* evidence.
- `tests/test_generate.py::test_neutral_instances_are_structurally_neutral`
  fails the build if any NEUTRAL instance carries a legible observation of the
  hypothesised field.
- The rule baseline's own abstention band (the fuzzy-similarity grey zone) is
  deliberately kept, so the comparison directly measures the difference between
  structural neutrality and threshold neutrality.
- If this definition is ever loosened, every dataset generated before the change
  is invalid. Bump the generator version.
