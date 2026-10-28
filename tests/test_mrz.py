"""Edge cases for ICAO 9303 TD3 MRZ construction.

The rule baseline is allowed to use MRZ check digits as decisive evidence of
corruption, so a check digit that is wrong in an edge case does not merely
produce a wrong string -- it hands the baseline a false signal and quietly
changes the number the project is trying to beat. These tests pin the
arithmetic against ICAO's own published specimen and then push every input
that is not a well-formed A-Z name.
"""

from __future__ import annotations

from datetime import date

import pytest

from kyc_nli.data.mrz import (
    FILLER,
    TD3_LINE_LENGTH,
    build_td3,
    check_digit,
    format_mrz_date,
    parse_mrz_name,
    transliterate_to_mrz_charset,
)

# --------------------------------------------------------------------------
# check_digit
# --------------------------------------------------------------------------


def test_check_digit_matches_the_icao_worked_example() -> None:
    """ICAO Doc 9303 Part 3 publishes this exact pair. If it drifts, we drifted."""
    assert check_digit("D23145890734") == "9"


def test_check_digit_of_the_empty_string_is_zero() -> None:
    """Not a curiosity: the 14-character optional-data field is usually empty."""
    assert check_digit("") == "0"


def test_check_digit_of_all_filler_is_zero() -> None:
    assert check_digit(FILLER * 14) == "0"


def test_check_digit_treats_letters_as_their_alphabet_position_plus_ten() -> None:
    # A = 10, weighted 7 -> 70 -> 0.  B = 11, weighted 7 -> 77 -> 7.
    assert check_digit("A") == "0"
    assert check_digit("B") == "7"


def test_check_digit_is_case_insensitive() -> None:
    """Lowercase never appears in a real MRZ, but a caller may not have upcased."""
    assert check_digit("l898902c3") == check_digit("L898902C3")


@pytest.mark.parametrize("bad", ["!", "A-B", "12 34", "É", "अ"])
def test_check_digit_rejects_characters_outside_the_mrz_alphabet(bad: str) -> None:
    """Loudly, rather than scoring them as zero and returning a plausible digit."""
    with pytest.raises(ValueError):
        check_digit(bad)


def test_the_weighting_cycle_restarts_every_three_characters() -> None:
    """7-3-1 repeating. Position 3 must weigh the same as position 0."""
    assert check_digit("100") == check_digit("000100"[3:])


# --------------------------------------------------------------------------
# transliterate_to_mrz_charset
# --------------------------------------------------------------------------


def test_separators_become_filler_not_nothing() -> None:
    """O'BRIEN -> O<BRIEN is a real and common source of VIZ/MRZ mismatch."""
    assert transliterate_to_mrz_charset("O'Brien") == "O<BRIEN"
    assert transliterate_to_mrz_charset("VAN DER BERG") == "VAN<DER<BERG"
    assert transliterate_to_mrz_charset("SMITH-JONES") == "SMITH<JONES"


def test_accented_latin_letters_fold_to_their_base_letter() -> None:
    """ICAO Doc 9303 Part 3 mandates the fold; dropping the letter is not an option.

    This was wrong until it was tested. JOSÉ became JOS<, a *different name*,
    silently, in the one zone the rule baseline trusts most. Every downstream
    comparison then sees a genuine holder whose MRZ and VIZ disagree, which is
    precisely the false-mismatch the project measures -- manufactured by us.
    """
    assert transliterate_to_mrz_charset("JOSÉ") == "JOSE"
    assert transliterate_to_mrz_charset("MÜLLER") == "MULLER"
    assert transliterate_to_mrz_charset("Ångström") == "ANGSTROM"
    assert transliterate_to_mrz_charset("Nuñez") == "NUNEZ"


def test_characters_with_no_latin_base_are_dropped_rather_than_guessed() -> None:
    """A non-Latin string reaching here is a caller bug; emit nothing, not noise."""
    assert transliterate_to_mrz_charset("चटर्जी") == ""


def test_digits_survive_because_document_numbers_run_through_here() -> None:
    assert transliterate_to_mrz_charset("l898902c3") == "L898902C3"


def test_the_result_is_always_a_legal_check_digit_input() -> None:
    """The contract that matters: whatever goes in, check_digit must not raise."""
    for raw in ["JOSÉ", "O'Brien", "चटर्जी", "", "A  B", "Ångström-Nuñez"]:
        check_digit(transliterate_to_mrz_charset(raw))


# --------------------------------------------------------------------------
# format_mrz_date
# --------------------------------------------------------------------------


def test_the_mrz_genuinely_cannot_express_a_century() -> None:
    """1905 and 2005 are the same six characters. This is a property of the
    format, not a defect here, and the temporal rules must not assume otherwise."""
    assert format_mrz_date(date(2005, 1, 2)) == "050102"
    assert format_mrz_date(date(1905, 1, 2)) == "050102"


