"""Prevent ambiguous caches or settings from being presented as reproduced evidence."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from kyc_nli.baselines import ExactMatchBaseline
from kyc_nli.cli import app
from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.languages import load_languages
from kyc_nli.nli.trace import TraceConfig, audit_reference, compare_cache
from kyc_nli.schema import Label


@pytest.fixture
def cases():
    instances = InstanceGenerator(GeneratorConfig(
        languages=tuple(load_languages()), identities_per_language=1, seed=7,
    )).generate()
    predictions = [ExactMatchBaseline().predict(x) for x in instances]
    return instances, predictions


def test_cache_comparison_joins_by_id_and_detects_label_changes(cases):
    instances, fresh = cases
    cached = list(reversed(fresh))
    assert compare_cache(instances, fresh, cached)["label_disagreements"] == 0
    replacement = Label.NEUTRAL if cached[0].label != Label.NEUTRAL else Label.CONTRADICTION
    cached[0] = cached[0].model_copy(update={"label": replacement})
    report = compare_cache(instances, fresh, cached)
    assert report["label_disagreements"] == 1
    assert report["changes"][0]["id"] == cached[0].instance_id


@pytest.mark.parametrize("corruption", ["duplicate", "missing", "unexpected"])
def test_cache_comparison_refuses_incompatible_case_sets(cases, corruption):
    instances, fresh = cases
    cached = list(fresh)
    if corruption == "duplicate":
        cached.append(cached[0])
    elif corruption == "missing":
        cached.pop()
    else:
        cached[0] = cached[0].model_copy(update={"instance_id": "unexpected-id"})
    with pytest.raises(ValueError):
        compare_cache(instances, fresh, cached)


def test_audit_reference_requires_unambiguous_aggregate_rows():
    text = "\n".join([
        "| Entailment | 271 | 29 | 0 |", "| Contradiction | 146 | 304 | 0 |",
        "| Neutral | 0 | 0 | 300 |",
        "| Cross-script wrong-name detection | 8 / 150 = 5.33% | historical |",
    ])
    report = audit_reference(text)
    assert report["confusion"] == [[271, 29, 0], [146, 304, 0], [0, 0, 300]]
    assert report["wrong_name_correct"] == 8
    with pytest.raises(ValueError, match="unambiguously"):
        audit_reference(text + "\n| Entailment | 1 | 2 | 3 |")


def test_trace_configuration_refuses_the_wrapper_default_length():
    import yaml

    from kyc_nli.languages import repo_root

    raw = yaml.safe_load((repo_root() / "configs/experiments/v0_trace.yaml").read_text())
    assert TraceConfig.model_validate(raw).max_length == 192
    raw["max_length"] = 256
    with pytest.raises(ValidationError):
        TraceConfig.model_validate(raw)


def test_trace_cli_passes_the_requested_configuration(monkeypatch, tmp_path):
    calls = []

    def run(config):
        calls.append(config)
        return tmp_path

    monkeypatch.setattr("kyc_nli.nli.trace.run_trace", run)
    result = CliRunner().invoke(app, ["trace-v0", "--config", "configs/custom.yaml"])
    assert result.exit_code == 0, result.output
    assert calls == [Path("configs/custom.yaml")]


def test_archive_diagnostic_distinguishes_payload_changes_from_header_changes(tmp_path):
    import runpy

    from kyc_nli.languages import repo_root

    components = runpy.run_path(str(repo_root() / "scripts/investigate_v0_trace.py"))["components"]

    def checkpoint(name, header, payload):
        path = tmp_path / name
        path.write_bytes(len(header).to_bytes(8, "little") + header + payload)
        return components(path)

    first = checkpoint("a", b"metadata A", b"tensor values")
    metadata_changed = checkpoint("b", b"metadata B", b"tensor values")
    values_changed = checkpoint("c", b"metadata A", b"other tensor values")
    assert first["header_sha256"] != metadata_changed["header_sha256"]
    assert first["tensor_payload_sha256"] == metadata_changed["tensor_payload_sha256"]
    assert first["tensor_payload_sha256"] != values_changed["tensor_payload_sha256"]


def test_audit_input_matching_keeps_the_contradiction_id_when_gold_inputs_collide():
    import runpy

    from kyc_nli.languages import repo_root

    match = runpy.run_path(str(repo_root() / "scripts/investigate_v0_trace.py"))[
        "match_audit_inputs"
    ]
    rows = [
        {"id": "group-c", "premise": "evidence", "hypothesis": "claim"},
        {"id": "group-e", "premise": "evidence", "hypothesis": "claim"},
    ]
    audit = [{"premise": "evidence", "hypothesis": "claim"}]
    assert match(rows, {"group-c"}, audit) == ["group-c"]
    with pytest.raises(ValueError, match="Ambiguous"):
        match(rows, {"group-c", "group-e"}, audit)
