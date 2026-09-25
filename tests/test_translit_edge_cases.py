"""Degenerate inputs to the transliteration engines, and the language registry.

`tests/test_translit.py` measures whether the engines are *good* -- recall
floors against attested spellings, script-specific alternations. This file asks
the different question of whether they behave sanely on input no linguist would
ever hand them: an empty field, a field of spaces, digits, the wrong script.

That matters because those are exactly the inputs OCR produces. The dominant
Urdu failure mode measured in M1 is the whole word coming back blank, so the
empty string is not an exotic case here -- it is the commonest damaged one.
"""

from __future__ import annotations

import pytest

from kyc_nli.languages import language_codes, load_languages, script_of
from kyc_nli.schema import Script
from kyc_nli.translit import get_transliterator

ACTIVE = language_codes()


def engine(language: str):
    return get_transliterator(script_of(language), language)


# --------------------------------------------------------------------------
# Degenerate inputs
# --------------------------------------------------------------------------


@pytest.mark.parametrize("language", ACTIVE)
def test_an_empty_field_has_exactly_one_rendering_in_every_language(language: str) -> None:
    """It is the empty string, and every engine must agree.

    Four of the five engines used to return the empty *set* here, which a caller
    reads as "no Latin string is an acceptable rendering" rather than "there is
    nothing to render". The rule baseline compares an observed value against
    this set, so the disagreement changed its behaviour by language on the
    commonest OCR-damaged input there is.
    """
    assert engine(language).variants("") == {""}


@pytest.mark.parametrize("language", ACTIVE)
def test_canonical_of_an_empty_field_is_empty_not_an_error(language: str) -> None:
    assert engine(language).canonical("") == ""


@pytest.mark.parametrize("language", ACTIVE)
def test_variants_is_never_empty_for_any_input(language: str) -> None:
    """An engine that returns nothing forces the caller to special-case it, and
    the caller here is a rule that decides whether to reject a human being.

    The awkward member of this list is U+200C, a zero-width non-joiner. M1
    traced the Tamil phantom 0.071 CER floor to that character surviving OCR,
    so a field whose entire content is one is a measured outcome, not a
    hypothetical one -- and it used to romanise to nothing at all.
    """
    for text in ["", " ", "   ", "123", "-", "<<<", "A", "‌", "‌‌"]:
        assert engine(language).variants(text), f"{language} produced nothing for {text!r}"


@pytest.mark.parametrize("language", ACTIVE)
def test_a_real_name_never_falls_back_to_the_empty_rendering(language: str) -> None:
    """The other side of that guarantee. The fallback exists for contentless
    input; a genuine surname reaching it would mean the engine had silently
    stopped generating and nothing else would say so."""
    from kyc_nli.data.name_pools import pool_for

    for native, _ in pool_for(language).surnames:
        assert engine(language).variants(native) != {""}, f"{language}: {native}"


@pytest.mark.parametrize("language", ACTIVE)
def test_digits_pass_through_a_transliterator_unchanged(language: str) -> None:
    """Document numbers reach these engines. Romanising a digit would corrupt a
    field that was already Latin."""
    assert "1234567" in engine(language).variants("1234567")


@pytest.mark.parametrize("language", ACTIVE)
def test_every_rendering_is_uppercase(language: str) -> None:
    """The MRZ is uppercase-only and every comparison downstream assumes it. A
    single lowercase variant is a silent non-match."""
    from kyc_nli.data.name_pools import pool_for

    native = pool_for(language).surnames[0][0]
    for variant in engine(language).variants(native):
        assert variant == variant.upper(), f"{language}: {variant!r}"


@pytest.mark.parametrize("language", ACTIVE)
def test_an_engine_is_a_pure_function_of_its_input(language: str) -> None:
    """Called twice, same answer. Variant generation walks the string with
    accumulating state, which is exactly the shape that leaks between calls."""
    from kyc_nli.data.name_pools import pool_for

    native = pool_for(language).surnames[0][0]
    eng = engine(language)
    assert eng.variants(native) == eng.variants(native)


