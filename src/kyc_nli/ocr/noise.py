"""Script-aware OCR corruption model.

Why simulate rather than run a real OCR engine: we need *controlled* noise. To
claim "the NLI model is robust to OCR error" we must be able to hold everything
else fixed and vary only the corruption rate, and we must know exactly which
character was corrupted so an error analysis is possible. A real OCR engine
gives neither.

The confusion sets below are script-specific because OCR failure modes are
script-specific. Latin OCR confuses 0/O and 1/I; Cyrillic OCR additionally
confuses *homoglyphs across scripts* (Cyrillic А U+0410 versus Latin A U+0041),
which is invisible to a human reader and catastrophic for exact matching;
Arabic OCR drops diacritics and confuses letters distinguished only by dot
count; Devanagari OCR drops matras and confuses conjuncts.

Validation status: these confusion sets are hand-built from the documented
failure modes of the corresponding scripts, NOT estimated from a real OCR
engine's output. Before the noise model appears in a results table it must be
calibrated against a real engine on MIDV-2020 crops. Tracked in
docs/decisions/0004-ocr-noise-is-simulated.md.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass, field

from kyc_nli.schema import Script

# --------------------------------------------------------------------------
# Character-level confusion sets, per script.
# --------------------------------------------------------------------------

LATIN_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "0": ("O", "D", "Q"),
    "O": ("0", "Q", "D"),
    "1": ("I", "L", "7"),
    "I": ("1", "L", "J"),
    "L": ("1", "I"),
    "5": ("S", "6"),
    "S": ("5", "8"),
    "8": ("B", "3", "6"),
    "B": ("8", "R"),
    "2": ("Z", "7"),
    "Z": ("2", "7"),
    "6": ("G", "5", "8"),
    "G": ("6", "C"),
    "7": ("1", "T"),
    "T": ("7", "I"),
    "M": ("N", "H"),
    "N": ("M", "H"),
    "U": ("V", "O"),
    "V": ("U", "Y"),
    "C": ("G", "O"),
    "E": ("F", "B"),
    "F": ("E", "P"),
    "K": ("X", "R"),
    "R": ("P", "B", "K"),
}

#: Cross-script homoglyphs. These are the dangerous ones: the rendered glyphs
#: are identical, so a corrupted string is visually indistinguishable from the
#: original but compares unequal under any byte-level test.
CYRILLIC_HOMOGLYPHS: dict[str, str] = {
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X",
}

CYRILLIC_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "И": ("Й", "Н"),
    "Й": ("И",),
    "Ш": ("Щ", "Ц"),
    "Щ": ("Ш",),
    "Ц": ("Ш", "Н"),
    "Ь": ("Ъ", "Б"),
    "Ъ": ("Ь",),
    "Б": ("Ь", "В"),
    "Г": ("Т", "П"),
    "П": ("Н", "Г"),
    "З": ("Э", "В"),
    "Э": ("З", "О"),
    "Ф": ("Ю",),
    "Ю": ("Ф", "Н"),
    "Я": ("Л", "А"),
    "Л": ("Я", "А"),
    "Д": ("Л", "А"),
    "Ж": ("Х",),
    "Ч": ("У", "Н"),
}

#: Arabic letters distinguished only by dots (i'jam). OCR at document
#: resolution loses dots constantly, and losing a dot changes the letter.
ARABIC_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "ب": ("ت", "ث", "ن", "ي"),
    "ت": ("ب", "ث", "ن"),
    "ث": ("ت", "ب"),
    "ن": ("ب", "ت", "ي"),
    "ي": ("ب", "ن", "ى"),
    "ى": ("ي", "ا"),
    "ج": ("ح", "خ"),
    "ح": ("ج", "خ"),
    "خ": ("ح", "ج"),
    "د": ("ذ", "ر"),
    "ذ": ("د",),
    "ر": ("ز", "د"),
    "ز": ("ر",),
    "س": ("ش",),
    "ش": ("س",),
    "ص": ("ض",),
    "ض": ("ص",),
    "ط": ("ظ",),
    "ظ": ("ط",),
    "ع": ("غ",),
    "غ": ("ع",),
    "ف": ("ق",),
    "ق": ("ف",),
    "ة": ("ه", "ت"),
    "ه": ("ة",),
    "أ": ("ا", "إ"),
    "إ": ("ا", "أ"),
    "ا": ("أ", "إ"),
}

#: Arabic harakat and tatweel: dropped by OCR far more often than misread.
ARABIC_DROPPABLE = "ًٌٍَُِّْـ"

#: Devanagari vowel signs (matras). Thin strokes, dropped or swapped often.
DEVANAGARI_CONFUSIONS: dict[str, tuple[str, ...]] = {
    "ा": ("", "ो"),
    "ि": ("ी", ""),
    "ी": ("ि", ""),
    "ु": ("ू", ""),
    "ू": ("ु", ""),
    "े": ("ै", ""),
    "ै": ("े",),
    "ो": ("ौ", "ा"),
    "ौ": ("ो",),
    "ं": ("", "ँ"),
    "ँ": ("ं", ""),
    "भ": ("म", "ग"),
    "म": ("भ",),
    "ध": ("घ", "द"),
    "घ": ("ध",),
    "ब": ("व",),
    "व": ("ब",),
    "ट": ("ठ",),
    "ठ": ("ट",),
    "ड": ("ङ", "उ"),
    "श": ("ष", "स"),
    "ष": ("श",),
    "स": ("श",),
}

_CONFUSION_BY_SCRIPT: dict[Script, dict[str, tuple[str, ...]]] = {
    Script.LATIN: LATIN_CONFUSIONS,
    Script.CYRILLIC: CYRILLIC_CONFUSIONS,
    Script.ARABIC: ARABIC_CONFUSIONS,
    Script.DEVANAGARI: DEVANAGARI_CONFUSIONS,
    Script.HAN: {},  # Han OCR fails by whole-character substitution, handled below
}


@dataclass
class NoiseConfig:
    """Corruption rates. All are per-character probabilities unless noted.

    The defaults correspond to a "moderate" setting: roughly one corrupted
    character in a 12-character surname, which is in the range reported for
    mobile-captured identity documents.
    """

    substitution_rate: float = 0.08
    deletion_rate: float = 0.01
    insertion_rate: float = 0.01
    #: Probability of swapping a character for its cross-script homoglyph.
    #: Applies to Cyrillic only. Kept separate because it is the single most
    #: important failure mode for the exact-match baseline and we want to be
    #: able to switch it on and off independently in ablations.
    homoglyph_rate: float = 0.05
    #: Probability of dropping an Arabic diacritic when one is present.
    diacritic_drop_rate: float = 0.7
    #: Probability of losing whitespace between name tokens.
    space_collapse_rate: float = 0.05
    #: Characters never corrupted, e.g. the MRZ filler.
    protected: str = "<"

    #: Populated at runtime with the edits actually applied, for error analysis.
    applied: list[str] = field(default_factory=list)


class OCRNoiser:
    """Applies script-aware character corruption to a string.

    Deterministic given a seed, which is required: every generated instance must
    be reproducible from its config plus its seed.
    """

    def __init__(self, config: NoiseConfig | None = None, seed: int | None = None) -> None:
        self.config = config or NoiseConfig()
        self.rng = random.Random(seed)

    def corrupt(self, text: str, script: Script) -> tuple[str, list[str]]:
        """Return ``(corrupted_text, list_of_edit_descriptions)``.

        The edit list is what makes error analysis possible: it says exactly
        which character at which index became which other character.
        """
        cfg = self.config
        edits: list[str] = []
        out: list[str] = []

        for idx, ch in enumerate(text):
            if ch in cfg.protected:
                out.append(ch)
                continue

            if script is Script.ARABIC and ch in ARABIC_DROPPABLE:
                if self.rng.random() < cfg.diacritic_drop_rate:
                    edits.append(f"{idx}:drop_diacritic:{_name(ch)}")
                    continue
                out.append(ch)
                continue

            if ch.isspace():
                if self.rng.random() < cfg.space_collapse_rate:
                    edits.append(f"{idx}:collapse_space")
                    continue
                out.append(ch)
                continue

            if self.rng.random() < cfg.deletion_rate:
                edits.append(f"{idx}:delete:{ch}")
                continue

            replacement = self._substitute(ch, script)
            if replacement is not None:
                kind = "homoglyph" if _is_homoglyph_swap(ch, replacement) else "substitute"
                edits.append(f"{idx}:{kind}:{ch}->{replacement}")
                out.append(replacement)
            else:
                out.append(ch)

            if self.rng.random() < cfg.insertion_rate:
                extra = self._random_char_like(ch, script)
                if extra:
                    edits.append(f"{idx}:insert:{extra}")
                    out.append(extra)

        return "".join(out), edits

    def _substitute(self, ch: str, script: Script) -> str | None:
        cfg = self.config

        if (
            script is Script.CYRILLIC
            and ch.upper() in CYRILLIC_HOMOGLYPHS
            and self.rng.random() < cfg.homoglyph_rate
        ):
            return CYRILLIC_HOMOGLYPHS[ch.upper()]

        if script is Script.HAN:
            # Han OCR substitutes a visually similar but semantically unrelated
            # character. Without a glyph-similarity index we cannot model which
            # one, so we corrupt to a neighbouring codepoint and record it.
            if self.rng.random() < cfg.substitution_rate and "一" <= ch <= "鿿":
                return chr(ord(ch) + self.rng.choice((-2, -1, 1, 2)))
            return None

        table = _CONFUSION_BY_SCRIPT.get(script, {})
        options = table.get(ch) or table.get(ch.upper())
        if not options:
            return None
        if self.rng.random() >= cfg.substitution_rate:
            return None
        choice = self.rng.choice(options)
        if not choice:
            return None
        return choice if ch.isupper() or not ch.isalpha() else choice.lower()

    def _random_char_like(self, ch: str, script: Script) -> str:
        table = _CONFUSION_BY_SCRIPT.get(script, {})
        options = table.get(ch) or table.get(ch.upper())
        if options:
            picked = self.rng.choice(options)
            if picked:
                return picked
        return ch


def _is_homoglyph_swap(original: str, replacement: str) -> bool:
    return CYRILLIC_HOMOGLYPHS.get(original.upper()) == replacement


def _name(ch: str) -> str:
    try:
        return unicodedata.name(ch)
    except ValueError:
        return f"U+{ord(ch):04X}"


# --------------------------------------------------------------------------
# Presets
# --------------------------------------------------------------------------

try:  # generated by `kyc-nli calibrate-ocr --write-tables`
    from kyc_nli.ocr.measured import MEASURED_CONFUSIONS, MEASURED_RATES

    _CALIBRATED = True
except ImportError:  # pragma: no cover - clean checkout before calibration
    MEASURED_CONFUSIONS, MEASURED_RATES = {}, {}
    _CALIBRATED = False


def is_calibrated() -> bool:
    """True when the measured tables from milestone M1 are present."""
    return _CALIBRATED


#: Named presets for the noise-level ablation.
#:
#: THESE ARE NOW MEASURED, not hand-built. Decision 0004 promised that no
#: noise-conditioned number would appear in the paper until they were, and
#: milestone M1 discharged it.
#:
#: The correction was not small, and it was not only a matter of scale. The
#: hand-built model made SUBSTITUTION the dominant error, roughly 8x more likely
#: than deletion. Measured Tesseract output on Indic scripts is the other way
#: round: deletion runs about 1.8x substitution at every level, and the
#: hand-built deletion rate was 10-17x too low. The shape of the noise was
#: wrong, not just its size.
#:
#:   level          measured sub / del / ins      hand-built (wrong)
#:   clean          0.000 / 0.000 / 0.000         same
#:   light          0.008 / 0.025 / 0.001         0.030 / 0.005 / 0.005
#:   moderate       0.096 / 0.170 / 0.024         0.080 / 0.010 / 0.010
#:   heavy          0.270 / 0.363 / 0.032         0.180 / 0.040 / 0.030
#:
#: Rendered text has no paper grain, glare or perspective, so these are a LOWER
#: BOUND on real-document error. See docs/decisions/0006-ocr-calibration.md.
_MEASURED_LEVEL_FOR_PRESET = {
    "clean": None,
    "light": "phone_photo",
    "moderate": "poor_capture",
    "heavy": "severe",
}


def _preset(name: str, **overrides: float) -> NoiseConfig:
    """Build a preset from the measured rates where they exist."""
    level = _MEASURED_LEVEL_FOR_PRESET[name]
    rates = MEASURED_RATES.get(level or "", {}) if level else {}
    return NoiseConfig(
        substitution_rate=rates.get("substitution", overrides.get("substitution_rate", 0.0)),
        deletion_rate=rates.get("deletion", overrides.get("deletion_rate", 0.0)),
        insertion_rate=rates.get("insertion", overrides.get("insertion_rate", 0.0)),
        homoglyph_rate=overrides.get("homoglyph_rate", 0.0),
        diacritic_drop_rate=overrides.get("diacritic_drop_rate", 0.0),
        space_collapse_rate=overrides.get("space_collapse_rate", 0.0),
    )


NOISE_PRESETS: dict[str, NoiseConfig] = {
    "clean": _preset("clean"),
    # Fallbacks apply only on a checkout that has not run the calibration.
    "light": _preset(
        "light",
        substitution_rate=0.008, deletion_rate=0.025, insertion_rate=0.001,
        homoglyph_rate=0.02, diacritic_drop_rate=0.4, space_collapse_rate=0.02,
    ),
    "moderate": _preset(
        "moderate",
        substitution_rate=0.096, deletion_rate=0.170, insertion_rate=0.024,
        homoglyph_rate=0.05, diacritic_drop_rate=0.7, space_collapse_rate=0.05,
    ),
    "heavy": _preset(
        "heavy",
        substitution_rate=0.270, deletion_rate=0.363, insertion_rate=0.032,
        homoglyph_rate=0.12, diacritic_drop_rate=0.9, space_collapse_rate=0.12,
    ),
}
