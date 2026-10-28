"""Stale or altered evaluation records must not enter manuscript outputs."""
from __future__ import annotations

import hashlib
import json

import pytest
import yaml

from kyc_nli.paper_v1 import load_records


@pytest.mark.parametrize("problem", ["changed_bytes", "legacy_dataset", "incomplete"])
def test_rejects_untraceable_paper_inputs(tmp_path, problem):
    content = {"status": "COMPLETE", "dataset_version": "synth_v1"}
    if problem == "legacy_dataset":
        content["dataset_version"] = "synth_v0"
    if problem == "incomplete":
        content["status"] = "RUNNING"
    record = tmp_path / "evaluation.json"
    record.write_text(json.dumps(content), encoding="utf-8")
    digest = hashlib.sha256(record.read_bytes()).hexdigest()
    config = tmp_path / "paper.yaml"
    config.write_text(yaml.safe_dump({"inputs": {
        name: {"path": str(record), "sha256": digest}
        for name in ("evaluation", "selective")}}), encoding="utf-8")
    if problem == "changed_bytes":
        record.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(config)
