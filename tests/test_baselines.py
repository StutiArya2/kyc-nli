"""Baseline and MRZ tests."""

from __future__ import annotations

from datetime import date

from kyc_nli.baselines import ExactMatchBaseline, RuleBaseline
from kyc_nli.baselines.rules import verify_mrz_check_digits
from kyc_nli.data import mrz
from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.evaluation import evaluate
from kyc_nli.schema import Label


def test_mrz_check_digit_matches_icao_worked_example() -> None:
    """ICAO 9303 Part 3 worked example: D23145890734 -> check digit 9."""
    assert mrz.check_digit("D23145890734") == "9"


def test_td3_lines_are_44_characters() -> None:
    line1, line2 = mrz.build_td3(
        surname_latin="IVANOV",
        given_latin="IURII",
        document_number="AB1234567",
        nationality="RUS",
        date_of_birth=date(1985, 3, 12),
        sex="M",
        date_of_expiry=date(2030, 6, 1),
    )
    assert len(line1) == 44
    assert len(line2) == 44
    assert mrz.parse_mrz_name(line1) == ("IVANOV", "IURII")


def test_built_mrz_passes_its_own_check_digits() -> None:
    line1, line2 = mrz.build_td3(
        surname_latin="SMITH",
        given_latin="JOHN",
        document_number="X9876543",
        nationality="GBR",
        date_of_birth=date(1990, 1, 1),
        sex="F",
        date_of_expiry=date(2029, 12, 31),
    )
    assert all(verify_mrz_check_digits(f"{line1}\n{line2}").values())


def test_exact_match_never_predicts_neutral() -> None:
    """The incumbent system has no abstention mechanism. That is the point."""
    instances = InstanceGenerator(
        GeneratorConfig(identities_per_language=4, seed=3)
    ).generate()
    model = ExactMatchBaseline()
    assert all(model.predict(i).label is not Label.NEUTRAL for i in instances)


def test_rule_baseline_beats_exact_match_substantially() -> None:
    """If this ever fails, the rule engine has been broken, not improved."""
    instances = InstanceGenerator(
        GeneratorConfig(identities_per_language=20, seed=11)
    ).generate()

    rules = RuleBaseline()
    exact = ExactMatchBaseline()
    rules_report = evaluate("rules", instances, [rules.predict(i) for i in instances])
    exact_report = evaluate("exact", instances, [exact.predict(i) for i in instances])

    assert rules_report.macro_f1 > exact_report.macro_f1 + 0.25
    assert rules_report.false_mismatch_rate < exact_report.false_mismatch_rate


def test_rule_baseline_is_near_ceiling_without_ocr_noise() -> None:
    """The finding the whole project has to be designed around.

    On clean input the deterministic baseline is already at ~0.97 macro-F1, so
    there is almost no headroom for a neural model. If a change to the generator
    makes this drop a lot, check that it did not simply make the task
    artificially harder in a way a reviewer would call out.
    """
    instances = InstanceGenerator(
        GeneratorConfig(identities_per_language=20, seed=11, noise_preset="clean")
    ).generate()
    report = evaluate(
        "rules", instances, [RuleBaseline().predict(i) for i in instances]
    )
    assert report.macro_f1 > 0.90


def test_rule_baseline_degrades_under_heavy_noise() -> None:
    """The complementary half of the finding: noise is where the headroom is."""
    clean = InstanceGenerator(
        GeneratorConfig(identities_per_language=20, seed=11, noise_preset="clean")
    ).generate()
    noisy = InstanceGenerator(
        GeneratorConfig(identities_per_language=20, seed=11, noise_preset="heavy")
    ).generate()

    model = RuleBaseline()
    clean_f1 = evaluate("c", clean, [model.predict(i) for i in clean]).macro_f1
    noisy_f1 = evaluate("n", noisy, [model.predict(i) for i in noisy]).macro_f1
    assert clean_f1 - noisy_f1 > 0.15
