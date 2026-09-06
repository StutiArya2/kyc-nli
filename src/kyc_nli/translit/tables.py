"""Script-to-Latin transliteration tables.

VERIFICATION STATUS -- read before citing any of this in the paper.

  ru  ICAO Doc 9303 Part 3 Cyrillic table.  Status: transcribed, NOT yet
      checked character-by-character against the published standard.
  ar  ICAO Doc 9303 Part 3 Arabic table.  Status: PARTIAL. The plain consonant
      and long-vowel rows are transcribed; the hamza-carrier and ta-marbuta
      rows use ICAO's multi-letter X-codes and are marked UNVERIFIED below.
  hi  No normative standard exists. This is a simplified ISO-15919-style
      mapping and is intended as a *baseline* romaniser, not a gold standard.
  zh  Hanyu Pinyin. The embedded table covers only the syllables used by the
      repo's synthetic name pool; install the `translit` extra (pypinyin) for
      general coverage.

Anything marked UNVERIFIED must be checked against the primary source before it
appears in a results table. See CLAUDE.md, "What to ask about rather than
deciding alone".
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Cyrillic -> Latin, ICAO Doc 9303 Part 3.
# Note ICAO deliberately differs from the "intuitive" scientific
# transliteration: Ю -> IU (not YU), Я -> IA (not YA), Х -> KH, Ц -> TS.
# Those three are the single most common source of false mismatches between a
# Russian VIZ and its own MRZ, so they matter more than they look.
# --------------------------------------------------------------------------
ICAO_CYRILLIC: dict[str, str] = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "E",
    "Ж": "ZH", "З": "Z", "И": "I", "Й": "I", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "KH", "Ц": "TS", "Ч": "CH", "Ш": "SH", "Щ": "SHCH",
    "Ъ": "IE", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "IU", "Я": "IA",
    # Non-Russian Cyrillic letters that appear in other issuing states.
    "Ґ": "G", "Є": "IE", "І": "I", "Ї": "I", "Ў": "U", "Ђ": "D", "Ј": "J",
    "Љ": "LJ", "Њ": "NJ", "Ћ": "C", "Џ": "DZ",
}

# --------------------------------------------------------------------------
# Arabic -> Latin, ICAO Doc 9303 Part 3.  PARTIAL, see module docstring.
# --------------------------------------------------------------------------
ICAO_ARABIC: dict[str, str] = {
    "ا": "A", "ب": "B", "ت": "T", "ث": "TH", "ج": "J", "ح": "H", "خ": "KH",
    "د": "D", "ذ": "DH", "ر": "R", "ز": "Z", "س": "S", "ش": "SH", "ص": "S",
    "ض": "D", "ط": "T", "ظ": "Z", "ع": "E", "غ": "G", "ف": "F", "ق": "Q",
    "ك": "K", "ل": "L", "م": "M", "ن": "N", "ه": "H", "و": "W", "ي": "Y",
    "ى": "Y",
    # UNVERIFIED against Doc 9303 -- hamza carriers and ta marbuta use ICAO
    # X-prefixed codes whose exact form must be confirmed before publication.
    "ء": "XE", "آ": "XAA", "أ": "A", "إ": "I", "ؤ": "U", "ئ": "Y", "ة": "H",
    # Diacritics (harakat). OCR drops these routinely; ICAO omits them.
    "\u064b": "", "\u064c": "", "\u064d": "", "\u064e": "", "\u064f": "",
    "\u0650": "", "\u0651": "", "\u0652": "", "\u0640": "",
}

# --------------------------------------------------------------------------
# Devanagari -> Latin, simplified ISO-15919-style. NOT normative.
# Handled in two layers because Devanagari is an abugida: consonants carry an
# inherent /a/ which a following vowel sign replaces, and virama deletes.
# --------------------------------------------------------------------------
DEVA_CONSONANTS: dict[str, str] = {
    "क": "K", "ख": "KH", "ग": "G", "घ": "GH", "ङ": "NG",
    "च": "CH", "छ": "CHH", "ज": "J", "झ": "JH", "ञ": "NY",
    "ट": "T", "ठ": "TH", "ड": "D", "ढ": "DH", "ण": "N",
    "त": "T", "थ": "TH", "द": "D", "ध": "DH", "न": "N",
    "प": "P", "फ": "PH", "ब": "B", "भ": "BH", "म": "M",
    "य": "Y", "र": "R", "ल": "L", "व": "V", "श": "SH", "ष": "SH",
    "स": "S", "ह": "H", "ळ": "L",
    # Nukta forms, common in names of Perso-Arabic origin.
    "क़": "Q", "ख़": "KH", "ग़": "GH", "ज़": "Z", "ड़": "R", "ढ़": "RH", "फ़": "F",
}
DEVA_INDEPENDENT_VOWELS: dict[str, str] = {
    "अ": "A", "आ": "AA", "इ": "I", "ई": "EE", "उ": "U", "ऊ": "OO",
    "ऋ": "RI", "ए": "E", "ऐ": "AI", "ओ": "O", "औ": "AU",
}
DEVA_VOWEL_SIGNS: dict[str, str] = {
    "\u093e": "AA", "\u093f": "I", "\u0940": "EE", "\u0941": "U", "\u0942": "OO",
    "\u0943": "RI", "\u0947": "E", "\u0948": "AI", "\u094b": "O", "\u094c": "AU",
}
DEVA_VIRAMA = "\u094d"
DEVA_NASALS: dict[str, str] = {"\u0902": "N", "\u0901": "N", "\u0903": "H"}

# --------------------------------------------------------------------------
# Han -> Pinyin. Embedded coverage is limited to the synthetic name pool.
# Install the `translit` extra for pypinyin-backed general coverage.
# --------------------------------------------------------------------------
PINYIN_MINIMAL: dict[str, str] = {
    # Surnames
    "王": "WANG", "李": "LI", "张": "ZHANG", "刘": "LIU", "陈": "CHEN",
    "杨": "YANG", "黄": "HUANG", "赵": "ZHAO", "吴": "WU", "周": "ZHOU",
    "徐": "XU", "孙": "SUN", "马": "MA", "朱": "ZHU", "胡": "HU",
    "郭": "GUO", "何": "HE", "林": "LIN", "高": "GAO", "罗": "LUO",
    # Given-name syllables
    "伟": "WEI", "芳": "FANG", "娜": "NA", "敏": "MIN", "静": "JING",
    "秀": "XIU", "英": "YING", "华": "HUA", "慧": "HUI", "秋": "QIU",
    "军": "JUN", "洋": "YANG", "勇": "YONG", "艳": "YAN", "杰": "JIE",
    "涛": "TAO", "明": "MING", "超": "CHAO", "霞": "XIA", "平": "PING",
    "刚": "GANG", "桂": "GUI", "文": "WEN", "丽": "LI", "强": "QIANG",
}
