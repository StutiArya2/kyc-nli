"""Rendering and OCR-calibration tests.

The alignment and rendering tests need no OCR engine and always run. The
end-to-end calibration test skips when Tesseract is absent, so a clean checkout
stays green.
"""

from __future__ import annotations

import numpy as np
import pytest

from kyc_nli.ocr import calibrate, render
from kyc_nli.ocr.render import DEGRADE_LEVELS, Script

needs_fonts = pytest.mark.skipif(
    not render.fonts_available(), reason="Noto fonts absent; run `kyc-nli calibrate-ocr --fetch`"
)
needs_tesseract = pytest.mark.skipif(
    not calibrate.is_available(), reason="Tesseract or a language pack is missing"
)


# --------------------------------------------------------------------------
# Alignment: pure logic, no dependencies.
# --------------------------------------------------------------------------


def test_identical_strings_align_as_all_matches() -> None:
    ops = calibrate.align("SHARMA", "SHARMA")
    assert [o[0] for o in ops] == ["match"] * 6


def test_substitution_is_attributed_to_the_right_characters() -> None:
    """The whole point of aligning: knowing WHICH character became which."""
    ops = calibrate.align("SHARMA", "SHARNA")
    subs = [(t, h) for op, t, h in ops if op == "sub"]
    assert subs == [("M", "N")]


def test_deletion_and_insertion_are_distinguished() -> None:
    assert [o[0] for o in calibrate.align("ABC", "AC")].count("del") == 1
    assert [o[0] for o in calibrate.align("AC", "ABC")].count("ins") == 1


def test_alignment_handles_empty_hypothesis() -> None:
    """A blank OCR result must not crash the aligner."""
    ops = calibrate.align("SHARMA", "")
    assert all(op == "del" for op, _, _ in ops)
    assert len(ops) == 6


def test_alignment_is_symmetric_in_cost() -> None:
    a = sum(1 for op, _, _ in calibrate.align("KUMAR", "KUMER") if op != "match")
    b = sum(1 for op, _, _ in calibrate.align("KUMER", "KUMAR") if op != "match")
    assert a == b == 1


def test_zero_width_marks_are_not_counted_as_errors() -> None:
    """Tesseract appends U+200C after Tamil words ending in a pure consonant.

    It is invisible and carries no identity information, but it put a constant
    ~0.07 floor under every Tamil CER and filled the confusion tables with ZWNJ
    entries -- an artifact of the measurement, not an OCR error.
    """
    truth = "ஈசனின்"
    with_zwnj = truth + "‌"
    assert calibrate.normalise(with_zwnj) == truth
    assert all(op == "match" for op, _, _ in calibrate.align(truth, with_zwnj))


def test_arabic_diacritics_are_still_counted_as_errors() -> None:
    """Losing a kasra IS a real read error, and the noise model simulates it.

    The zero-width strip must not quietly widen into stripping diacritics.
    """
    truth = "جمالِ"
    dropped = "جمال"
    assert calibrate.normalise(dropped) != calibrate.normalise(truth)
    assert any(op != "match" for op, _, _ in calibrate.align(truth, dropped))


def test_confusion_table_has_the_shape_the_noise_model_consumes() -> None:
    """The output must drop straight into kyc_nli.ocr.noise."""
    from collections import Counter

    result = calibrate.CalibrationResult(
        language="hi",
        script=Script.DEVANAGARI,
        levels=[
            calibrate.LevelResult(
                level="x", n_words=1, n_chars=10, cer=0.1,
                substitution_rate=0.1, deletion_rate=0.0, insertion_rate=0.0,
                blank_rate=0.0,
                confusions=Counter({("भ", "म"): 5, ("ब", "व"): 3, ("क", "फ"): 1}),
            )
        ],
    )
    table = result.confusion_table(min_count=2)
    assert table == {"भ": ("म",), "ब": ("व",)}  # the count-1 pair is dropped as noise
    assert all(isinstance(v, tuple) for v in table.values())


# --------------------------------------------------------------------------
# Rendering: needs the fonts, not the OCR engine.
# --------------------------------------------------------------------------


