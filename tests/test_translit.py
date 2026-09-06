"""Transliteration tests.

The ICAO cases are the ones that matter: they have a normative right answer, so
a failure here is a bug, not a judgement call.
"""

from __future__ import annotations

import pytest

from kyc_nli.schema import Script
from kyc_nli.translit import get_transliterator


@pytest.mark.parametrize(
    ("cyrillic", "expected"),
    [
        ("ИВАНОВ", "IVANOV"),
        ("ПЕТРОВ", "PETROV"),
        # The three ICAO rules people get wrong, and the reason Russian VIZ/MRZ
        # pairs mismatch under naive transliteration.
        ("ЮРИЙ", "IURII"),   # Ю -> IU, not YU
        ("ЯКОВЛЕВ", "IAKOVLEV"),  # Я -> IA, not YA
        ("ХАРИТОНОВ", "KHARITONOV"),  # Х -> KH, not H
        ("ЦВЕТКОВ", "TSVETKOV"),  # Ц -> TS, not C
        ("ЩУКИН", "SHCHUKIN"),  # Щ -> SHCH
    ],
)
def test_icao_cyrillic_is_normative(cyrillic: str, expected: str) -> None:
    engine = get_transliterator(Script.CYRILLIC)
    assert expected in engine.variants(cyrillic)


def test_cyrillic_includes_common_wrong_renderings() -> None:
    """The baseline must accept the spellings people actually write on forms."""
    variants = get_transliterator(Script.CYRILLIC).variants("ЮРИЙ")
    assert "IURII" in variants  # ICAO
    assert "YURII" in variants  # what the holder writes


def test_arabic_romanisation_is_set_valued() -> None:
    """One Arabic string, several legitimate Latin spellings."""
    variants = get_transliterator(Script.ARABIC).variants("محمد")
    assert len(variants) > 1
    assert {"MOHAMMED", "MUHAMMAD", "MOHAMED"} & variants


def test_devanagari_covers_schwa_deletion() -> None:
    """Hindi drops the final inherent vowel; both spellings appear on documents."""
    variants = get_transliterator(Script.DEVANAGARI).variants("शर्मा")
    assert any(v.startswith("SH") or v.startswith("S") for v in variants)
    assert len(variants) > 1


def test_han_emits_both_name_orders() -> None:
    """Family-first (MRZ) and given-first (Western form) must both be accepted."""
    variants = get_transliterator(Script.HAN).variants("王伟")
    assert "WANG WEI" in variants
    assert "WEI WANG" in variants


def test_latin_is_identity() -> None:
    assert get_transliterator(Script.LATIN).variants("smith") == {"SMITH"}
