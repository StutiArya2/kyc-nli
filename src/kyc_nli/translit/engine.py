"""Transliteration engines: native script -> Latin.

Each engine returns a *set* of acceptable Latin renderings, not a single string.
That is the whole point: for every language in the active set the relation is
genuinely one-to-many, and any component that models it as a function will
manufacture false mismatches. The rule baseline consumes these sets; the neural
model does not see them at all, so the comparison stays fair.
"""

from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass

from kyc_nli.schema import Script
from kyc_nli.translit import tables


def _is_arabic(ch: str) -> bool:
    return "؀" <= ch <= "ۿ" or "ﭐ" <= ch <= "﷿"


def _reduce_geminates(text: str) -> str:
    """Collapse doubled consonant digraphs and letters.

    Indic scripts write gemination explicitly but romanisations usually do not:
    முத்து transliterates to MUTHTHU and is written MUTHU. Digraphs are handled
    before single letters so THTH collapses to TH rather than to TTH.
    """
    for digraph in ("TH", "DH", "CH", "SH", "KH", "GH", "PH", "BH", "JH", "ZH"):
        text = text.replace(digraph * 2, digraph)
    out: list[str] = []
    for ch in text:
        if out and out[-1] == ch and ch.isalpha():
            continue
        out.append(ch)
    return "".join(out)


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


# ==========================================================================
# Brahmic abugidas: Devanagari, Tamil, Bengali
# ==========================================================================


@dataclass(frozen=True)
class BrahmicTables:
    """The five tables an abugida transliterator needs."""

    consonants: dict[str, str]
    independent_vowels: dict[str, str]
    vowel_signs: dict[str, str]
    virama: str
    nasals: dict[str, str]
    #: Vowel the bare consonant carries when no sign follows.
    inherent_vowel: str = "A"