def test_single_digit_months_and_days_are_zero_padded() -> None:
    assert format_mrz_date(date(1959, 1, 2)) == "590102"
    assert len(format_mrz_date(date(2030, 12, 31))) == 6


def test_a_leap_day_formats_like_any_other_day() -> None:
    assert format_mrz_date(date(2024, 2, 29)) == "240229"


# --------------------------------------------------------------------------
# build_td3
# --------------------------------------------------------------------------


def _specimen() -> tuple[str, str]:
    return build_td3(
        surname_latin="ERIKSSON",
        given_latin="ANNA MARIA",
        document_number="L898902C3",
        nationality="UTO",
        date_of_birth=date(1974, 8, 12),
        sex="F",
        date_of_expiry=date(2012, 4, 15),
    )


def test_the_icao_specimen_reproduces_character_for_character() -> None:
    """The Doc 9303 Part 4 specimen passport. Any drift here is a real defect."""
    line1, line2 = _specimen()
    assert line1 == "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    assert line2 == "L898902C36UTO7408122F1204159<<<<<<<<<<<<<<08"


@pytest.mark.parametrize(
    "surname,given",
    [
        ("ERIKSSON", "ANNA MARIA"),
        ("X" * 50, "Y" * 20),  # overflows the 44-character line
        ("", ""),  # every field empty
        ("O'BRIEN-SMITH", "MARY JANE ELIZABETH"),
        ("JOSÉ", "MÜLLER"),
    ],
)
def test_both_lines_are_always_exactly_44_characters(surname: str, given: str) -> None:
    """A short line is not a cosmetic problem -- offsets are positional, so every
    field after the short point is read from the wrong place."""
    line1, line2 = build_td3(
        surname_latin=surname,
        given_latin=given,
        document_number="AB1234567",
        nationality="IND",
        date_of_birth=date(1990, 5, 5),
        sex="M",
        date_of_expiry=date(2030, 5, 5),
    )
    assert len(line1) == TD3_LINE_LENGTH
    assert len(line2) == TD3_LINE_LENGTH


def test_an_overlong_name_truncates_rather_than_overflowing() -> None:
    """ICAO truncates; it does not wrap. Given names are the first casualty."""
    line1, _ = build_td3(
        surname_latin="X" * 50,
        given_latin="ANNA",
        document_number="AB1234567",
        nationality="IND",
        date_of_birth=date(1990, 5, 5),
        sex="M",
        date_of_expiry=date(2030, 5, 5),
    )
    assert len(line1) == TD3_LINE_LENGTH
    assert "ANNA" not in line1


def test_every_check_digit_in_line_two_verifies() -> None:
    """Recompute each digit from the substring it covers, as a reader would."""
    _, line2 = _specimen()
    assert check_digit(line2[0:9]) == line2[9]  # document number
    assert check_digit(line2[13:19]) == line2[19]  # date of birth
    assert check_digit(line2[21:27]) == line2[27]  # date of expiry
    assert check_digit(line2[28:42]) == line2[42]  # optional data
    composite = line2[0:10] + line2[13:20] + line2[21:43]
    assert check_digit(composite) == line2[43]


def test_the_issuing_state_defaults_to_the_nationality() -> None:
    explicit, _ = build_td3(
        surname_latin="A", given_latin="B", document_number="1", nationality="IND",
        date_of_birth=date(1990, 1, 1), sex="M", date_of_expiry=date(2030, 1, 1),
        issuing_state="IND",
    )
    implied, _ = build_td3(
        surname_latin="A", given_latin="B", document_number="1", nationality="IND",
        date_of_birth=date(1990, 1, 1), sex="M", date_of_expiry=date(2030, 1, 1),
    )
    assert explicit == implied


# --------------------------------------------------------------------------
# parse_mrz_name
# --------------------------------------------------------------------------


def test_parsing_recovers_the_name_it_was_built_from() -> None:
    line1, _ = _specimen()
    assert parse_mrz_name(line1) == ("ERIKSSON", "ANNA MARIA")


def test_parsing_survives_a_name_with_no_given_names() -> None:
    """Mononymous holders exist and the MRZ carries them with an empty half."""
    line1, _ = build_td3(
        surname_latin="RAJINIKANTH", given_latin="", document_number="AB1234567",
        nationality="IND", date_of_birth=date(1950, 12, 12), sex="M",
        date_of_expiry=date(2030, 12, 12),
    )
    assert parse_mrz_name(line1) == ("RAJINIKANTH", "")


def test_parsing_a_truncated_name_does_not_raise() -> None:
    """A damaged MRZ read is the normal case, not the exceptional one."""
    assert parse_mrz_name("P<IND") == ("", "")
    assert parse_mrz_name("") == ("", "")