@pytest.mark.parametrize("language", ACTIVE)
def test_a_long_name_does_not_explode_the_variant_set(language: str) -> None:
    """Variants are combinatorial in the number of ambiguous characters. A cap
    that is too low silently drops the correct spelling -- BANDYOPADHYAY was
    lost that way at 512 -- and no cap at all hangs the generator."""
    from kyc_nli.data.name_pools import pool_for

    pool = pool_for(language)
    longest = max((n for n, _ in pool.surnames + pool.given), key=len)
    assert 0 < len(engine(language).variants(longest)) <= 8192


# --------------------------------------------------------------------------
# Engine dispatch
# --------------------------------------------------------------------------


def test_urdu_and_arabic_share_a_script_but_not_an_engine() -> None:
    """Dispatching on script alone gives Urdu names the Arabic treatment, which
    loses the ye/vao vowel readings that took Urdu recall from 0.086 to 0.303."""
    urdu = get_transliterator(Script.ARABIC, "ur")
    arabic = get_transliterator(Script.ARABIC, "ar")
    assert type(urdu) is not type(arabic)


def test_an_unknown_language_falls_back_to_the_script_engine() -> None:
    """A language code the registry has never seen must not crash a run; the
    script is enough to pick a defensible engine."""
    assert get_transliterator(Script.DEVANAGARI, "mr") is get_transliterator(Script.DEVANAGARI)


def test_an_unregistered_script_fails_by_name() -> None:
    """Better than returning the identity function and silently treating an
    unromanised script as already-Latin."""
    class Fake:
        pass

    with pytest.raises((NotImplementedError, KeyError, TypeError)):
        get_transliterator(Fake())  # type: ignore[arg-type]


def test_engines_are_cached_so_the_tables_are_built_once() -> None:
    assert get_transliterator(Script.TAMIL) is get_transliterator(Script.TAMIL)


# --------------------------------------------------------------------------
# The language registry
# --------------------------------------------------------------------------


def test_the_active_set_is_the_five_scripts_of_the_indian_document_context() -> None:
    assert set(ACTIVE) == {"en", "hi", "ta", "bn", "ur"}


def test_every_language_declares_a_distinct_script() -> None:
    """Two languages on one script is legal -- Urdu and Arabic -- but within the
    active five each script is probed by exactly one language, and a duplicate
    would mean a failure mode is being measured twice and another not at all."""
    scripts = [script_of(code) for code in ACTIVE]
    assert len(set(scripts)) == len(scripts)


def test_every_language_names_the_failure_mode_it_probes() -> None:
    """A language in the set for no stated reason is a language a reviewer will
    ask about and nobody will be able to answer."""
    for spec in load_languages().values():
        assert spec.failure_mode.strip(), spec.code
        assert spec.romanisation.standard.strip(), spec.code


def test_romanisation_normativity_is_three_valued_not_boolean() -> None:
    """Urdu forces this: ICAO fixes the consonants, the script writes no short
    vowels, so the standard constrains the answer without determining it."""
    specs = load_languages()
    assert specs["ur"].romanisation.normative == "partial"
    assert specs["ur"].romanisation.is_normative is False
    assert {s.romanisation.normative for s in specs.values()} <= {"full", "partial", "none"}


def test_a_legacy_boolean_in_a_config_still_loads() -> None:
    """Configs written before decision 0005 used True/False. They must not
    become unloadable, or the old ablations become unreproducible."""
    from kyc_nli.languages import Romanisation

    assert Romanisation(standard="x", normative=True).normative == "full"
    assert Romanisation(standard="x", normative=False).normative == "none"


def test_the_registry_is_read_from_config_not_from_code() -> None:
    """The promise is that a sixth language is a YAML edit. If this file were
    the source of truth, that promise would already be broken."""
    from kyc_nli.languages import repo_root

    assert (repo_root() / "configs" / "languages.yaml").exists()


def test_loading_an_explicit_path_does_not_poison_the_default(tmp_path) -> None:
    """`load_languages` is cached on one slot. A test that loads a fixture
    registry must not leave the rest of the suite looking at it."""
    before = set(load_languages())
    fixture = tmp_path / "languages.yaml"
    fixture.write_text(
        "languages:\n"
        "  - code: xx\n"
        "    name: Test\n"
        "    script: Latn\n"
        "    romanisation: {standard: none, normative: none}\n"
        "    failure_mode: none\n",
        encoding="utf-8",
    )
    assert set(load_languages(fixture)) == {"xx"}
    assert set(load_languages()) == before