class BrahmicTransliterator(Transliterator):
    """Shared machinery for Indic abugidas.

    All three scripts work the same way: a consonant carries an inherent vowel,
    a following vowel sign replaces it, and a virama deletes it. Only the tables
    and the variant-expansion rules differ, so the traversal lives here once.

    Subclasses override ``_expand`` to declare which alternations are legitimate
    for their script. That is where the linguistics goes, and it is the part a
    reviewer will actually interrogate.
    """

    tables: BrahmicTables

    #: Upper bound on the variant set. Each alternation rule can double the set,
    #: so an unbounded expansion is exponential in the number of rules.
    #:
    #: Truncation is a LAST RESORT, not a tuning knob. It is deterministic
    #: (sorted) so results stay reproducible, but sorted-prefix truncation is
    #: alphabetically biased: at 512 it silently dropped BANDYOPADHYAY from
    #: বন্দ্যোপাধ্যায়'s variant set, which is the single most common Bengali
    #: surname romanisation. If a recall test starts failing, RAISE THIS rather
    #: than accept a truncated set -- a baseline handicapped by a cap is not the
    #: strong baseline the comparison needs.
    max_variants: int = 8192

    def __init__(self) -> None:
        # Memoised per engine. The rule baseline calls variants() once per
        # observation per instance, and the expansion is the hot path.
        self._cache: dict[str, set[str]] = {}

    def variants(self, text: str) -> set[str]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        out = {v for v in self._expand({self._transliterate(text)}) if v}
        if len(out) > self.max_variants:
            out = set(sorted(out)[: self.max_variants])
        self._cache[text] = out
        return out

    def _expand(self, seed: set[str]) -> set[str]:
        """Script-specific legitimate alternations. Override in subclasses."""
        return seed

    def _transliterate(self, text: str) -> str:
        t = self.tables
        out: list[str] = []
        chars = list(unicodedata.normalize("NFC", text))
        i = 0
        while i < len(chars):
            ch = chars[i]
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if ch in t.consonants:
                out.append(t.consonants[ch])
                if nxt in t.vowel_signs:
                    out.append(t.vowel_signs[nxt])
                    i += 1
                elif nxt == t.virama:
                    i += 1  # virama suppresses the inherent vowel
                else:
                    out.append(t.inherent_vowel)
            elif ch in t.independent_vowels:
                out.append(t.independent_vowels[ch])
            elif ch in t.nasals:
                out.append(t.nasals[ch])
            elif ch.isspace():
                out.append(" ")
            elif ch.isascii():
                out.append(ch.upper())
            i += 1
        return "".join(out)

    @staticmethod
    def _apply_substitutions(
        seed: set[str], pairs: tuple[tuple[str, str], ...]
    ) -> set[str]:
        """Expand ``seed`` by each alternation, replacing all and one at a time.

        Both are needed. ``str.replace`` rewrites every occurrence, so the Hindi
        A/E alternation turns VARMA into VERME rather than the attested VERMA,
        and the Bengali B/V alternation would rewrite the initial B of বিশ্বাস
        as well as the one that actually alternates. Emitting the
        replace-each-single-occurrence variants alongside the replace-all one
        covers both, at the cost of a larger set -- which ``max_variants``
        bounds.
        """
        out = set(seed)
        for a, b in pairs:
            for v in list(out):
                out.add(v.replace(a, b))
                # Each single occurrence on its own.
                start = 0
                while (idx := v.find(a, start)) != -1:
                    out.add(v[:idx] + b + v[idx + len(a) :])
                    start = idx + 1
        return out

    @staticmethod
    def _drop_final_vowel(seed: set[str], vowel: str = "A") -> set[str]:
        """Schwa deletion, word-final: RAMA is written RAM."""
        return seed | {v[:-1] for v in seed if v.endswith(vowel) and len(v) > 2}

    @staticmethod
    def _delete_medial_schwa(seed: set[str]) -> set[str]:
        """Schwa deletion, word-medial: MEHATA is written MEHTA.

        Indic scripts write the inherent vowel that the spoken language has
        already deleted, so a faithful character-by-character transliteration
        over-generates vowels: सरकार gives SARAKARA where every document says
        SARKAR.

        Which medial schwas actually delete is governed by syllable weight and
        is genuinely hard -- a correct implementation needs a phonological
        model, and it is one of the concrete reasons a lookup-table romaniser
        cannot solve Hindi or Bengali. Rather than approximate the rule badly,
        this over-generates: every medial A is optionally dropped, singly and
        all together. Over-generation is the right failure direction for a
        baseline's *recognition* set -- it costs precision on the fuzzy match,
        never recall.
        """
        out = set(seed)
        for word in list(seed):
            positions = [
                i
                for i, ch in enumerate(word)
                if ch == "A" and 0 < i < len(word) - 1 and word[i - 1].isalpha()
            ]
            if not positions:
                continue
            for i in positions:
                out.add(word[:i] + word[i + 1 :])
            # All at once, which is what fully-reduced spellings look like.
            out.add("".join(c for i, c in enumerate(word) if i not in set(positions)))
        return out


class DevanagariTransliterator(BrahmicTransliterator):
    """Simplified ISO-15919-style Devanagari -> Latin. NON-normative.

    Hindi has no authority fixing the answer, so this engine emits a wide
    variant set (AA/A, EE/I, OO/U, V/W, final schwa present or deleted).
    """

    script = Script.DEVANAGARI
    tables = BrahmicTables(
        consonants=tables.DEVA_CONSONANTS,
        independent_vowels=tables.DEVA_INDEPENDENT_VOWELS,
        vowel_signs=tables.DEVA_VOWEL_SIGNS,
        virama=tables.DEVA_VIRAMA,
        nasals=tables.DEVA_NASALS,
    )

    #: Measured against the attested romanisations in the name pool, not
    #: guessed. Each entry earns its place by fixing a real miss:
    #:   NH/NGH   सिंह is SINGH -- the anusvara is /ŋ/ before a velar
    #:   AU/O     राठौर is RATHORE
    #:   A/E      वर्मा is written both VARMA and VERMA
    _ALTERNATIONS: tuple[tuple[str, str], ...] = (
        ("AA", "A"),
        ("EE", "I"),
        ("OO", "U"),
        ("AU", "O"),
        ("NH", "NGH"),
        ("V", "W"),
        ("SH", "S"),
        ("A", "E"),
    )

    def _expand(self, seed: set[str]) -> set[str]:
        out = self._apply_substitutions(seed, self._ALTERNATIONS)
        out = self._delete_medial_schwa(out)
        out = self._drop_final_vowel(out)
        # PANDE / PANDEY: an optional glide on a final E.
        return out | {v + "Y" for v in out if v.endswith("E")}


