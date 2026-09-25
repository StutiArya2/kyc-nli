"""Edge cases for the OCR noise model.

This model decides how hard the benchmark is, so its failure modes are not
crashes -- they are numbers that move. Milestone M1 already found the
hand-built version wrong in *shape*: deletion was 10-17x too low, and correcting
it moved the rule engine from 0.831 to 0.597 at moderate noise. These tests pin
the properties that a future edit could break without anything looking amiss.
"""

from __future__ import annotations

import pytest

from kyc_nli.ocr.noise import (
    NOISE_PRESETS,
    NoiseConfig,
    OCRNoiser,
    is_calibrated,
)
from kyc_nli.schema import Script

SCRIPTS = [
    Script.LATIN,
    Script.DEVANAGARI,
    Script.TAMIL,
    Script.BENGALI,
    Script.ARABIC,
]


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


@pytest.mark.parametrize("script", SCRIPTS)
def test_the_same_seed_corrupts_a_string_the_same_way_twice(script: str) -> None:
    """Every instance in the benchmark must be reproducible from config + seed.
    A noiser that drifts makes the manifest's digest a lie."""
    text = "CHATTERJEE"
    a = OCRNoiser(NOISE_PRESETS["moderate"], seed=42).corrupt(text, script)
    b = OCRNoiser(NOISE_PRESETS["moderate"], seed=42).corrupt(text, script)
    assert a == b


def test_different_seeds_generally_produce_different_corruptions() -> None:
    """The other half: the seed must actually reach the randomness."""
    text = "BANDYOPADHYAY" * 3
    outputs = {
        OCRNoiser(NOISE_PRESETS["moderate"], seed=s).corrupt(text, Script.LATIN)[0]
        for s in range(10)
    }
    assert len(outputs) > 1


def test_no_noiser_consults_the_global_random_module(monkeypatch) -> None:
    """`random.seed()` elsewhere in a process must not change the benchmark.
    Module-level random is the classic way for that to happen silently."""
    import random as global_random

    def explode(*_a, **_k):  # pragma: no cover - only runs if the rule is broken
        raise AssertionError("the noiser reached for the module-level RNG")

    monkeypatch.setattr(global_random, "random", explode)
    monkeypatch.setattr(global_random, "choice", explode)
    OCRNoiser(NOISE_PRESETS["heavy"], seed=1).corrupt("CHATTERJEE", Script.LATIN)


# --------------------------------------------------------------------------
# The clean preset must be the identity
# --------------------------------------------------------------------------


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize(
    "text", ["CHATTERJEE", "चटर्जी", "சுப்ரமணியன்", "চট্টোপাধ্যায়", "صدیقی", "P<<IND<X"]
)
def test_the_clean_preset_changes_nothing_at_all(script: str, text: str) -> None:
    """The clean ablation is the control arm. If it corrupts even one character,
    every "effect of noise" measurement is measured against the wrong zero."""
    out, edits = OCRNoiser(NOISE_PRESETS["clean"], seed=7).corrupt(text, script)
    assert out == text
    assert edits == []


# --------------------------------------------------------------------------
# Degenerate inputs
# --------------------------------------------------------------------------


@pytest.mark.parametrize("preset", list(NOISE_PRESETS))
@pytest.mark.parametrize("script", SCRIPTS)
def test_an_empty_string_corrupts_to_an_empty_string(preset: str, script: str) -> None:
    """A field that was never read is represented as "". Insertion must not
    conjure a value into a field the document does not carry."""
    assert OCRNoiser(NOISE_PRESETS[preset], seed=1).corrupt("", script) == ("", [])


@pytest.mark.parametrize("preset", list(NOISE_PRESETS))
def test_protected_characters_are_never_touched(preset: str) -> None:
    """The MRZ filler is structural, not content. Corrupting it would move every
    field boundary and break the check digits for a reason that is not OCR."""
    text = "<" * 40
    out, edits = OCRNoiser(NOISE_PRESETS[preset], seed=3).corrupt(text, Script.LATIN)
    assert out == text
    assert edits == []


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_total_corruption_config_still_returns_a_string(script: str) -> None:
    """Rates of 1.0 are outside the ablation but inside the type. The model must
    degrade to an empty read, which is the real Urdu failure mode, not raise."""
    config = NoiseConfig(
        substitution_rate=1.0, deletion_rate=1.0, insertion_rate=1.0,
        diacritic_drop_rate=1.0, space_collapse_rate=1.0,
    )
    out, edits = OCRNoiser(config, seed=1).corrupt("CHATTERJEE SMITH", script)
    assert isinstance(out, str)
    assert all(e.split(":")[0].isdigit() for e in edits)