@needs_fonts
@pytest.mark.parametrize(
    ("text", "script"),
    [
        ("SHARMA", Script.LATIN),
        ("शर्मा", Script.DEVANAGARI),
        ("சுப்ரமணியன்", Script.TAMIL),
        ("বন্দ্যোপাধ্যায়", Script.BENGALI),
        ("صدیقی", Script.ARABIC),
    ],
)
def test_every_script_renders_visible_ink(text: str, script: Script) -> None:
    image = render.render(text, script, size_px=40)
    arr = np.asarray(image)
    assert arr.min() < 128, f"{script} rendered blank -- missing font or shaping failure"
    ink_fraction = (arr < 128).mean()
    assert 0.005 < ink_fraction < 0.6, f"{script} ink fraction {ink_fraction:.3f} is implausible"


@needs_fonts
def test_devanagari_vowel_sign_reorders() -> None:
    """कि must render the i-matra BEFORE the consonant.

    This is the single check that proves complex-script shaping is active.
    Without HarfBuzz the glyphs come out in logical order and every Indic
    rendering is subtly wrong -- which would calibrate the noise model against
    text no real document contains.
    """
    import uharfbuzz as hb

    font_path = str(render.fonts_dir() / render.FONTS[Script.DEVANAGARI])

    def glyph_ids(text: str) -> list[int]:
        font = hb.Font(hb.Face(hb.Blob.from_file_path(font_path)))
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf)
        return [g.codepoint for g in buf.glyph_infos]

    ka = glyph_ids("क")
    ka_with_matra = glyph_ids("कि")

    assert len(ka) == 1
    assert len(ka_with_matra) == 2
    # The consonant must end up SECOND: the i-matra is drawn before it.
    assert ka_with_matra[1] == ka[0], (
        f"expected the consonant glyph {ka[0]} in second position, got "
        f"{ka_with_matra} -- shaping is not reordering the vowel sign"
    )
    assert ka_with_matra[0] != ka[0]


@needs_fonts
def test_degradation_monotonically_damages_the_image() -> None:
    """Pixel-level damage must increase with level.

    Necessary but NOT sufficient: the first version of the degradation ladder
    passed this test while producing identical OCR output at three of its four
    levels. Pixels can change a lot without the engine noticing. The test that
    actually guards the axis is
    ``test_degradation_is_monotonic_in_measured_cer`` below.
    """
    image = render.render("SHARMA KUMAR", Script.LATIN, size_px=40)
    base = np.asarray(image, dtype=np.float32)
    previous = 0.0
    for config in DEGRADE_LEVELS[1:]:
        out = np.asarray(
            render.degrade(image, config, seed=1).resize(image.size), dtype=np.float32
        )
        damage = float(np.abs(out - base).mean())
        assert damage > previous, f"{config.name} is not harsher than the level before it"
        previous = damage


# --------------------------------------------------------------------------
# End to end: needs Tesseract.
# --------------------------------------------------------------------------


@needs_tesseract
@needs_fonts
def test_clean_latin_is_read_almost_perfectly() -> None:
    """A sanity floor. If pristine Latin OCR is bad, the harness is broken."""
    result = calibrate.calibrate_language("en", ["SHARMA", "KUMAR", "PATEL"])
    assert result.levels[0].cer < 0.15


@needs_tesseract
@needs_fonts
def test_degradation_is_monotonic_in_measured_cer() -> None:
    """The degradation ladder must actually separate conditions for the ENGINE.

    This is the test that matters and the one the original ladder failed: Latin
    read at 0.000 CER through three of four levels, so the "OCR noise" axis was
    measuring one condition three times. Checked on Latin because it is the
    easiest script — if the axis separates here it separates everywhere.
    """
    words = ["SHARMA", "KUMAR", "PATEL", "MEHTA", "IYER", "MENON", "REDDY", "NAIR"]
    result = calibrate.calibrate_language("en", words)
    cers = [lr.cer for lr in result.levels]
    assert cers[0] < 0.05, f"pristine Latin should be near-perfect, got {cers[0]:.3f}"
    assert cers[-1] > 0.10, f"the hardest level must actually be hard, got {cers[-1]:.3f}"
    assert cers[-1] > cers[0], f"CER did not rise across the ladder: {cers}"
    distinct = len({round(c, 3) for c in cers})
    assert distinct >= 3, f"only {distinct} distinct CERs across {len(cers)} levels: {cers}"
