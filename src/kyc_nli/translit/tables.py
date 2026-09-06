"""Script-to-Latin transliteration tables.

VERIFICATION STATUS -- read before citing any of this in the paper.

  hi/ta/bn  No normative standard exists for Indian-language romanisation on
      identity documents. These are simplified ISO-15919-style mappings intended
      as *baseline* romanisers, not gold standards. Their deliberate
      one-to-many-ness is the point, not a defect.
  ur  ICAO Doc 9303 Part 3 Arabic table, extended with the Perso-Arabic letters
      Urdu adds. Status: PARTIAL. Plain consonants and long vowels are
      transcribed; hamza-carrier and ta-marbuta rows use ICAO's multi-letter
      X-codes and are marked UNVERIFIED below.
  ru/zh  Retained but NOT in the active language set (see decision 0005). ICAO
      Doc 9303 Cyrillic transcribed but not checked character-by-character;
      Pinyin covers only the embedded name pool.

Anything marked UNVERIFIED must be checked against the primary source before it
appears in a results table. See CLAUDE.md, "What to ask about rather than
deciding alone".
"""

from __future__ import annotations

# ==========================================================================
# ACTIVE SET: the five languages of the Indian document context.
# ==========================================================================

# --------------------------------------------------------------------------
# Devanagari (Hindi) -> Latin, simplified ISO-15919-style. NON-normative.
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
    "ा": "AA", "ि": "I", "ी": "EE", "ु": "U", "ू": "OO",
    "ृ": "RI", "े": "E", "ै": "AI", "ो": "O", "ौ": "AU",
}
DEVA_VIRAMA = "्"
DEVA_NASALS: dict[str, str] = {"ं": "N", "ँ": "N", "ः": "H"}

# --------------------------------------------------------------------------
# Tamil -> Latin. NON-normative, and the most systematically ambiguous of the
# three Brahmic scripts here.
#
# Tamil orthography does not distinguish voiced from voiceless stops: the same
# letter is read K or G, CH or S, T or D, TH or DH, P or B depending on its
# position in the word. So a single Tamil string has several *equally correct*
# Latin renderings, and which one a holder writes on a form is not predictable
# from the script. This is a stronger version of the Hindi argument, and it is
# the reason Tamil is in the set.
# --------------------------------------------------------------------------
TAML_CONSONANTS: dict[str, str] = {
    "க": "K", "ங": "NG", "ச": "CH", "ஞ": "NY", "ட": "T", "ண": "N",
    "த": "TH", "ந": "N", "ப": "P", "ம": "M", "ய": "Y", "ர": "R",
    "ல": "L", "வ": "V", "ழ": "ZH", "ள": "L", "ற": "R", "ன": "N",
    # Grantha letters, used for Sanskrit and Perso-Arabic loans in names.
    "ஜ": "J", "ஷ": "SH", "ஸ": "S", "ஹ": "H", "க்ஷ": "KSH", "ஶ": "SH",
}
#: Voicing alternations. Each key may legitimately be rendered as its value.
TAML_VOICING: dict[str, str] = {"K": "G", "CH": "S", "T": "D", "TH": "DH", "P": "B"}
TAML_INDEPENDENT_VOWELS: dict[str, str] = {
    "அ": "A", "ஆ": "AA", "இ": "I", "ஈ": "EE", "உ": "U", "ஊ": "OO",
    "எ": "E", "ஏ": "EE", "ஐ": "AI", "ஒ": "O", "ஓ": "OO", "ஔ": "AU",
}
TAML_VOWEL_SIGNS: dict[str, str] = {
    "ா": "AA", "ி": "I", "ீ": "EE", "ு": "U", "ூ": "OO",
    "ெ": "E", "ே": "EE", "ை": "AI", "ொ": "O", "ோ": "OO",
    "ௌ": "AU",
}
TAML_VIRAMA = "்"  # pulli
TAML_NASALS: dict[str, str] = {}

# --------------------------------------------------------------------------
# Bengali -> Latin. NON-normative.
#
# Bengali's own quirk: the inherent vowel is phonetically closer to /o/ than
# /a/, so the same name is romanised BANERJEE or BANDYOPADHYAY, SEN or SHEN,
# and ব is written B or V. Bengali also has no /v/, so Sanskrit-derived names
# alternate B/V freely.
# --------------------------------------------------------------------------
BENG_CONSONANTS: dict[str, str] = {
    "ক": "K", "খ": "KH", "গ": "G", "ঘ": "GH", "ঙ": "NG",
    "চ": "CH", "ছ": "CHH", "জ": "J", "ঝ": "JH", "ঞ": "NY",
    "ট": "T", "ঠ": "TH", "ড": "D", "ঢ": "DH", "ণ": "N",
    "ত": "T", "থ": "TH", "দ": "D", "ধ": "DH", "ন": "N",
    "প": "P", "ফ": "PH", "ব": "B", "ভ": "BH", "ম": "M",
    "য": "J", "র": "R", "ল": "L", "শ": "SH", "ষ": "SH", "স": "S",
    "হ": "H", "ড়": "R", "ঢ়": "RH", "য়": "Y", "ৎ": "T",
}
BENG_INDEPENDENT_VOWELS: dict[str, str] = {
    "অ": "A", "আ": "AA", "ই": "I", "ঈ": "EE", "উ": "U", "ঊ": "OO",
    "ঋ": "RI", "এ": "E", "ঐ": "AI", "ও": "O", "ঔ": "AU",
}
BENG_VOWEL_SIGNS: dict[str, str] = {
    "া": "AA", "ি": "I", "ী": "EE", "ু": "U", "ূ": "OO",
    "ৃ": "RI", "ে": "E", "ৈ": "AI", "ো": "O", "ৌ": "AU",
}
BENG_VIRAMA = "্"  # hasanta
BENG_NASALS: dict[str, str] = {"ং": "NG", "ঁ": "N", "ঃ": "H"}

