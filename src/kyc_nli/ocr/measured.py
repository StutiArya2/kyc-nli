"""MEASURED OCR error rates and confusions. GENERATED FILE - DO NOT EDIT.

Regenerate with:  kyc-nli calibrate-ocr --words 200 --write-tables

Produced by rendering known text with correct complex-script shaping, degrading
it, running Tesseract, and aligning the output against the input. See
docs/decisions/0006-ocr-calibration.md for what this does and does not measure;
in particular, rendered text has no paper grain, glare or perspective, so these
rates are a LOWER BOUND on real-document error.

Seed 20260906. 200 words per language per level.
"""

from __future__ import annotations


#: Measured (substitution, deletion, insertion) rates per level,
#: averaged over the Indic scripts (hi, ta, bn). English is excluded
#: as the easy case and Urdu as the anomalous one -- its error is
#: dominated by whole-word read failures, not character confusion.
MEASURED_RATES: dict[str, dict[str, float]] = {
    "pristine": {"substitution": 0.0048, "deletion": 0.0112, "insertion": 0.0017},
    "good_scan": {"substitution": 0.0045, "deletion": 0.0160, "insertion": 0.0014},
    "phone_photo": {"substitution": 0.0083, "deletion": 0.0251, "insertion": 0.0008},
    "poor_capture": {"substitution": 0.0955, "deletion": 0.1695, "insertion": 0.0236},
    "severe": {"substitution": 0.2704, "deletion": 0.3630, "insertion": 0.0318},
}

#: Per-language whole-word read-failure rate, by level. Urdu is the
#: reason this exists: its OCR failure is bimodal -- the engine either
#: reads a word correctly or returns nothing at all -- which a
#: character-substitution model cannot express.
MEASURED_BLANK_RATES: dict[str, dict[str, float]] = {
    "en": {"pristine": 0.0000, "good_scan": 0.0000, "phone_photo": 0.0000, "poor_capture": 0.0000, "severe": 0.1000},
    "hi": {"pristine": 0.0050, "good_scan": 0.0050, "phone_photo": 0.0100, "poor_capture": 0.0400, "severe": 0.0350},
    "ta": {"pristine": 0.0000, "good_scan": 0.0050, "phone_photo": 0.0100, "poor_capture": 0.0100, "severe": 0.1100},
    "bn": {"pristine": 0.0100, "good_scan": 0.0100, "phone_photo": 0.0150, "poor_capture": 0.1300, "severe": 0.1100},
    "ur": {"pristine": 0.3150, "good_scan": 0.2550, "phone_photo": 0.0100, "poor_capture": 0.0250, "severe": 0.3400},
}

#: Measured character confusions, most frequent first.
MEASURED_CONFUSIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {
        'Y': ('V',),
        'I': ('E',),
        'A': ('a',),
    },
    "hi": {
        'र': ('्', 'ख', '५'),
        'े': ('ै', 'क'),
        'त': ('ल', 'ह'),
        'ा': ('क', 'आ', 'श', '्', 'ख'),
        'व': ('क',),
        'आ': ('अ',),
        'ठ': ('ट',),
        'न': ('क', 'ह', 'र', 'म'),
        '्': ('क',),
        'ज': ('क',),
        'स': ('ख', '७'),
        'ध': ('च', 'घ'),
        'म': ('क',),
        'ं': ('ी', 'क', 'ा', 'ड'),
        'ु': ('्',),
        'ल': ('े', 'स', 'क'),
        'ट': ('श',),
        'छ': ('क',),
        'प': ('च', 'क'),
        'ि': ('ह',),
        'ो': ('े', 'ी'),
        'ी': ('क',),
        'द': ('ड',),
    },
    "ta": {
        'ன': ('ண',),
        'ய': ('வ',),
        'வ': ('ல', 'க'),
        'ள': ('ன',),
        'ல': ('ஸ', 'ன'),
        'ந': ('த',),
        'ு': ('க',),
        'ை': ('.',),
        '்': ('ப',),
    },
    "bn": {
        'া': ('০', '্'),
        'ে': ('ো', '০', 'া', '১', 'ল'),
        'দ': ('স',),
        '্': ('া', 'আ'),
        'ম': ('স', 'া', 'গ'),
        'ক': ('ব', 'ফ'),
        'ল': ('র', 'ক'),
        'ন': ('ল', 'স', 'ব', 'শ', 'জ'),
        'ব': ('ক',),
        'ো': ('ে',),
        'ভ': ('ত',),
        'ু': ('া',),
        'ফ': ('ষ',),
        'স': ('দ', 'গ', 'ন', 'জ'),
        'র': ('জ', 'া', 'গ', 'ত', 'প'),
        'ণ': ('া',),
        'য': ('স', 'া'),
        'ূ': ('ু',),
        'হ': ('গ',),
        'জ': ('১', 'ক'),
        'অ': ('আ',),
        'ও': ('০',),
        'শ': ('া',),
    },
    "ur": {
        'م': ('ع', 'ھ', 'س'),
        'ن': ('ت', 'ئ', 'ٹ'),
        'ي': ('ی',),
        'ہ': ('ب', 'ت'),
        'ب': ('ہ', 'م', 'ی', 'ت'),
        'پ': ('ب', 'ی'),
        'ت': ('ٹ', 'ن'),
        'ل': ('ٹ', 'ن'),
        'ی': ('س', 'م'),
        'ك': ('ک',),
        'ج': ('چ', 'ح'),
        'ڑ': ('ز',),
        'ٹ': ('ت', 'ئ', 'ن'),
        'ر': ('ز',),
        'س': ('ص',),
        'ُ': ('أ',),
        'ِ': ('ی', 'پ'),
        'چ': ('ج',),
        'د': ('م',),
        'ک': ('گ',),
        'ڈ': ('ٹ',),
        'ز': ('ڑ',),
        'ا': ('ل',),
        'ئ': ('ت',),
        'و': ('ی',),
    },
}
