"""Transliteration engines: native script -> Latin.

Each engine returns a *set* of acceptable Latin renderings, not a single string.
That is the whole point: for Arabic and Hindi the relation is genuinely
one-to-many, and any component that models it as a function will manufacture
false mismatches. The rule baseline consumes these sets; the neural model does
not see them at all, so the comparison stays fair.
"""

from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod

from kyc_nli.schema import Script
from kyc_nli.translit import tables


def _is_arabic(ch: str) -> bool:
    return "؀" <= ch <= "ۿ" or "ﭐ" <= ch <= "﷿"


class Transliterator(ABC):
    """Maps a native-script string to the set of plausible Latin renderings."""

    script: Script

    @abstractmethod
    def variants(self, text: str) -> set[str]:
        """All Latin renderings this engine considers acceptable. Uppercase."""

    def canonical(self, text: str) -> str:
        """The single normative rendering, where one exists.

        For non-normative scripts this returns an arbitrary-but-stable member of
        ``variants``; callers that care should check
        ``LanguageSpec.romanisation.normative`` first.
        """
        vs = self.variants(text)
        return sorted(vs)[0] if vs else ""


class IdentityTransliterator(Transliterator):
    """Latin-script source. Romanisation is the identity function."""

    script = Script.LATIN

    def variants(self, text: str) -> set[str]:
        return {text.upper()}


class CyrillicTransliterator(Transliterator):
    """ICAO Doc 9303 Part 3 Cyrillic -> Latin.

    Normative: exactly one correct output. The extra variants returned here are
    the *common wrong* renderings (YU for IU, H for KH, C for TS) that appear on
    real application forms, included so the rule baseline is genuinely strong
    rather than a strawman.
    """

    script = Script.CYRILLIC

    def variants(self, text: str) -> set[str]:
        icao = self._map(text, tables.ICAO_CYRILLIC)
        common = {
            icao,
            icao.replace("IU", "YU").replace("IA", "YA"),
            icao.replace("KH", "H"),
            icao.replace("TS", "C"),
            icao.replace("IU", "YU").replace("IA", "YA").replace("KH", "H"),
        }
        return {v for v in common if v}

    @staticmethod
    def _map(text: str, table: dict[str, str]) -> str:
        out: list[str] = []
        for ch in text:
            up = ch.upper()
            if up in table:
                out.append(table[up])
            elif ch.isspace():
                out.append(" ")
            elif ch == "-":
                out.append("-")
            elif ch.isascii():
                out.append(up)
        return "".join(out)


class ArabicTransliterator(Transliterator):
    """ICAO Doc 9303 Part 3 Arabic -> Latin, plus attested spelling variants.

    Arabic is where romanisation is most visibly set-valued: one Arabic string
    maps to Mohammed / Muhammad / Mohamad / Mohamed, all of which appear on
    genuine documents issued to the same person.
    """

    script = Script.ARABIC

    #: Post-transliteration spelling alternations attested in identity data.
    #: Keys are the ICAO consonant skeleton; values are surface spellings.
    _ALTERNATIONS: tuple[tuple[str, str], ...] = (
        ("MHMD", "MOHAMMED"),
        ("MHMD", "MUHAMMAD"),
        ("MHMD", "MOHAMED"),
        ("AHMD", "AHMED"),
        ("AHMD", "AHMAD"),
        ("ALY", "ALI"),
        ("HSN", "HASSAN"),
        ("HSYN", "HUSSEIN"),
        ("ABDALLH", "ABDULLAH"),
        ("FATMH", "FATIMA"),
        ("KHALD", "KHALID"),
        ("OMR", "OMAR"),
        ("YWSF", "YOUSSEF"),
        ("MRYM", "MARYAM"),
        ("ZYNB", "ZAINAB"),
        ("SARH", "SARAH"),
        ("NWR", "NOUR"),
        ("LYLY", "LAILA"),
        ("IBRAHYM", "IBRAHIM"),
        ("MSTFY", "MUSTAFA"),
    )

    def variants(self, text: str) -> set[str]:
        skeleton = "".join(
            tables.ICAO_ARABIC.get(ch, "" if _is_arabic(ch) else ch.upper())
            for ch in unicodedata.normalize("NFC", text)
        ).strip()
        out = {skeleton}
        for token in skeleton.split():
            for key, expansion in self._ALTERNATIONS:
                if token == key:
                    out.add(skeleton.replace(token, expansion))
        return {v for v in out if v}

    def consonant_skeleton(self, text: str) -> str:
        """Vowel-stripped Latin skeleton: the script-agnostic comparison key."""
        return "".join(c for c in self.canonical(text) if c not in "AEIOU")