class TamilTransliterator(BrahmicTransliterator):
    """Tamil -> Latin. NON-normative and systematically ambiguous.

    Tamil orthography does not mark voicing: one letter is read K or G, CH or S,
    T or D, TH or DH, P or B depending on position. So a single Tamil string has
    several equally correct Latin renderings and the holder's choice is not
    recoverable from the script.

    This is a stronger form of the Hindi argument, and it is the reason Tamil
    earns a place: a lookup table cannot be right here even in principle,
    because there is no single right answer to look up.
    """

    script = Script.TAMIL
    tables = BrahmicTables(
        consonants=tables.TAML_CONSONANTS,
        independent_vowels=tables.TAML_INDEPENDENT_VOWELS,
        vowel_signs=tables.TAML_VOWEL_SIGNS,
        virama=tables.TAML_VIRAMA,
        nasals=tables.TAML_NASALS,
    )

    #: Alternations beyond voicing, each measured against the attested
    #: romanisations in the name pool rather than guessed:
    #:   NGK/NK/NG  வெங்கடேசன் is written VENKATESAN, not VENGKATESAN
    #:   TH/T, DH/D சுந்தரம் is SUNDARAM, not SUNTHARAM
    #:   OO/O, EE/E கோபால் is GOPAL, not GOOPAAL
    _ALTERNATIONS: tuple[tuple[str, str], ...] = (
        ("NGK", "NK"),
        ("NGK", "NG"),
        ("AA", "A"),
        ("EE", "E"),
        ("EE", "I"),
        ("OO", "O"),
        ("OO", "U"),
        ("TH", "T"),
        ("DH", "D"),
        ("ZH", "L"),
        ("V", "W"),
    )

    def _expand(self, seed: set[str]) -> set[str]:
        # Voicing first: this is the script-level ambiguity, not a spelling
        # preference, and it must be applied before anything that rewrites the
        # consonants it produces.
        out = set(seed)
        for voiceless, voiced in tables.TAML_VOICING.items():
            out |= {v.replace(voiceless, voiced) for v in list(out)}
        out = self._apply_substitutions(out, self._ALTERNATIONS)
        out |= {_reduce_geminates(v) for v in out}
        return self._drop_final_vowel(out)


class BengaliTransliterator(BrahmicTransliterator):
    """Bengali -> Latin. NON-normative.

    Bengali's inherent vowel is phonetically nearer /o/ than /a/, and the
    language has no /v/, so the same name appears as BANERJEE or BANARJEE, SEN
    or SHEN, BASU or BOSU, and B alternates with V in Sanskrit-derived names.
    """

    script = Script.BENGALI
    #: Measured against the pool, same discipline as Tamil and Hindi:
    #:   J/Y    য is /dʒ/ medially but the ya-phala /j/ in conjuncts, written
    #:          with the same letter -- without this বন্দ্যোপাধ্যায় romanises
    #:          as BANDJOPADHJAJ rather than the actual BANDYOPADHYAY
    #:   A/O    the inherent vowel is nearer /o/: BASU and BOSU, BANERJEE and
    #:          BONERJEE
    #:   A/U    দত্ত is written DUTTA as often as DATTA
    #:   NGG/NG গঙ্গোপাধ্যায় is GANGOPADHYAY, not GANGGOPADHYAY
    #:   B/V, V/W  Bengali has no /v/, so Sanskrit-derived names alternate
    _ALTERNATIONS: tuple[tuple[str, str], ...] = (
        ("J", "Y"),
        ("NGG", "NG"),
        ("NYJ", "NJ"),
        ("AA", "A"),
        ("EE", "I"),
        ("OO", "U"),
        ("B", "V"),
        ("V", "W"),
        ("SH", "S"),
        ("A", "O"),
        ("A", "U"),
    )
    tables = BrahmicTables(
        consonants=tables.BENG_CONSONANTS,
        independent_vowels=tables.BENG_INDEPENDENT_VOWELS,
        vowel_signs=tables.BENG_VOWEL_SIGNS,
        virama=tables.BENG_VIRAMA,
        nasals=tables.BENG_NASALS,
    )

    def _expand(self, seed: set[str]) -> set[str]:
        out = self._apply_substitutions(seed, self._ALTERNATIONS)
        out = self._delete_medial_schwa(out)
        out = self._drop_final_vowel(out)
        # CHAKRABORTY, BHATTACHARYA: a final I is commonly written Y.
        return out | {v[:-1] + "Y" for v in out if v.endswith("I")}