def test_a_zero_rate_config_is_the_identity_on_every_script() -> None:
    config = NoiseConfig(
        substitution_rate=0.0, deletion_rate=0.0, insertion_rate=0.0,
        homoglyph_rate=0.0, diacritic_drop_rate=0.0, space_collapse_rate=0.0,
    )
    for script in SCRIPTS:
        assert OCRNoiser(config, seed=9).corrupt("ABC DEF", script)[0] == "ABC DEF"


# --------------------------------------------------------------------------
# The edit trail
# --------------------------------------------------------------------------


def test_every_edit_is_attributed_to_a_position_in_the_input() -> None:
    """The edit list is what makes the confusion analysis possible. An edit with
    no index is an edit nobody can attribute to a character."""
    text = "BANDYOPADHYAY"
    out, edits = OCRNoiser(NOISE_PRESETS["heavy"], seed=11).corrupt(text, Script.LATIN)
    assert edits, "heavy noise on a 13-character name should do something"
    for edit in edits:
        index, kind, *_ = edit.split(":")
        assert 0 <= int(index) < len(text)
        assert kind in {
            "delete", "substitute", "insert", "homoglyph",
            "collapse_space", "drop_diacritic",
        }


def test_an_unchanged_string_reports_no_edits() -> None:
    """The edit trail and the output must not disagree about whether OCR did
    anything; `was_corrupted` in the schema trusts them both."""
    for seed in range(25):
        out, edits = OCRNoiser(NOISE_PRESETS["light"], seed=seed).corrupt("AB", Script.LATIN)
        if out == "AB":
            assert edits == []


# --------------------------------------------------------------------------
# The measured rates themselves
# --------------------------------------------------------------------------


def test_the_presets_come_from_the_calibration_not_from_the_fallbacks() -> None:
    """Decision 0004: no noise-conditioned number appears in the write-up until
    the rates are measured. This asserts M1 actually discharged that."""
    assert is_calibrated()


def test_deletion_dominates_substitution_at_every_noisy_level() -> None:
    """The M1 finding, as a regression guard. The hand-built model had this
    backwards -- substitution 8x deletion -- and the corrected shape is what
    moved the rule engine from 0.831 to 0.597. A future recalibration that
    inverts it again should have to argue with this test."""
    for level in ("light", "moderate", "heavy"):
        config = NOISE_PRESETS[level]
        assert config.deletion_rate > config.substitution_rate, level


def test_the_presets_are_ordered_by_severity() -> None:
    """clean < light < moderate < heavy, as an ablation axis must be. A ladder
    that is flat or non-monotone was shipped twice during M1."""
    order = ["clean", "light", "moderate", "heavy"]
    totals = [
        NOISE_PRESETS[name].substitution_rate
        + NOISE_PRESETS[name].deletion_rate
        + NOISE_PRESETS[name].insertion_rate
        for name in order
    ]
    assert totals == sorted(totals)
    assert totals[0] == 0.0
    assert len(set(totals)) == len(totals), "two presets are the same severity"


@pytest.mark.parametrize("name", list(NOISE_PRESETS))
def test_every_rate_is_a_probability(name: str) -> None:
    config = NOISE_PRESETS[name]
    for attribute in (
        "substitution_rate", "deletion_rate", "insertion_rate",
        "homoglyph_rate", "diacritic_drop_rate", "space_collapse_rate",
    ):
        assert 0.0 <= getattr(config, attribute) <= 1.0, f"{name}.{attribute}"


def test_heavier_noise_actually_damages_more_text() -> None:
    """The rates could be ordered while the corruption is not, if a preset stops
    reaching the code path it configures."""
    text = "BANDYOPADHYAY CHATTERJEE MUKHERJEE"
    damage = {}
    for name in ("clean", "light", "moderate", "heavy"):
        changed = sum(
            len(OCRNoiser(NOISE_PRESETS[name], seed=s).corrupt(text, Script.LATIN)[1])
            for s in range(20)
        )
        damage[name] = changed
    assert damage["clean"] == 0
    assert damage["light"] < damage["moderate"] < damage["heavy"]
