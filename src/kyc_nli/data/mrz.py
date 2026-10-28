"""ICAO 9303 TD3 Machine Readable Zone construction.

Implemented faithfully enough that the check digits are real, because the rule
baseline is allowed to use them: a check-digit failure is decisive evidence of
corruption, and any baseline we claim to beat must be allowed its strongest
signals. TD3 (passport) only for now; TD1 (ID card, 3x30) is not yet implemented.
"""

from __future__ import annotations

import unicodedata
from datetime import date

FILLER = "<"
TD3_LINE_LENGTH = 44

_WEIGHTS = (7, 3, 1)


def check_digit(value: str) -> str:
    """ICAO 9303 modulo-10 check digit with 7-3-1 weighting."""
    total = 0
    for i, ch in enumerate(value):
        up = ch.upper()
        # ASCII-only, deliberately. `ch.isdigit()` is true of '٣' and
        # `ch.isalpha()` of 'É' and 'अ', and the arithmetic below would then
        # return a digit in 0-9 that looks entirely plausible and verifies
        # against nothing. A check digit that fails loudly is worth more than
        # one that is quietly meaningless.
        if "0" <= up <= "9":
            v = int(up)
        elif up == FILLER:
            v = 0
        elif "A" <= up <= "Z":
            v = ord(up) - ord("A") + 10
        else:
            raise ValueError(f"Character {ch!r} is not valid in an MRZ field")
        total += v * _WEIGHTS[i % 3]
    return str(total % 10)


def transliterate_to_mrz_charset(text: str) -> str:
    """Reduce a Latin string to the MRZ character set [A-Z0-9<].

    Spaces, hyphens and apostrophes become the filler character, which is where
    a surprising amount of real-world mismatch comes from: O'BRIEN becomes
    O<BRIEN in the MRZ but stays O'BRIEN in the VIZ.

    Accented Latin letters FOLD to their base letter -- É to E, Ü to U -- as
    ICAO Doc 9303 Part 3 requires. Dropping the letter instead would emit JOS<
    for JOSÉ: a different name, in the one zone the rule baseline trusts most,
    manufacturing exactly the false mismatch this project measures.
    """
    # NFKD splits a precomposed letter into base + combining mark, so discarding
    # the marks leaves the base. Letters with no decomposition (ß, Ł, Ø) survive
    # as themselves and are dropped below, which is the honest outcome: they
    # need a language-specific expansion table, not a guess.
    decomposed = unicodedata.normalize("NFKD", text.upper())
    out: list[str] = []
    for ch in decomposed:
        if unicodedata.combining(ch):
            continue
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch in " -'":
            out.append(FILLER)
    return "".join(out)


def _pad(value: str, length: int) -> str:
    return (value[:length]).ljust(length, FILLER)


def format_mrz_date(d: date) -> str:
    """YYMMDD, as the MRZ carries it. Century is genuinely absent from the MRZ."""
    return f"{d.year % 100:02d}{d.month:02d}{d.day:02d}"


def build_td3(
    *,
    surname_latin: str,
    given_latin: str,
    document_number: str,
    nationality: str,
    date_of_birth: date,
    sex: str,
    date_of_expiry: date,
    issuing_state: str | None = None,
    document_type: str = "P",
) -> tuple[str, str]:
    """Build the two 44-character TD3 MRZ lines."""
    issuing_state = issuing_state or nationality

    name = (
        f"{transliterate_to_mrz_charset(surname_latin)}"
        f"{FILLER}{FILLER}"
        f"{transliterate_to_mrz_charset(given_latin)}"
    )
    line1 = _pad(f"{document_type}{FILLER}{issuing_state}{name}", TD3_LINE_LENGTH)

    doc_no = _pad(transliterate_to_mrz_charset(document_number), 9)
    dob = format_mrz_date(date_of_birth)
    doe = format_mrz_date(date_of_expiry)
    optional = _pad("", 14)

    composite_source = (
        doc_no + check_digit(doc_no) + dob + check_digit(dob) + doe + check_digit(doe) + optional
    )
    line2 = (
        f"{doc_no}{check_digit(doc_no)}"
        f"{nationality}"
        f"{dob}{check_digit(dob)}"
        f"{sex}"
        f"{doe}{check_digit(doe)}"
        f"{optional}{check_digit(optional)}"
        f"{check_digit(composite_source)}"
    )
    return line1, _pad(line2, TD3_LINE_LENGTH)


def parse_mrz_name(line1: str) -> tuple[str, str]:
    """Recover (surname, given names) from TD3 line 1. Inverse of the padding."""
    body = line1[5:]
    surname, _, given = body.partition(FILLER * 2)
    return (
        surname.replace(FILLER, " ").strip(),
        given.replace(FILLER, " ").strip(),
    )
