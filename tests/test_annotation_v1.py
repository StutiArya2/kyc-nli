"""Blinding and returned-sheet integrity must fail closed."""

from __future__ import annotations

import json
import zipfile

import pytest
import yaml

from kyc_nli.annotation_v1 import (
    RESPONSE_FIELDS,
    VISIBLE_FIELDS,
    check,
    prepare,
    validate_sheet,
    write_csv,
)
from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.data.io import save_instances
from kyc_nli.languages import repo_root
from kyc_nli.v1 import fingerprint


@pytest.fixture
def batch(tmp_path):
    data = tmp_path / "test.jsonl"
    save_instances(
        InstanceGenerator(
            GeneratorConfig(
                identities_per_language=12,
                seed=29,
            )
        ).generate(),
        data,
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"dataset_version": "synth_v1", "files": {"test": fingerprint(data)}})
    )
    config = tmp_path / "annotation.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "dataset_manifest": str(manifest),
                "label_definitions": str(repo_root() / "docs/label-definitions.md"),
                "output_root": str(tmp_path / "batches"),
                "seed": 20261028,
                "per_language_label": 4,
                "wrong_name_per_language": 2,
            }
        )
    )
    return prepare(config)


def test_packages_are_blank_and_private_key_is_not_shared(batch):
    manifest = json.loads((batch / "ANALYST_ONLY/manifest.json").read_text(encoding="utf-8"))
    assert manifest["n"] == manifest["distinct_identities"] == 60
    assert manifest["wrong_name_cases"] == 10
    expected = json.loads(
        (batch / "ANALYST_ONLY/expected_visible_rows.json").read_text(encoding="utf-8")
    )
    for suffix in "AB":
        with zipfile.ZipFile(batch / f"annotator_{suffix}.zip") as archive:
            assert set(archive.namelist()) == {"sheet.csv", "README.md", "LABEL_DEFINITIONS.md"}
        result = validate_sheet(batch / f"annotator_{suffix}/sheet.csv", expected)
        assert not result["complete"]
        assert all(not row[field] for row in result["rows"].values() for field in RESPONSE_FIELDS)
        assert all(
            set(row) == set(VISIBLE_FIELDS + RESPONSE_FIELDS) for row in result["rows"].values()
        )
    a = (batch / "annotator_A/sheet.csv").read_bytes()
    b = (batch / "annotator_B/sheet.csv").read_bytes()
    assert a != b


@pytest.mark.parametrize("problem", ["duplicate", "missing", "evidence", "invalid_label"])
def test_altered_or_incomplete_case_sets_are_rejected(batch, tmp_path, problem):
    expected = json.loads(
        (batch / "ANALYST_ONLY/expected_visible_rows.json").read_text(encoding="utf-8")
    )
    rows = [dict(row) for row in expected]
    if problem == "duplicate":
        rows.append(rows[0])
    elif problem == "missing":
        rows.pop()
    elif problem == "evidence":
        rows[0]["document_evidence"] += " changed"
    else:
        rows[0]["human_label"] = "invalid"
    path = tmp_path / "changed.csv"
    write_csv(path, rows, VISIBLE_FIELDS + RESPONSE_FIELDS)
    with pytest.raises(ValueError):
        validate_sheet(path, expected)


def test_blank_sheets_never_produce_agreement_metrics(batch):
    output = check(batch, batch / "annotator_A/sheet.csv", batch / "annotator_B/sheet.csv")
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "INCOMPLETE"
    assert not report["human_validation_complete"]
    assert "cohen_kappa_on_definite_only" not in report


def test_reordered_complete_sheets_do_not_prove_independence(batch, tmp_path):
    expected = json.loads(
        (batch / "ANALYST_ONLY/expected_visible_rows.json").read_text(encoding="utf-8")
    )
    rows = [dict(row, human_label="entailment") for row in expected]
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_csv(a, rows, VISIBLE_FIELDS + RESPONSE_FIELDS)
    write_csv(b, list(reversed(rows)), VISIBLE_FIELDS + RESPONSE_FIELDS)
    report = json.loads(check(batch, a, b).read_text(encoding="utf-8"))
    assert report["agreement_on_definite_only"] == 1
    assert report["cohen_kappa_on_definite_only"] is None
    assert not report["human_validation_complete"]
    assert "PROVENANCE_NOT_VERIFIED" in report["status"]
