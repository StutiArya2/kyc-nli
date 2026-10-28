"""Freeze the targeted surname-label repair and score independently named weights.

The v0 identity and OCR streams stay fixed. Only invalid negative hypotheses
change, so evaluating a frozen v0-trained checkpoint does not require retraining.
"""

from __future__ import annotations

import csv
import gc
import importlib.metadata
import json
import os
import platform
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField

from kyc_nli.baselines import ExactMatchBaseline, RuleBaseline
from kyc_nli.data.generate import (
    GeneratorConfig,
    InstanceGenerator,
    accepted_surnames,
    normalise_surname,
)
from kyc_nli.data.io import file_digest, load_instances, split_by_identity
from kyc_nli.evaluation import evaluate, paired_bootstrap
from kyc_nli.evaluation.significance import bootstrap_macro_f1
from kyc_nli.languages import load_languages, repo_root
from kyc_nli.nli.dataset import LABELS, leaks_ground_truth, serialise_hypothesis, serialise_premise
from kyc_nli.schema import Field, Label, Zone


class FreezeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_version: Literal["synth_v1"]
    identities_per_language: int = PydanticField(ge=3)
    noise_preset: str
    seed: int
    alt_romanisation_rate: float = PydanticField(ge=0, le=1)
    reference_v0: Path
    output: Path


class CheckpointConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: Path
    sha256: str


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_manifest: Path
    training_reference: Path
    output_root: Path
    seed: int
    bootstrap: int = PydanticField(ge=1000)
    max_length: Literal[192]
    batch_size: int = PydanticField(ge=1)
    threads: int = PydanticField(ge=1)
    checkpoints: dict[str, CheckpointConfig]


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False))


def fingerprint(path: Path) -> dict:
    return {"path": str(path), "sha256": file_digest(path), "bytes": path.stat().st_size}


def capture_source(output: Path) -> dict:
    files = sorted((repo_root() / "src").rglob("*.py"))
    files += sorted((repo_root() / "configs").rglob("*.yaml"))
    result = {}
    for path in files:
        relative = path.relative_to(repo_root())
        target = output / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        result[relative.as_posix()] = fingerprint(path)
    return result


def validate_dataset(instances: list, splits: dict) -> dict:
    if not instances or len({x.id for x in instances}) != len(instances):
        raise ValueError("Empty dataset or duplicate IDs")
    if any(x.provenance.contains_real_pii or leaks_ground_truth(x) for x in instances):
        raise ValueError("Real PII or ground-truth serialization leakage")
    if any(x.provenance.generator != "synthetic_v1" for x in instances):
        raise ValueError("Mixed dataset provenance")
    for key in ("identity_id", "contrast_group_id"):
        values = {name: {getattr(x, key) for x in rows} for name, rows in splits.items()}
        if any(None in ids for ids in values.values()):
            raise ValueError(f"Missing {key}")
        for a, b in (("train", "dev"), ("train", "test"), ("dev", "test")):
            if values[a] & values[b]:
                raise ValueError(f"Split leakage by {key}")
    groups = defaultdict(list)
    for instance in instances:
        if instance.contrast_group_id.endswith("-name"):
            groups[instance.contrast_group_id].append(instance.label.value)
    if any(Counter(labels) != Counter({label.value: 1 for label in Label})
           for labels in groups.values()):
        raise ValueError("Broken name E/C/N contrast group")
    negatives = [x for x in instances if x.phenomenon == "cross_script_name_mismatch"]
    if len(negatives) != len(groups):
        raise ValueError("Missing name contradictions")
    for instance in negatives:
        viz = instance.observation(Field.SURNAME, Zone.VIZ)
        mrz = instance.observation(Field.SURNAME, Zone.MRZ)
        if viz is None or mrz is None or viz.clean_value is None or mrz.clean_value is None:
            raise ValueError("Clean surname evidence required for construction audit")
        accepted = accepted_surnames(
            viz.clean_value, mrz.clean_value, viz.script, instance.language,
        )
        if normalise_surname(instance.hypothesis.value) in accepted:
            raise ValueError(f"Invalid clean-name negative: {instance.id}")
    return {"name_contradictions": len(negatives), "clean_name_alias_collisions": 0,
            "identity_overlap": 0, "contrast_group_overlap": 0,
            "ground_truth_leakage_flags": 0, "contains_real_pii": False}


