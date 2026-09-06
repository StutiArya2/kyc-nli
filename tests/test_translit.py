"""Transliteration tests.

Structure mirrors the argument the project makes. For each language, the test
asserts the property that language is in the set to demonstrate:

  en  identity
  hi  wide non-normative variant set
  ta  voicing is not recoverable from the script
  bn  inherent-vowel and ya-phala alternations
  ur  consonant skeleton plus a romanisation lexicon
  ru  a NORMATIVE table exists (retained, not in the active set) -- the contrast
      case a lookup table should win
"""

from __future__ import annotations

import pytest

from kyc_nli.data.name_pools import POOLS
from kyc_nli.languages import load_languages
from kyc_nli.schema import Script
from kyc_nli.translit import get_transliterator

# --------------------------------------------------------------------------
# The property every language must satisfy: the attested Latin form printed on
# the document must be recognised as a legitimate variant of the native form.
# If this fails, the rule baseline is being handed an unwinnable task and any
# comparison against it is meaningless.
# --------------------------------------------------------------------------


#: Measured recall floors, one per language. These are REGRESSION GUARDS set a
#: little below what the engine currently achieves (en 100, hi 90, ta 92,
#: bn 100, ur 98) -- not targets, and not numbers to relax when a test fails.
#:
#: The residual is a finding, not a defect to tune away. Even with a generous
#: alternation set, medial schwa deletion and a romanisation lexicon, the
#: rule-based romaniser still misses attested spellings that require schwa
#: *epenthesis* (अग्रवाल -> AGARWAL), diphthong monophthongisation
#: (नायर -> NAIR) or Grantha conjunct handling (லட்சுமி -> LAKSHMI). Closing
#: those by adding per-name rules would be fitting the baseline to the test
#: pool, which is the methodological error CLAUDE.md warns against.
RECALL_FLOOR: dict[str, float] = {
    "en": 1.00,
    "hi": 0.85,
    "ta": 0.88,
    "bn": 0.95,
    "ur": 0.95,
}


@pytest.mark.parametrize("language", sorted(load_languages()))
def test_attested_romanisation_recall(language: str) -> None:
    """The romanisation printed on the document must be a recognised variant.

    If this drops, the rule baseline is being handed a task it cannot win and
    any comparison against it stops meaning anything.
    """
    pool = POOLS[language]
    engine = get_transliterator(pool.script, language)
    entries = pool.surnames + pool.given
    unrecognised = [
        (native, latin)
        for native, latin in entries
        if latin not in engine.variants(native)
    ]
    recall = 1 - len(unrecognised) / len(entries)
    assert recall >= RECALL_FLOOR[language], (
        f"{language}: recall {recall:.0%} below the {RECALL_FLOOR[language]:.0%} "
        f"floor; {len(unrecognised)}/{len(entries)} attested romanisations are "
        f"not in the variant set, e.g. {unrecognised[:5]}"
    )


def test_variant_sets_stay_bounded() -> None:
    """Expansion is exponential in the rule count; the cap must not be hit.

    A hit cap means silent truncation, and truncation is alphabetically biased:
    at 512 it dropped BANDYOPADHYAY, the commonest Bengali surname spelling.
    """
    for language, pool in POOLS.items():
        engine = get_transliterator(pool.script, language)
        cap = getattr(engine, "max_variants", None)
        if cap is None:
            continue
        for native, _ in pool.surnames + pool.given:
            assert len(engine.variants(native)) < cap, (
                f"{language}: {native!r} saturated the variant cap ({cap}); "
                f"raise max_variants rather than accept a truncated set"
            )


# --------------------------------------------------------------------------
# Per-language properties
# --------------------------------------------------------------------------


def test_latin_is_identity() -> None:
    assert get_transliterator(Script.LATIN, "en").variants("smith") == {"SMITH"}


def test_hindi_emits_a_wide_variant_set() -> None:
    """No authority fixes Hindi romanisation, so the engine must over-generate."""
    variants = get_transliterator(Script.DEVANAGARI, "hi").variants("शर्मा")
    assert len(variants) > 3
    assert "SHARMA" in variants


def test_hindi_covers_schwa_deletion() -> None:
    """Hindi drops the final inherent vowel; both spellings appear on documents."""
    variants = get_transliterator(Script.DEVANAGARI, "hi").variants("कुमार")
    assert "KUMAR" in variants


