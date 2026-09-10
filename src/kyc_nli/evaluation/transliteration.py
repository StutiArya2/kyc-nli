"""Measure the transliteration engines against real human romanisations.

Until now, engine recall was measured against 40 hand-written pairs per language
that we chose ourselves. That number flatters us by construction: we wrote the
pairs, so of course the engine covers them. Dakshina replaces it with thousands
of romanisations produced by native speakers who had never heard of this project.

Two families of number come out of this, and they answer different questions.

ABOUT THE ENGINE — how much real variation do we cover?
  any_recall    at least one attested human spelling is in our variant set
  top1_recall   the MOST-attested spelling is in our variant set
  spelling_recall  the fraction of all attested spellings we cover

ABOUT THE PROBLEM — how one-to-many is romanisation, really?
  mean_spellings_per_word   measured, not asserted. This is the number that
                            quantifies the phenomenon the whole project is
                            premised on, from data we did not construct.

The second family matters as much as the first. "Romanisation is one-to-many" is
currently an assertion in the proposal supported by three hand-picked examples.
After this it is a measurement with a citation.

Precision matters too: an engine that emits every string in the universe has
perfect recall and is useless, so mean variant-set size is reported alongside.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from kyc_nli.data.corpora import RomanisationEntry
from kyc_nli.languages import load_languages
from kyc_nli.translit import get_transliterator


@dataclass
class TransliterationReport:
    language: str
    n_words: int
    #: Fraction of words where at least one attested spelling is in our set.
    any_recall: float
    #: Fraction where the most-attested spelling is in our set. Stricter, and
    #: closer to what matters: the spelling a holder is most likely to write.
    top1_recall: float
    #: Fraction of all attested spellings covered, across all words.
    spelling_recall: float
    #: Mean size of our variant set. The precision cost of that recall.
    mean_variants: float
    #: Mean distinct human spellings per native word, measured from the corpus.
    #: This is the project's core premise, quantified.
    mean_spellings_per_word: float
    #: Fraction of words with more than one attested spelling.
    multi_spelling_rate: float

    def to_row(self) -> str:
        return (
            f"| {self.language} | {self.n_words} | {self.any_recall:.3f} | "
            f"{self.top1_recall:.3f} | {self.spelling_recall:.3f} | "
            f"{self.mean_variants:.0f} | {self.mean_spellings_per_word:.2f} | "
            f"{self.multi_spelling_rate:.3f} |"
        )


HEADER = (
    "| lang | words | any-recall | top1-recall | spelling-recall | "
    "mean variants | spellings/word | multi-spelling |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- |"
)


def evaluate_transliteration(
    language: str,
    entries: list[RomanisationEntry],
    sample: int | None = 2000,
    seed: int = 20260906,
) -> TransliterationReport:
    """Score one language's engine against its Dakshina romanisations.

    ``sample`` caps the word count: the Brahmic engines expand to hundreds of
    variants per word, so scoring an entire lexicon is slow without changing the
    conclusion. Sampling is seeded, so the number is reproducible.
    """
    spec = load_languages()[language]
    engine = get_transliterator(spec.script, language)

    if sample is not None and len(entries) > sample:
        entries = random.Random(seed).sample(entries, sample)

    any_hits = 0
    top1_hits = 0
    spellings_covered = 0
    spellings_total = 0
    variant_sizes = 0
    multi = 0

    for entry in entries:
        variants = engine.variants(entry.native)
        variant_sizes += len(variants)
        attested = set(entry.romanisations)
        spellings_total += len(attested)
        covered = attested & variants
        spellings_covered += len(covered)
        if covered:
            any_hits += 1
        if entry.primary in variants:
            top1_hits += 1
        if len(attested) > 1:
            multi += 1

    n = len(entries) or 1
    return TransliterationReport(
        language=language,
        n_words=len(entries),
        any_recall=any_hits / n,
        top1_recall=top1_hits / n,
        spelling_recall=spellings_covered / (spellings_total or 1),
        mean_variants=variant_sizes / n,
        mean_spellings_per_word=spellings_total / n,
        multi_spelling_rate=multi / n,
    )