def freeze(config_path: Path) -> Path:
    config_path = resolve(config_path)
    config = FreezeConfig.model_validate(yaml.safe_load(config_path.read_text(encoding="utf-8")))
    output = resolve(config.output)
    targets = {"all": output, **{name: output.with_name(f"{output.stem}.{name}.jsonl")
                               for name in ("train", "dev", "test")}}
    manifest_path = output.with_suffix(".manifest.json")
    if any(p.exists() for p in [*targets.values(), manifest_path]):
        raise FileExistsError("Frozen dataset output exists; refusing overwrite")
    generator_config = GeneratorConfig(
        languages=tuple(load_languages()), identities_per_language=config.identities_per_language,
        noise_preset=config.noise_preset, seed=config.seed,
        alt_romanisation_rate=config.alt_romanisation_rate, dataset_version=config.dataset_version,
    )
    instances = InstanceGenerator(generator_config).generate()
    repeated = InstanceGenerator(generator_config).generate()
    if [x.model_dump_json() for x in instances] != [x.model_dump_json() for x in repeated]:
        raise ValueError("Generation is not reproducible")
    splits = split_by_identity(instances)
    integrity = validate_dataset(instances, splits)
    if len(instances) != len(load_languages()) * config.identities_per_language * 7:
        raise ValueError("Unexpected dataset cardinality")
    reference_path = resolve(config.reference_v0)
    reference = {x.id: x for x in load_instances(reference_path)}
    if set(reference) != {x.id for x in instances}:
        raise ValueError("V1 identities/cases differ from preserved v0")
    changed = []
    for item in instances:
        old = reference[item.id]
        if item.premise != old.premise or item.identity_id != old.identity_id:
            raise ValueError("Repair shifted an identity or OCR stream")
        a, b = item.model_dump(), old.model_dump()
        a.pop("provenance")
        b.pop("provenance")
        if a != b:
            if item.phenomenon != "cross_script_name_mismatch":
                raise ValueError("Repair changed a non-negative instance")
            for key in ("hypothesis", "rationale"):
                a.pop(key)
                b.pop(key)
            if a != b:
                raise ValueError("Repair changed more than a negative hypothesis/rationale")
            changed.append(item.id)
    reference_splits = split_by_identity(list(reference.values()))
    for name in splits:
        if {x.id for x in splits[name]} != {x.id for x in reference_splits[name]}:
            raise ValueError("V1 split IDs changed")
    output.parent.mkdir(parents=True, exist_ok=True)
    for name, rows in {"all": instances, **splits}.items():
        with targets[name].open("x", encoding="utf-8", newline="\n") as stream:
            for item in sorted(rows, key=lambda x: x.id):
                stream.write(item.model_dump_json() + "\n")
    manifest = {
        "dataset_version": config.dataset_version, "configuration": asdict(generator_config),
        "freeze_config": fingerprint(config_path), "reference_v0": fingerprint(reference_path),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root(),
                                            text=True).strip(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": {name: fingerprint(path) for name, path in targets.items()},
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "label_counts": {name: dict(Counter(x.label.value for x in rows))
                         for name, rows in splits.items()},
        "integrity": integrity, "changed_negative_ids": sorted(changed),
        "changed_test_negative_ids": sorted(set(changed) & {x.id for x in splits["test"]}),
        "repeated_generation_identical": True, "v0_premises_and_split_ids_preserved": True,
        "source_files": {str(p.relative_to(repo_root())): fingerprint(p)
                         for p in sorted((repo_root() / "src").rglob("*.py"))},
        "limitations": ["Alias checks cover engine and embedded-pool equivalence only",
                        "No claim that every OCR-corrupted label has been human validated"],
    }
    write_json(manifest_path, manifest)
    print(f"Frozen v1: {manifest_path}; repaired {len(changed)} negatives", flush=True)
    return manifest_path


def score(name: str, instances: list, predictions: list, config: EvaluationConfig) -> dict:
    if len(predictions) != len(instances) or {p.instance_id for p in predictions} != {
        x.id for x in instances
    }:
        raise ValueError("Prediction IDs must exactly match the frozen test cases")
    report = asdict(evaluate(
        name, instances, predictions, bootstrap=config.bootstrap, seed=config.seed,
    ))
    by_id = {p.instance_id: p for p in predictions}
    negative = [x for x in instances if x.phenomenon == "cross_script_name_mismatch"]
    automated = [x for x in instances if by_id[x.id].label != Label.NEUTRAL]
    report.update({
        "accuracy": sum(by_id[x.id].label == x.label for x in instances) / len(instances),
        "wrong_name_n": len(negative),
        "wrong_name_correct": sum(by_id[x.id].label == x.label for x in negative),
        "wrong_name_prediction_counts": dict(Counter(by_id[x.id].label.value for x in negative)),
        "default_policy": {
            "review_n": len(instances) - len(automated), "automated_n": len(automated),
            "automated_errors": sum(by_id[x.id].label != x.label for x in automated),
        },
        "per_language_macro_f1_ci": {
            language: asdict(bootstrap_macro_f1(
                [x for x in instances if x.language == language], predictions,
                n_resamples=config.bootstrap, seed=config.seed,
            )) for language in sorted({x.language for x in instances})
        },
    })
    return report


