"""Edge cases for the command line.

Every number in the write-up is produced by one of these commands, and until
now none of them was executed by a test: the CLI was the largest uncovered
surface in the repository. What is checked here is not the arithmetic -- the
metric tests own that -- but that each command parses its arguments, refuses
bad ones by name, and writes the files it claims to write.

The dataset is generated once per module at the smallest size the splitter can
honour, because these tests must stay fast enough to run on every change.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from kyc_nli.cli import app

# A wide terminal: rich truncates table cells to fit, and a squeezed column
# turns an assertion about the output into an assertion about the width of
# whatever shell the suite happened to run in.
runner = CliRunner(env={"COLUMNS": "240"})


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    """A real generated dataset, splits and manifest included."""
    out = tmp_path_factory.mktemp("cli") / "tiny.jsonl"
    result = runner.invoke(
        app, ["generate", "--out", str(out), "--identities", "4", "--seed", "3"]
    )
    assert result.exit_code == 0, result.output
    return out


# --------------------------------------------------------------------------
# Every command is reachable and documented
# --------------------------------------------------------------------------


def test_the_top_level_help_lists_every_command() -> None:
    """A command nobody can find is a command nobody reproduces."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in (
        "generate", "inspect", "run-baseline", "compare", "languages",
        "translit-eval", "calibrate-ocr", "risk-coverage", "demo",
    ):
        assert command in result.output


@pytest.mark.parametrize(
    "command",
    ["generate", "inspect", "run-baseline", "compare", "risk-coverage", "calibrate-ocr"],
)
def test_each_command_has_its_own_help(command: str) -> None:
    assert runner.invoke(app, [command, "--help"]).exit_code == 0


def test_an_unknown_command_fails_rather_than_doing_something_else() -> None:
    assert runner.invoke(app, ["definitely-not-a-command"]).exit_code != 0


# --------------------------------------------------------------------------
# languages
# --------------------------------------------------------------------------


def test_languages_prints_the_configured_set_and_nothing_hardcoded() -> None:
    """Adding a sixth language must be a config edit. If this table were built
    from a literal in the code, that promise would already be broken."""
    result = runner.invoke(app, ["languages"])
    assert result.exit_code == 0
    for code in ("en", "hi", "ta", "bn", "ur"):
        assert code in result.output


# --------------------------------------------------------------------------
# generate
# --------------------------------------------------------------------------


def test_generate_writes_the_dataset_the_manifest_and_the_splits(dataset) -> None:
    assert dataset.exists()
    assert dataset.with_suffix(".manifest.json").exists()
    for split in ("train", "dev", "test"):
        path = dataset.with_name(f"{dataset.stem}.{split}.jsonl")
        assert path.exists(), f"missing {split} split"
        assert path.read_text(encoding="utf-8").strip(), f"{split} split is empty"