def test_tamil_voicing_is_not_recoverable_from_the_script() -> None:
    """The property that earns Tamil its place in the set.

    Tamil orthography does not mark voicing, so க is K or G with equal
    legitimacy. Both must be in the variant set: a romaniser that picks one is
    wrong half the time and has no way to know which half.
    """
    variants = get_transliterator(Script.TAMIL, "ta").variants("கண்ணன்")
    assert "KANNAN" in variants
    assert "GANNAN" in variants


def test_tamil_recognises_attested_forms_across_voicing() -> None:
    """Both members of a voicing pair must be reachable from one Tamil string."""
    engine = get_transliterator(Script.TAMIL, "ta")
    assert "SUBRAMANIYAN" in engine.variants("சுப்ரமணியன்")
    assert "GOPAL" in engine.variants("கோபால்")
    assert "NATARAJAN" in engine.variants("நடராஜன்")


def test_bengali_ya_phala_alternation() -> None:
    """য is /dʒ/ medially but the ya-phala /j/ in conjuncts, same letter.

    Without the J/Y alternation বন্দ্যোপাধ্যায় romanises as BANDJOPADHJAJ
    instead of the actual BANDYOPADHYAY, which no Bengali document has ever
    printed.
    """
    variants = get_transliterator(Script.BENGALI, "bn").variants("বন্দ্যোপাধ্যায়")
    assert "BANDYOPADHYAY" in variants


def test_bengali_inherent_vowel_alternation() -> None:
    """A/O alternation: BASU and BOSU are the same name."""
    variants = get_transliterator(Script.BENGALI, "bn").variants("বসু")
    assert {"BASU", "BOSU"} <= variants


def test_urdu_uses_its_own_kaf_and_ye_not_the_arabic_ones() -> None:
    """Urdu writes K as U+06A9 and Y as U+06CC.

    An Arabic-only table drops both silently -- no error, just a corrupted name.
    This test is the guard against that regression.
    """
    engine = get_transliterator(Script.ARABIC, "ur")
    assert "KHAN" in engine.variants("خان")          # contains U+06A9
    assert engine.variants("شیخ") != {"SH"}          # contains U+06CC
    assert "SHEIKH" in engine.variants("شیخ")


def test_urdu_romanisation_is_set_valued() -> None:
    """One Perso-Arabic skeleton, several legitimate Latin spellings."""
    variants = get_transliterator(Script.ARABIC, "ur").variants("محمد")
    assert {"MOHAMMAD", "MUHAMMAD", "MOHD"} <= variants


def test_urdu_canonical_prefers_attested_over_skeleton() -> None:
    """The document prints SIDDIQUI, never the vowel-less skeleton SDYQY."""
    engine = get_transliterator(Script.ARABIC, "ur")
    assert engine.canonical("صدیقی") == "SIDDIQUI"


def test_urdu_and_arabic_get_different_engines_for_the_same_script() -> None:
    """Dispatching on script alone would give Urdu the Arabic treatment."""
    urdu = get_transliterator(Script.ARABIC, "ur")
    arabic = get_transliterator(Script.ARABIC, "ar")
    assert type(urdu) is not type(arabic)


# --------------------------------------------------------------------------
# Retained, not in the active set: the normative contrast case.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cyrillic", "expected"),
    [
        ("ИВАНОВ", "IVANOV"),
        ("ЮРИЙ", "IURII"),        # Ю -> IU, not YU
        ("ЯКОВЛЕВ", "IAKOVLEV"),  # Я -> IA, not YA
        ("ХАРИТОНОВ", "KHARITONOV"),
        ("ЦВЕТКОВ", "TSVETKOV"),
        ("ЩУКИН", "SHCHUKIN"),
    ],
)
def test_icao_cyrillic_is_normative(cyrillic: str, expected: str) -> None:
    """Kept as the contrast condition: the one script with a right answer."""
    assert expected in get_transliterator(Script.CYRILLIC, "ru").variants(cyrillic)


def test_han_emits_both_name_orders() -> None:
    variants = get_transliterator(Script.HAN, "zh").variants("王伟")
    assert {"WANG WEI", "WEI WANG"} <= variants
