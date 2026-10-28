"""Check whether different historical weights explain conflicting surname results.

This diagnostic never substitutes an archived checkpoint for the primary local
evaluation. It runs only the already-defined wrong-name subset and retains both
sets of predictions. The CLI registers this after the primary trace completes.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from kyc_nli.data.io import file_digest, load_instances
from kyc_nli.languages import repo_root
from kyc_nli.nli.model import CrossEncoderNLI
from kyc_nli.schema import Label


class InvestigationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_dir: Path
    checkpoint_archive: Path
    audit_archive: Path
    output_root: Path


def components(path: Path) -> dict:
    """Distinguish different tensor values from a metadata-only file hash change."""
    with path.open("rb") as stream:
        size = int.from_bytes(stream.read(8), "little")
        header = stream.read(size)
        if len(header) != size:
            raise ValueError("Incomplete safetensors header")
        return {"header_sha256": hashlib.sha256(header).hexdigest(),
                "tensor_payload_sha256": hashlib.file_digest(stream, "sha256").hexdigest()}


def match_audit_inputs(serialized: list[dict], subset_ids: set[str], rows: list[dict]) -> list:
    """A v0 collision can give E and C cases identical input text; retain the C ID."""
    pairs = {(row["premise"], row["hypothesis"]): row["id"]
             for row in serialized if row["id"] in subset_ids}
    if len(pairs) != len(subset_ids):
        raise ValueError("Ambiguous duplicate inputs within the wrong-name subset")
    matched = [pairs.get((row["premise"], row["hypothesis"])) for row in rows]
    if set(matched) != subset_ids or len(matched) != len(subset_ids):
        raise ValueError("Archived audit pairs do not exactly match the primary subset")
    return matched


def run(config_path: Path) -> Path:
    import os
    import zipfile

    import torch

    def resolve(path):
        return path if path.is_absolute() else repo_root() / path

    config_path = resolve(config_path)
    config = InvestigationConfig.model_validate(
        yaml.safe_load(config_path.read_text(encoding="utf-8"))
    )
    trace = resolve(config.trace_dir)
    manifest = json.loads((trace / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "COMPLETE":
        raise ValueError("Primary frozen evaluation must complete first")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = resolve(config.output_root) / stamp
    output.mkdir(parents=True, exist_ok=False)
    print(f"INVESTIGATION OUTPUT: {output}", flush=True)
    settings = manifest["inference"]
    dataset = resolve(Path(manifest["config"]["test_path"]))
    if file_digest(dataset) != manifest["inputs"][str(dataset)]["sha256"]:
        raise ValueError("Primary test dataset changed")
    subset = [x for x in load_instances(dataset)
              if x.phenomenon == "cross_script_name_mismatch"]
    serialized = [json.loads(line) for line in
                  (trace / "serialized_inputs.jsonl").read_text(encoding="utf-8").splitlines()]
    archive_path = resolve(config.checkpoint_archive)
    audit_path = resolve(config.audit_archive)
    evidence_paths = [config_path, Path(__file__), archive_path, audit_path, dataset,
                      trace / "manifest.json", trace / "predictions.jsonl",
                      trace / "serialized_inputs.jsonl"]
    fingerprints = {str(p): file_digest(p) for p in evidence_paths}
    (output / "investigation_source.py").write_bytes(Path(__file__).read_bytes())
    (output / "config.yaml").write_bytes(config_path.read_bytes())

    with zipfile.ZipFile(audit_path) as archive:
        audit_summary = json.loads(archive.read("audit_summary.json"))
        audit_rows = list(csv.DictReader(io.StringIO(
            archive.read("cross_script_evidence_audit.csv").decode("utf-8-sig")
        )))
    matched = match_audit_inputs(serialized, {x.id for x in subset}, audit_rows)

    model_dir = output / "archived_checkpoint"
    model_dir.mkdir()
    names = ("model.safetensors", "config.json", "tokenizer.json",
             "tokenizer_config.json", "training_summary.json")
    with zipfile.ZipFile(archive_path) as archive:
        for name in names:
            with (
                archive.open("results/models/cross_encoder/" + name) as src,
                (model_dir / name).open("xb") as dest,
            ):
                shutil.copyfileobj(src, dest)
        historical_metrics = json.loads(archive.read("results/cross_encoder.json"))
    local_dir = resolve(Path(manifest["config"]["model_dir"]))
    local_weights = local_dir / "model.safetensors"
    archive_weights = model_dir / "model.safetensors"
    evidence = {
        "primary_trace": str(trace), "source_sha256": fingerprints,
        "archived_weights_sha256": file_digest(archive_weights),
        "local_weights_sha256": file_digest(local_weights),
        "archived_components": components(archive_weights),
        "local_components": components(local_weights),
        "tokenizer_bytes_identical": {
            name: file_digest(model_dir / name) == file_digest(local_dir / name)
            for name in ("tokenizer.json", "tokenizer_config.json")
        },
        "archived_training_summary": json.loads(
            (model_dir / "training_summary.json").read_text(encoding="utf-8")),
        "local_training_summary": json.loads(
            (local_dir / "training_summary.json").read_text(encoding="utf-8")),
        "audit_input_pairs_exactly_matched": len(matched),
        "audit_regenerated_test_sha256_matches_primary": (
            audit_summary["test_sha256"] == file_digest(dataset)
        ),
        "historical_full_metrics_NOT_rerun_here": historical_metrics,
        "inference_settings": settings,
        "subset": "cross_script_name_mismatch only; existing v0 labels unchanged",
    }
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    torch.manual_seed(settings["seed"])
    torch.set_num_threads(settings["threads"])
    torch.use_deterministic_algorithms(True)
    net = CrossEncoderNLI(model_dir, max_length=settings["max_length"],
                          batch_size=settings["batch_size"], device=settings["device"])
    archived = []
    with (output / "archived_subset_predictions.jsonl").open("x", encoding="utf-8") as f:
        for start in range(0, len(subset), settings["batch_size"]):
            batch = net.predict_all(subset[start:start + settings["batch_size"]])
            archived.extend(batch)
            for prediction in batch:
                f.write(prediction.model_dump_json() + "\n")
            f.flush()
            if len(archived) % 40 == 0 or len(archived) == len(subset):
                print(f"Archived checkpoint: {len(archived)}/{len(subset)}", flush=True)
    primary = {row["instance_id"]: row for row in (
        json.loads(line) for line in (trace / "predictions.jsonl").read_text().splitlines()
    )}
    evidence["subset_n"] = len(subset)
    evidence["archived_prediction_counts"] = dict(Counter(p.label.value for p in archived))
    evidence["primary_prediction_counts"] = dict(Counter(primary[x.id]["label"] for x in subset))
    evidence["archived_correct"] = sum(p.label == x.label
                                       for x, p in zip(subset, archived, strict=True))
    evidence["primary_correct"] = sum(primary[x.id]["label"] == x.label.value for x in subset)
    evidence["archived_false_entailments"] = sum(p.label == Label.ENTAILMENT for p in archived)
    evidence["limits"] = [
        "Only the wrong-name subset was rerun for archived weights; "
        "full historical score remains archived",
        "Cache has no weight fingerprint; matching predictions do not establish "
        "its historical origin",
        "Gold-label defects remain; this comparison does not establish corrected-v1 accuracy",
    ]
    with (output / "case_comparison.csv").open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "gold", "primary_label", "archived_label", "primary_confidence",
            "archived_confidence",
        ])
        writer.writeheader()
        for x, p in zip(subset, archived, strict=True):
            writer.writerow({"id": x.id, "gold": x.label.value,
                             "primary_label": primary[x.id]["label"],
                             "archived_label": p.label.value,
                             "primary_confidence": primary[x.id]["confidence"],
                             "archived_confidence": p.confidence})
    for p, digest in fingerprints.items():
        if file_digest(Path(p)) != digest:
            raise RuntimeError(f"Investigation input changed: {p}")
    evidence["status"] = "COMPLETE"
    evidence["inputs_unchanged_after_run"] = True
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({key: evidence[key] for key in (
        "subset_n", "archived_correct", "primary_correct", "archived_prediction_counts",
        "primary_prediction_counts", "tokenizer_bytes_identical",
    )}, indent=2))
    return output