class DevanagariTransliterator(Transliterator):
    """Simplified ISO-15919-style Devanagari -> Latin. NON-normative.

    Hindi is the language where no authority fixes the answer, so this engine
    intentionally emits a wide variant set (AA/A, EE/I, OO/U, V/W, final schwa
    present or deleted). If a neural model cannot beat this on Hindi, the
    learned-romanisation argument for NLI is in trouble, which is exactly the
    go/no-go signal we want to surface early.
    """

    script = Script.DEVANAGARI

    def variants(self, text: str) -> set[str]:
        out = {self._transliterate(text)}
        for a, b in (("AA", "A"), ("EE", "I"), ("OO", "U"), ("V", "W"), ("SH", "S")):
            out |= {v.replace(a, b) for v in list(out)}
        # Schwa deletion: Hindi drops the final inherent vowel (RAM, not RAMA).
        out |= {v[:-1] for v in list(out) if v.endswith("A") and len(v) > 2}
        return {v for v in out if v}

    def _transliterate(self, text: str) -> str:
        out: list[str] = []
        chars = list(unicodedata.normalize("NFC", text))
        i = 0
        while i < len(chars):
            ch = chars[i]
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if ch in tables.DEVA_CONSONANTS:
                out.append(tables.DEVA_CONSONANTS[ch])
                if nxt in tables.DEVA_VOWEL_SIGNS:
                    out.append(tables.DEVA_VOWEL_SIGNS[nxt])
                    i += 1
                elif nxt == tables.DEVA_VIRAMA:
                    i += 1  # virama suppresses the inherent vowel
                else:
                    out.append("A")  # inherent vowel
            elif ch in tables.DEVA_INDEPENDENT_VOWELS:
                out.append(tables.DEVA_INDEPENDENT_VOWELS[ch])
            elif ch in tables.DEVA_NASALS:
                out.append(tables.DEVA_NASALS[ch])
            elif ch.isspace():
                out.append(" ")
            elif ch.isascii():
                out.append(ch.upper())
            i += 1
        return "".join(out)


class HanTransliterator(Transliterator):
    """Han -> Hanyu Pinyin, emitting both name orders.

    Chinese produces the mirror image of the Arabic error: romanisation collapses
    distinct names onto the same Pinyin, so the risk is a false *match*. The
    variant set includes surname-first and surname-last, spaced and unspaced,
    because all four appear across MRZ and form data.
    """

    script = Script.HAN

    def __init__(self) -> None:
        self._pypinyin = None
        try:  # optional dependency: pip install -e ".[translit]"
            import pypinyin  # type: ignore[import-not-found]

            self._pypinyin = pypinyin
        except ImportError:
            pass

    def syllables(self, text: str) -> list[str]:
        cleaned = [c for c in text if not c.isspace()]
        if self._pypinyin is not None:
            joined = "".join(cleaned)
            style = self._pypinyin.Style.NORMAL
            return [s[0].upper() for s in self._pypinyin.pinyin(joined, style=style)]
        return [tables.PINYIN_MINIMAL.get(c, c) for c in cleaned]

    def variants(self, text: str) -> set[str]:
        syls = [s for s in self.syllables(text) if s]
        if not syls:
            return set()
        # Convention: the first character of a Han name is the family name.
        family, given = syls[0], syls[1:]
        out: set[str] = set()
        for g in {"".join(given), " ".join(given)}:
            if not g:
                out.add(family)
                continue
            out.add(f"{family} {g}")  # family-first, as in the PRC MRZ
            out.add(f"{g} {family}")  # given-first, as typed on Western forms
        return out


_ENGINE_CLASSES: dict[Script, type[Transliterator]] = {
    Script.LATIN: IdentityTransliterator,
    Script.CYRILLIC: CyrillicTransliterator,
    Script.ARABIC: ArabicTransliterator,
    Script.DEVANAGARI: DevanagariTransliterator,
    Script.HAN: HanTransliterator,
}

_ENGINES: dict[Script, Transliterator] = {}


def get_transliterator(script: Script) -> Transliterator:
    """Cached engine for ``script``."""
    if script not in _ENGINES:
        cls = _ENGINE_CLASSES.get(script)
        if cls is None:
            raise NotImplementedError(f"No transliterator registered for script {script}")
        _ENGINES[script] = cls()
    return _ENGINES[script]