def evaluate_v1(config_path: Path) -> Path:
    import torch

    from kyc_nli.nli.model import CrossEncoderNLI

    config_path = resolve(config_path)
    config = EvaluationConfig.model_validate(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
    )
    manifest_path = resolve(config.dataset_manifest)
    dataset = json.loads(manifest_path.read_text(encoding="utf-8"))
    if dataset["dataset_version"] != "synth_v1":
        raise ValueError("Expected corrected v1 manifest")
    for record in dataset["files"].values():
        if file_digest(Path(record["path"])) != record["sha256"]:
            raise ValueError("Frozen dataset hash mismatch")
    test = load_instances(Path(dataset["files"]["test"]["path"]))
    training_path = resolve(config.training_reference)
    training = load_instances(training_path)
    if {x.identity_id for x in test} & {x.identity_id for x in training}:
        raise ValueError("Test identities overlap the preserved training split")

    def document_numbers(rows):
        return {o.clean_value for x in rows for o in x.observations(Field.DOCUMENT_NUMBER)
                if o.clean_value}

    if document_numbers(test) & document_numbers(training):
        raise ValueError("Test document numbers overlap training")
    if any(leaks_ground_truth(x) or x.provenance.contains_real_pii for x in test):
        raise ValueError("Invalid neural inputs")
    paths = {name: resolve(checkpoint.path) for name, checkpoint in config.checkpoints.items()}
    inputs = {str(p): fingerprint(p) for p in [config_path, manifest_path, training_path]}
    inputs.update({record["path"]: record for record in dataset["files"].values()})
    for name, path in paths.items():
        if file_digest(path / "model.safetensors") != config.checkpoints[name].sha256:
            raise ValueError(f"Wrong checkpoint bytes: {name}")
        if json.loads((path / "config.json").read_text())["model_type"] != "xlm-roberta":
            raise ValueError("Expected XLM-R weights")
        for p in sorted(path.rglob("*")):
            if p.is_file():
                inputs[str(p)] = fingerprint(p)
    output = resolve(config.output_root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output.mkdir(parents=True, exist_ok=False)
    print(f"V1 EVALUATION OUTPUT: {output}", flush=True)
    source = capture_source(output)
    write_json(output / "start.json", {
        "configuration": config.model_dump(mode="json"), "inputs": inputs,
        "source_files": source, "dataset_version": "synth_v1",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root(),
                                            text=True).strip(),
        "runtime": {"python": platform.python_version(), "torch": torch.__version__,
                    "transformers": importlib.metadata.version("transformers")},
        "label_index": dict(enumerate(label.value for label in LABELS)),
        "training_overlap": {"identity_ids": 0, "document_numbers": 0},
        "bootstrap_unit": "contrast_group", "device": "cpu", "dtype": "float32",
        "limitations": ["Models trained on v0, evaluated frozen on corrected v1",
                        "Original training-data byte hashes are not available",
                        "No threshold selection; default policy only; synthetic data only"],
    })
    (output / "pip_freeze.txt").write_bytes(subprocess.check_output(
        [os.sys.executable, "-m", "pip", "freeze"], cwd=repo_root()))
    with (output / "serialized_test.jsonl").open("x", encoding="utf-8") as stream:
        for instance in test:
            stream.write(json.dumps({"id": instance.id, "premise": serialise_premise(instance),
                                     "hypothesis": serialise_hypothesis(instance)},
                                    ensure_ascii=False) + "\n")
    torch.manual_seed(config.seed)
    torch.set_num_threads(config.threads)
    torch.use_deterministic_algorithms(True)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    predictions, reports = {}, {}
    for name in ["exact_match", "rule_engine", *paths]:
        target = output / name
        target.mkdir()
        if name in paths:
            model = CrossEncoderNLI(paths[name], max_length=config.max_length,
                                    batch_size=config.batch_size, device="cpu")
        else:
            model = ExactMatchBaseline() if name == "exact_match" else RuleBaseline()
        predicted = []
        with (target / "predictions.jsonl").open("x", encoding="utf-8") as stream:
            for start in range(0, len(test), config.batch_size):
                batch = test[start:start + config.batch_size]
                items = (model.predict_all(batch) if name in paths
                         else [model.predict(x) for x in batch])
                predicted.extend(items)
                for item in items:
                    stream.write(item.model_dump_json() + "\n")
                stream.flush()
                if name in paths and (len(predicted) % 80 == 0 or len(predicted) == len(test)):
                    print(f"{name}: {len(predicted)}/{len(test)}", flush=True)
        predictions[name] = predicted
        reports[name] = score(name, test, predicted, config)
        write_json(target / "metrics.json", reports[name])
        with (target / "errors.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "identity_id", "language", "phenomenon", "gold", "predicted"])
            for x, prediction in zip(test, predicted, strict=True):
                if x.label != prediction.label:
                    writer.writerow([x.id, x.identity_id, x.language, x.phenomenon,
                                     x.label.value, prediction.label.value])
        print(f"{name}: F1 {reports[name]['macro_f1_ci']}", flush=True)
        del model
        gc.collect()
    comparisons = {}
    for name in paths:
        comparisons[f"{name}-rule_engine"] = asdict(paired_bootstrap(
            test, predictions[name], predictions["rule_engine"], name, "rule_engine",
            n_resamples=config.bootstrap, seed=config.seed,
        ))
    for evidence in [*inputs.values(), *source.values()]:
        if file_digest(Path(evidence["path"])) != evidence["sha256"]:
            raise RuntimeError(f"Input or source changed: {evidence['path']}")
    write_json(output / "summary.json", {"status": "COMPLETE", "dataset_version": "synth_v1",
                                       "systems": reports, "paired_vs_rule": comparisons,
                                       "inputs_unchanged_after_run": True})
    return output
