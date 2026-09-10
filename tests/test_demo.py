"""Tests for the presentation walkthrough.

The demo is the one artefact that gets run in front of an audience, so the thing
worth testing is not that it produces the right numbers -- the evaluation tests
cover that -- but that it *never crashes*, including in every degraded state it
can find itself in: no trained model, no corpus, no benchmark on disk.
"""

from __future__ import annotations

import pytest

from kyc_nli import demo
from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.data.io import split_by_identity
from kyc_nli.languages import load_languages
from kyc_nli.schema import Label


@pytest.fixture(scope="module")
def instances():
    config = GeneratorConfig(
        languages=tuple(load_languages()), identities_per_language=12, seed=11
    )
    return split_by_identity(InstanceGenerator(config).generate())["test"]


def test_every_section_runs(instances, capsys) -> None:
    """All five sections, end to end, no exception."""
    demo.show_problem(instances)
    demo.show_labels(instances)
    demo.show_scale(instances)
    demo.show_scoreboard(instances, bootstrap=0)
    demo.show_finding()
    out = capsys.readouterr().out
    assert "MISMATCH" in out
    assert "ENTAILMENT" in out and "CONTRADICTION" in out and "NEUTRAL" in out
    assert "rule_engine" in out


def test_scoreboard_survives_a_missing_model(instances, capsys) -> None:
    """The neural model may be untrained for hours. That must not be fatal.

    A demo that depends on a 9-hour training run having finished is a demo that
    fails in front of an audience.
    """
    demo.show_scoreboard(instances, bootstrap=0)
    out = capsys.readouterr().out
    assert "exact_match" in out and "rule_engine" in out


def test_scale_section_survives_a_missing_corpus(monkeypatch, instances, capsys) -> None:
    """Dakshina is a 2 GB optional download; its absence must degrade, not crash."""
    from kyc_nli.data import corpora

    monkeypatch.setattr(corpora, "is_available", lambda: False)
    demo.show_scale(instances)
    assert "fetch-dakshina" in capsys.readouterr().out


def test_problem_section_shows_the_printed_name_not_the_ocr_damage(instances, capsys) -> None:
    """Section 1 is about cross-script matching, not OCR damage.

    Showing the corrupted value there reads as a broken font rather than as the
    argument, and it conflates two separate problems that have separate slides.
    """
    demo.show_problem(instances)
    out = capsys.readouterr().out
    pick = next(
        (
            i
            for i in instances
            if i.language in ("hi", "ta", "bn")
            and i.label is Label.ENTAILMENT
            and i.hypothesis.field.value == "surname"
        ),
        None,
    )
    if pick is None:
        pytest.skip("no suitable instance in this sample")
    viz = next(
        o for o in pick.premise if o.field.value == "surname" and o.zone.value == "viz"
    )
    assert (viz.clean_value or viz.value) in out


def test_run_accepts_a_single_step(instances, capsys, monkeypatch) -> None:
    monkeypatch.setattr(demo, "_load", lambda dataset, sample=0: instances)
    demo.run(bootstrap=0, only=5)
    out = capsys.readouterr().out
    assert "changed the project" in out
    assert "Three answers" not in out


def test_subsample_keeps_every_language_and_whole_groups(instances) -> None:
    """The demo scores a sample, so the sample must not distort the story.

    Scoring the cross-encoder over the full split takes ~6 minutes on a CPU,
    which is far too long to stand in front of. Sampling is the fix, but an
    unbalanced draw would make the per-language claim wrong, and a half-present
    contrast group would make the whole-group metric meaningless.
    """
    # Smaller than the fixture's split, or _subsample is correctly a no-op.
    sample = demo._subsample(instances, 15)
    assert 0 < len(sample) < len(instances)
    assert {i.language for i in sample} == {i.language for i in instances}

    # Any group that survives must survive intact.
    from collections import Counter

    full = Counter(i.contrast_group_id for i in instances if i.contrast_group_id)
    kept = Counter(i.contrast_group_id for i in sample if i.contrast_group_id)
    for group, n in kept.items():
        assert n == full[group], f"contrast group {group} was split by sampling"


def test_subsample_is_deterministic(instances) -> None:
    """A demo that shows different numbers each run invites the wrong question."""
    a = [i.id for i in demo._subsample(instances, 15)]
    b = [i.id for i in demo._subsample(instances, 15)]
    assert a == b


def test_subsample_is_a_noop_when_it_would_not_shrink(instances) -> None:
    assert demo._subsample(instances, 0) is instances
    assert demo._subsample(instances, len(instances) + 1) is instances