# ==========================================================================
# Perso-Arabic
# ==========================================================================


class ArabicTransliterator(Transliterator):
    """ICAO Doc 9303 Part 3 Arabic -> Latin, plus attested spelling variants.

    Perso-Arabic script is where romanisation is most visibly set-valued: one
    string maps to Mohammed / Muhammad / Mohamad / Mohamed, all of which appear
    on genuine documents issued to the same person.
    """

    script = Script.ARABIC
    table: dict[str, str] = tables.ICAO_ARABIC

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
        skeleton = self._skeleton(text)
        out = {skeleton}
        for token in skeleton.split():
            for key, expansion in self._ALTERNATIONS:
                if token == key:
                    out.add(skeleton.replace(token, expansion))
        return {v for v in out if v}

    def canonical(self, text: str) -> str:
        """Prefer an attested romanisation over the raw consonant skeleton.

        The base implementation returns ``sorted(variants)[0]``, which for
        Perso-Arabic picks an arbitrary member and frequently lands on the
        vowel-less skeleton (SDYQY rather than SIDDIQUI). A real Indian passport
        prints the attested spelling in its Latin zone, so that is what the
        generator must use as the document's own Latin rendering.
        """
        skeleton = self._skeleton(text)
        attested = sorted(v for v in self.variants(text) if v != skeleton)
        return attested[0] if attested else skeleton

    def _skeleton(self, text: str) -> str:
        return "".join(
            self.table.get(ch, "" if _is_arabic(ch) else ch.upper())
            for ch in unicodedata.normalize("NFC", text)
        ).strip()

    def consonant_skeleton(self, text: str) -> str:
        """Vowel-stripped Latin skeleton: the script-agnostic comparison key."""
        return "".join(c for c in self._skeleton(text) if c not in "AEIOU")


class UrduTransliterator(ArabicTransliterator):
    """Urdu (Perso-Arabic) -> Latin.

    Uses the ICAO Arabic table extended with the letters Urdu adds. The
    extension is not cosmetic: Urdu writes K as U+06A9 and Y as U+06CC rather
    than the Arabic U+0643 and U+064A, so an Arabic-only table drops both
    silently and corrupts most Urdu names without raising an error.

    South Asian Muslim naming also differs from Arabic: compound given names
    (Mohammad Aslam, Abdul Rahman) and honorific surnames (Khan, Sheikh, Ansari)
    dominate, and their romanisations are conventionalised differently.
    """

    script = Script.ARABIC  # same script; a distinct engine for the language
    table = tables.ICAO_URDU

    #: Romanisation lexicon, keyed by the skeleton THIS ENGINE ACTUALLY EMITS.
    #: Derived by running the engine over the name pool rather than written from
    #: intuition -- an entry keyed on a skeleton the engine never produces is
    #: dead weight that silently does nothing, which is how these lexicons rot.
    #: Regenerate with:  scripts/dump_urdu_skeletons.py
    #:
    #: This lexicon is the baseline's advantage and it is meant to be a real
    #: one: production KYC systems match Perso-Arabic names against exactly such
    #: a table. A model that cannot beat it has not earned its place.
    _ALTERNATIONS: tuple[tuple[str, str], ...] = (
        # given names
        ("MHMD", "MOHAMMAD"),
        ("MHMD", "MUHAMMAD"),
        ("MHMD", "MOHD"),        # the abbreviation that appears on real forms
        ("EBDALLH", "ABDULLAH"),
        ("RYHANH", "REHANA"),
        ("FATMH", "FATIMA"),
        ("EAYSHH", "AYESHA"),
        ("EMRAN", "IMRAN"),
        ("NSRYN", "NASREEN"),
        ("ZBYDH", "ZUBAIDA"),
        ("ABRAHYM", "IBRAHIM"),
        ("RDWAN", "RIZWAN"),
        ("SHBANH", "SHABANA"),
        ("NAZYH", "NAZIA"),
        ("FYRWZ", "FEROZ"),
        ("JAWYD", "JAVED"),
        ("SHKYL", "SHAKEEL"),
        ("TBSM", "TABASSUM"),
        ("SLYM", "SALEEM"),
        ("RSHYD", "RASHEED"),
        ("YWSF", "YUSUF"),
        # surnames
        ("SDYQY", "SIDDIQUI"),
        ("ANSARY", "ANSARI"),
        ("SHYKH", "SHEIKH"),
        ("SYD", "SYED"),
        ("SYD", "SAYYED"),
        ("QRYSHY", "QURESHI"),
        ("PTHAN", "PATHAN"),
        ("MLK", "MALIK"),
        ("RDWY", "RIZVI"),
        ("NQWY", "NAQVI"),
        ("HSYN", "HUSSAIN"),
        ("AHMD", "AHMAD"),
        ("AHMD", "AHMED"),
        ("RHMAN", "RAHMAN"),
        ("HASHMY", "HASHMI"),
        ("FARWQY", "FAROOQUI"),
        ("FARWQY", "FAROOQI"),
        ("ETHMANY", "USMANI"),
        ("CHSHTY", "CHISHTI"),
        ("BYG", "BAIG"),
        ("BYG", "BEG"),
        ("MRZA", "MIRZA"),
        ("KHTK", "KHATTAK"),
    )