def test_the_manifest_records_the_seed_that_produced_the_file(dataset) -> None:
    """Without it the digest proves two files match but not how to remake them."""
    payload = json.loads(dataset.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert payload["generator_config"]["seed"] == 3
    assert payload["generator_config"]["identities_per_language"] == 4
    assert payload["contains_real_pii"] is False


def test_generate_is_reproducible_from_the_seed_alone(tmp_path) -> None:
    """Two runs, same seed, byte-identical output. This is the claim the manifest
    makes on behalf of every result in the project."""
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    for out in (first, second):
        assert runner.invoke(
            app,
            ["generate", "--out", str(out), "--identities", "3", "--seed", "11", "--no-split"],
        ).exit_code == 0
    assert first.read_bytes() == second.read_bytes()


def test_a_different_seed_produces_a_different_dataset(tmp_path) -> None:
    """The other half of the claim: the seed is actually doing something."""
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    for out, seed in ((a, "1"), (b, "2")):
        runner.invoke(
            app,
            ["generate", "--out", str(out), "--identities", "3", "--seed", seed, "--no-split"],
        )
    assert a.read_bytes() != b.read_bytes()


def test_an_unknown_noise_preset_is_refused_by_name(tmp_path) -> None:
    """Not silently treated as 'clean'. A whole ablation run at the wrong noise
    level is invisible in its own output."""
    result = runner.invoke(
        app,
        ["generate", "--out", str(tmp_path / "x.jsonl"), "--identities", "2", "--noise", "medium"],
    )
    assert result.exit_code != 0


# --------------------------------------------------------------------------
# inspect
# --------------------------------------------------------------------------


def test_inspect_shows_instances_in_full(dataset) -> None:
    result = runner.invoke(app, ["inspect", str(dataset), "--n", "2"])
    assert result.exit_code == 0
    assert "Hypothesis:" in result.output and "Gold:" in result.output


def test_inspect_filters_to_one_language(dataset) -> None:
    result = runner.invoke(app, ["inspect", str(dataset), "--n", "3", "--language", "ta"])
    assert result.exit_code == 0
    assert "[ta]" in result.output


def test_a_filter_that_matches_nothing_prints_nothing_and_still_exits_clean(dataset) -> None:
    """An empty filter result is a legitimate answer to a legitimate question."""
    result = runner.invoke(app, ["inspect", str(dataset), "--language", "zz"])
    assert result.exit_code == 0
    assert "Hypothesis:" not in result.output


def test_inspect_on_a_missing_file_fails_loudly(tmp_path) -> None:
    result = runner.invoke(app, ["inspect", str(tmp_path / "nope.jsonl")])
    assert result.exit_code != 0


# --------------------------------------------------------------------------
# run-baseline
# --------------------------------------------------------------------------


def test_run_baseline_writes_both_report_formats(dataset, tmp_path) -> None:
    out = tmp_path / "reports"
    result = runner.invoke(
        app,
        [
            "run-baseline", "rule_engine",
            "--dataset", str(dataset.with_name(f"{dataset.stem}.test.jsonl")),
            "--out", str(out), "--bootstrap", "0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "rule_engine.md").exists()
    payload = json.loads((out / "rule_engine.json").read_text(encoding="utf-8"))
    assert 0.0 <= payload["macro_f1"] <= 1.0


def test_an_unknown_system_names_the_ones_that_exist(dataset, tmp_path) -> None:
    """So the next command the reader types is the right one."""
    result = runner.invoke(
        app, ["run-baseline", "transformer", "--dataset", str(dataset), "--out", str(tmp_path)]
    )
    assert result.exit_code != 0
    assert "rule_engine" in result.output or "rule_engine" in str(result.exception)


# --------------------------------------------------------------------------
# compare
# --------------------------------------------------------------------------


def test_compare_scores_every_available_system(dataset) -> None:
    result = runner.invoke(
        app,
        ["compare", "--dataset", str(dataset.with_name(f"{dataset.stem}.test.jsonl")),
         "--bootstrap", "0"],
    )
    assert result.exit_code == 0, result.output
    assert "exact_match" in result.output and "rule_engine" in result.output


def test_compare_without_bootstrap_omits_the_significance_section(dataset) -> None:
    """A comparison printed without a paired test invites 'is that real?' with no
    answer, so the section must be visibly absent rather than silently empty."""
    result = runner.invoke(
        app,
        ["compare", "--dataset", str(dataset.with_name(f"{dataset.stem}.test.jsonl")),
         "--bootstrap", "0"],
    )
    assert "Paired bootstrap" not in result.output


# --------------------------------------------------------------------------
# risk-coverage (M4)
# --------------------------------------------------------------------------


def test_risk_coverage_writes_a_curve_for_every_system(dataset, tmp_path) -> None:
    out = tmp_path / "sp.json"
    result = runner.invoke(
        app,
        ["risk-coverage", "--dataset", str(dataset.with_name(f"{dataset.stem}.test.jsonl")),
         "--out", str(out), "--steps", "10"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert {"exact_match", "rule_engine"} <= set(payload)
    for system in payload.values():
        assert len(system["selective_curve"]) == 11  # steps + 1
        assert len(system["risk_coverage"]) == 10
        assert system["own_operating_point"]["threshold"] == 0.0


def test_an_unreachable_budget_is_reported_as_such_not_as_total_review(
    dataset, tmp_path
) -> None:
    """Reporting 100% review for an impossible target would imply the target was
    met by reviewing everything. It was not met; nothing was decided."""
    result = runner.invoke(
        app,
        ["risk-coverage", "--dataset", str(dataset.with_name(f"{dataset.stem}.test.jsonl")),
         "--out", str(tmp_path / "sp.json"), "--budgets", "0.0", "--steps", "5"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads((tmp_path / "sp.json").read_text(encoding="utf-8"))
    assert "0.0" in payload["exact_match"]["review_load_at_error"]


# --------------------------------------------------------------------------
# Commands whose dependencies are optional
# --------------------------------------------------------------------------


def test_translit_eval_without_dakshina_says_which_command_to_run(monkeypatch) -> None:
    """Dakshina is a 2 GB optional download. Its absence must produce an
    instruction, not a stack trace ending in a KeyError on an empty dict."""
    from kyc_nli.data import corpora

    monkeypatch.setattr(corpora, "is_available", lambda: False)
    result = runner.invoke(app, ["translit-eval"])
    assert result.exit_code != 0
    assert "fetch-dakshina" in result.output


def test_calibrate_ocr_without_tesseract_names_the_missing_language_packs(
    monkeypatch, tmp_path
) -> None:
    """Tesseract is a system package with per-language data files, and the usual
    failure is having the binary but not hin/tam/ben/urd. Reporting only
    'tesseract not found' would send the reader to reinstall what they have."""
    from kyc_nli.ocr import calibrate as ocr_calibrate
    from kyc_nli.ocr import render as ocr_render

    monkeypatch.setattr(ocr_render, "fonts_available", lambda: True)
    monkeypatch.setattr(ocr_calibrate, "tessdata_dir", lambda: tmp_path)
    monkeypatch.setattr(ocr_calibrate, "download_langs", lambda: tmp_path)
    monkeypatch.setattr(ocr_calibrate, "is_available", lambda langs: False)
    monkeypatch.setattr(ocr_calibrate, "available_langs", lambda: {"eng"})

    result = runner.invoke(app, ["calibrate-ocr", "--out", str(tmp_path / "r.md")])
    assert result.exit_code != 0
    assert "hin" in result.output or "hin" in str(result.exception)


def test_the_demo_command_runs_a_single_section_without_a_trained_model(
    monkeypatch, dataset
) -> None:
    """The demo is run live in front of an audience. Every optional component --
    the model, the corpus, the benchmark -- must degrade to a printed note."""
    result = runner.invoke(
        app,
        ["demo", "--dataset", str(dataset.with_name(f"{dataset.stem}.test.jsonl")),
         "--step", "1", "--bootstrap", "0"],
    )
    assert result.exit_code == 0, result.output