# --------------------------------------------------------------------------
# Perso-Arabic (Urdu) -> Latin, ICAO Doc 9303 Part 3 Arabic table extended with
# the letters Urdu adds. PARTIAL, see module docstring.
#
# The extension matters: Urdu writes K as U+06A9 and Y as U+06CC, NOT the
# Arabic U+0643 and U+064A. A table built for Arabic alone silently drops both,
# which corrupts most Urdu names without raising an error.
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
    "ً": "", "ٌ": "", "ٍ": "", "َ": "", "ُ": "",
    "ِ": "", "ّ": "", "ْ": "", "ـ": "",
}

#: Letters Urdu adds to the Arabic inventory, plus its divergent K and Y.
URDU_EXTENSIONS: dict[str, str] = {
    "ک": "K",   # ک  Urdu kaf, NOT U+0643
    "ی": "Y",   # ی  Urdu ye, NOT U+064A
    "گ": "G",   # گ  gaf
    "پ": "P",   # پ  pe
    "چ": "CH",  # چ  che
    "ژ": "ZH",  # ژ  zhe
    "ٹ": "T",   # ٹ  retroflex te
    "ڈ": "D",   # ڈ  retroflex dal
    "ڑ": "R",   # ڑ  retroflex re
    "ں": "N",   # ں  noon ghunna
    "ے": "E",   # ے  bari ye
    "ہ": "H",   # ہ  gol he
    "ھ": "H",   # ھ  do-chashmi he (aspiration marker)
    "ۃ": "H",   # ۃ  ta marbuta goal
    "ء": "XE",  # ء  hamza
}

ICAO_URDU: dict[str, str] = {**ICAO_ARABIC, **URDU_EXTENSIONS}

# ==========================================================================
# RETAINED BUT NOT IN THE ACTIVE SET (decision 0005).
#
# Kept because the language registry makes an unlisted language cost nothing,
# and because "does this generalise beyond the Indian document context?" is a
# question a reviewer will ask and these make it cheap to answer.
# ==========================================================================

# Cyrillic -> Latin, ICAO Doc 9303 Part 3.
# Note ICAO deliberately differs from the "intuitive" scientific
# transliteration: Ю -> IU (not YU), Я -> IA (not YA), Х -> KH, Ц -> TS.
ICAO_CYRILLIC: dict[str, str] = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "E",
    "Ж": "ZH", "З": "Z", "И": "I", "Й": "I", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "KH", "Ц": "TS", "Ч": "CH", "Ш": "SH", "Щ": "SHCH",
    "Ъ": "IE", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "IU", "Я": "IA",
    "Ґ": "G", "Є": "IE", "І": "I", "Ї": "I", "Ў": "U", "Ђ": "D", "Ј": "J",
    "Љ": "LJ", "Њ": "NJ", "Ћ": "C", "Џ": "DZ",
}

# Han -> Pinyin. Embedded coverage is limited to the retained name pool.
PINYIN_MINIMAL: dict[str, str] = {
    "王": "WANG", "李": "LI", "张": "ZHANG", "刘": "LIU", "陈": "CHEN",
    "杨": "YANG", "黄": "HUANG", "赵": "ZHAO", "吴": "WU", "周": "ZHOU",
    "徐": "XU", "孙": "SUN", "马": "MA", "朱": "ZHU", "胡": "HU",
    "郭": "GUO", "何": "HE", "林": "LIN", "高": "GAO", "罗": "LUO",
    "伟": "WEI", "芳": "FANG", "娜": "NA", "敏": "MIN", "静": "JING",
    "秀": "XIU", "英": "YING", "华": "HUA", "慧": "HUI", "秋": "QIU",
    "军": "JUN", "洋": "YANG", "勇": "YONG", "艳": "YAN", "杰": "JIE",
    "涛": "TAO", "明": "MING", "超": "CHAO", "霞": "XIA", "平": "PING",
    "刚": "GANG", "桂": "GUI", "文": "WEN", "丽": "LI", "强": "QIANG",
}
