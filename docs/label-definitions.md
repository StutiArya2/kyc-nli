# Label definitions

This is the ground truth for annotation. If an annotator disagrees with a gold
label, this document is what settles it. Changing anything here invalidates
every dataset generated before the change — bump the generator version and say
so in the manifest.

## The task

Given a **premise** (the set of field values physically observable on an
identity document, across zones, in whatever scripts and formats they appear)
and a **hypothesis** (a single assertion about the holder, typically taken from
an onboarding form), assign one of three labels.

## ENTAILMENT

The document's evidence, correctly interpreted, supports the hypothesis.

"Correctly interpreted" is doing the work. It covers:

- **Cross-script equivalence.** VIZ `ИВАНОВ` entails "surname is IVANOV",
  because ICAO Doc 9303 Part 3 fixes that transliteration and the MRZ on the
  same document carries it.
- **Non-normative romanisation.** VIZ `شرما` entails "surname is SHARMA" and
  also "surname is SHARMAA", because Arabic and Hindi romanisation is genuinely
  one-to-many. All members of the accepted variant set entail.
- **Format variance.** MRZ `900312` entails "born on 1990-03-12".
- **Name-order variance.** Han `王伟` entails both "WANG WEI" and "WEI WANG".
- **Surviving OCR corruption.** If the underlying printed string entails the
  hypothesis and OCR corrupted a character, the label stays ENTAILMENT. The
  gold label describes the *document*, not the scan.

### Worked examples

| Premise (relevant zone) | Hypothesis | Label | Why |
| --- | --- | --- | --- |
| VIZ `ЮРИЙ` (Cyrl), MRZ `IURII` | "The holder's given names are YURI." | ENTAILMENT | `YURI` is an attested romanisation; `IURII` is the ICAO form of the same string. Zero shared characters with the VIZ is irrelevant. |
| MRZ `900312`, VIZ `12 MAR 1990` | "The holder was born on 1990-03-12." | ENTAILMENT | Two zones, two formats, one date. |

## CONTRADICTION

The document's evidence, correctly interpreted, refutes the hypothesis. Two
sub-cases, and both must be present in any credible dataset:

1. **Direct refutation.** The document legibly states a different value.
2. **Joint impossibility.** Every field is individually well-formed but the
   combination cannot exist: a 40-year validity period, a birth date after the
   issue date, an issue date preceding the document template's introduction.

### Worked examples

| Premise | Hypothesis | Label | Why |
| --- | --- | --- | --- |
| VIZ + MRZ both carry `1990-03-12` | "The holder was born on 1990-03-13." | CONTRADICTION | Legible, consistent, and different. |
| Issue `1995-06-02`, expiry `2035-06-02`, template `2020-polycarbonate` | "The document expires on 2035-06-02." | CONTRADICTION | 40-year validity, and a 1995 issue date on a template introduced in 2020. Neither field is individually invalid. |

## NEUTRAL — the definition everything turns on

**NEUTRAL means the premise lacks the evidence to adjudicate the hypothesis.**
It is a property of the document, not of the model.

This is the project's central definitional commitment, and it exists because the
obvious alternative is indefensible. If NEUTRAL were "the model isn't sure", it
would be a confidence threshold wearing a semantic label, and the three-way
formulation would collapse into binary classification plus abstention — which
is a solved problem in the selective-prediction literature and not a
contribution.

A hypothesis is NEUTRAL when, and only when:

- **The field is absent from the document type.** A passport MRZ does not carry
  place of birth. A claim about place of birth against an MRZ-only premise is
  structurally undecidable.
- **The field is present but unreadable**, and no other zone carries it. The
  document has the answer; this scan does not.
- **The hypothesis is strictly more specific than the document.** The document
  says `MOHAMMED AL-ANSARI`; the hypothesis asserts a middle name the document
  never records. Compatible, unconfirmed.

A hypothesis is **not** NEUTRAL merely because matching is hard. `ЮРИЙ` versus
`YURI` is ENTAILMENT, however low the string similarity.

### Worked examples

| Premise | Hypothesis | Label | Why |
| --- | --- | --- | --- |
| MRZ only; no VIZ captured | "The holder was born in CAIRO." | NEUTRAL | The MRZ has no place-of-birth field. Nothing in the premise bears on the claim. |
| VIZ surname reads `???????`, conf. 0.05; MRZ surname absent | "The holder's surname is SHARMA." | NEUTRAL | The evidence exists on the document but not in this observation. Route to human review. |

### The boundary everybody gets wrong

**CONTRADICTION vs NEUTRAL** is the distinction that separates a real three-way
system from a two-way system with a reject option:

> Contradiction requires *positive evidence against*. Absence of evidence is
> never contradiction.

A blank field is NEUTRAL. A field reading something else is CONTRADICTION. A
field too corrupted to read is NEUTRAL, even if what survives looks different
from the claim — because "looks different" after corruption is not evidence.

## Consequences for the dataset

Every NEUTRAL instance in the generated benchmark is constructed by *removing*
or *destroying* evidence, never by picking hard cases. `test_generate.py`
asserts this: a NEUTRAL instance carrying a legible observation of the
hypothesised field is a bug that fails the test suite.

## Annotation protocol (for the human-labelled subset)

Not yet run. When it is: two independent annotators per instance, a third for
adjudication, Cohen's kappa reported per class and per language. Target
kappa > 0.75 overall and > 0.65 on NEUTRAL, which will be the hardest.
Anything below that means this document is not clear enough and must be
rewritten before labelling continues.
