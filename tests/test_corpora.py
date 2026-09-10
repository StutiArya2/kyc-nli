"""Dakshina loader and transliteration-evaluation tests.

Every test here skips cleanly when Dakshina is absent. A clean checkout must have
a green suite without a 2 GB download; anything else makes the test suite a
gatekeeper instead of a safety net.
"""

from __future__ import annotations

import pytest

from kyc_nli.data import corpora
from kyc_nli.data.corpora import RomanisationEntry
from kyc_nli.evaluation.transliteration import evaluate_transliteration

needs_dakshina = pytest.mark.skipif(
    not corpora.is_available(),
    reason="Dakshina not downloaded; run `kyc-nli fetch-dakshina`",
)


# --------------------------------------------------------------------------
# Pure-logic tests: no corpus required.
# --------------------------------------------------------------------------


def test_primary_is_the_most_attested_spelling() -> None:
    """The spelling most annotators wrote, not the first one alphabetically."""
    entry = RomanisationEntry(
        native="शर्मा", romanisations=("SHARMA", "SARMA", "SHARMAA"), counts=(9, 2, 1)
    )
    assert entry.primary == "SHARMA"


def test_primary_falls_back_when_counts_are_missing() -> None:
    entry = RomanisationEntry(native="शर्मा", romanisations=("SHARMA", "SARMA"))
    assert entry.primary == "SHARMA"


def test_evaluation_handles_a_synthetic_lexicon() -> None:
    """Recall arithmetic, checked against a hand-built case with known answers."""
    entries = [
        # Fully covered: the engine emits both spellings.
        RomanisationEntry(native="कुमार", romanisations=("KUMAR", "KUMAAR"), counts=(5, 1)),
        # Not covered at all: no engine emits this.
        RomanisationEntry(native="शर्मा", romanisations=("ZZZZZZ",), counts=(1,)),
    ]
    report = evaluate_transliteration("hi", entries, sample=None)
    assert report.n_words == 2
    assert report.any_recall == pytest.approx(0.5)
    assert report.multi_spelling_rate == pytest.approx(0.5)
    assert report.mean_spellings_per_word == pytest.approx(1.5)
    assert 0.0 < report.spelling_recall < 1.0


def test_evaluation_is_deterministic_under_sampling() -> None:
    entries = [
        RomanisationEntry(native=f"क{i}", romanisations=(f"K{i}",), counts=(1,))
        for i in range(50)
    ]
    a = evaluate_transliteration("hi", entries, sample=10, seed=3)
    b = evaluate_transliteration("hi", entries, sample=10, seed=3)
    assert a == b


# --------------------------------------------------------------------------
# Corpus-backed tests.
# --------------------------------------------------------------------------


@needs_dakshina
@pytest.mark.parametrize("language", corpora.DAKSHINA_LANGUAGES)
def test_lexicons_load_for_every_active_language(language: str) -> None:
    entries = corpora.load_romanisations(language, max_entries=500)
    assert entries, f"no lexicon entries parsed for {language}"
    assert all(e.romanisations for e in entries)
    assert all(e.native for e in entries)


@needs_dakshina
def test_romanisation_really_is_one_to_many() -> None:
    """The project's central premise, checked against data we did not construct.

    If most native words carried exactly one human romanisation, the "a lookup
    table cannot be right" argument would be much weaker and the proposal would
    need rewriting. This asserts the premise holds in real data.
    """
    for language in corpora.DAKSHINA_LANGUAGES:
        entries = corpora.load_romanisations(language, max_entries=3000)
        multi = sum(1 for e in entries if len(e.romanisations) > 1)
        rate = multi / len(entries)
        assert rate > 0.2, (
            f"{language}: only {rate:.1%} of words have more than one attested "
            f"romanisation -- the one-to-many premise may not hold"
        )