# ==========================================================================
# Retained but not in the active set (decision 0005)
# ==========================================================================


class CyrillicTransliterator(Transliterator):
    """ICAO Doc 9303 Part 3 Cyrillic -> Latin. Not in the active language set.

    Retained because it is the one script here with a *normative* answer, which
    makes it useful as a contrast condition: it is the case a lookup table
    should win, against which the Indian languages are the case it cannot.
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


class HanTransliterator(Transliterator):
    """Han -> Hanyu Pinyin, emitting both name orders. Not in the active set."""

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
        family, given = syls[0], syls[1:]
        out: set[str] = set()
        for g in {"".join(given), " ".join(given)}:
            if not g:
                out.add(family)
                continue
            out.add(f"{family} {g}")
            out.add(f"{g} {family}")
        return out


# ==========================================================================
# Registry
# ==========================================================================

#: Engines are selected by *language*, not only by script, because Urdu and
#: Arabic share a script but need different tables and alternation sets.
_ENGINE_BY_LANGUAGE: dict[str, type[Transliterator]] = {
    "ur": UrduTransliterator,
    "ar": ArabicTransliterator,
}

_ENGINE_BY_SCRIPT: dict[Script, type[Transliterator]] = {
    Script.LATIN: IdentityTransliterator,
    Script.DEVANAGARI: DevanagariTransliterator,
    Script.TAMIL: TamilTransliterator,
    Script.BENGALI: BengaliTransliterator,
    Script.ARABIC: ArabicTransliterator,
    Script.CYRILLIC: CyrillicTransliterator,
    Script.HAN: HanTransliterator,
}

_ENGINES: dict[tuple[Script, str | None], Transliterator] = {}


def get_transliterator(script: Script, language: str | None = None) -> Transliterator:
    """Cached engine for ``script``, specialised by ``language`` where it matters.

    Pass the language code whenever you have it. Two languages sharing a script
    (Urdu and Arabic) need different tables, and dispatching on script alone
    silently gives Urdu names the Arabic treatment.
    """
    key = (script, language if language in _ENGINE_BY_LANGUAGE else None)
    if key not in _ENGINES:
        cls = _ENGINE_BY_LANGUAGE.get(language or "") or _ENGINE_BY_SCRIPT.get(script)
        if cls is None:
            raise NotImplementedError(f"No transliterator registered for script {script}")
        _ENGINES[key] = cls()
    return _ENGINES[key]
