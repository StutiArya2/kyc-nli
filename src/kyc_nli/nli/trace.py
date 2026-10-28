"""Tie a frozen evaluation to bytes, rather than to an ambiguous model name.

The historical prediction cache has no checkpoint fingerprint. It is a comparison
artifact, never a source of fresh predictions. No labels, splits or thresholds
are modified here, including the known-invalid v0 surname negatives.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import subprocess
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from kyc_nli.data.io import file_digest, load_instances
from kyc_nli.evaluation import evaluate
from kyc_nli.evaluation.significance import bootstrap_macro_f1
from kyc_nli.languages import repo_root
from kyc_nli.nli.dataset import LABELS, leaks_ground_truth, serialise_hypothesis, serialise_premise
from kyc_nli.schema import Instance, Label, Prediction


class TraceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: Literal["synth_v0"]
    test_path: Path
    train_path: Path
    dev_path: Path
    model_dir: Path
    candidate_model_dir: Path | None = None
    cache_path: Path
    audit_path: Path
    backup_path: Path
    output_root: Path
    max_length: Literal[192]
    batch_size: int = Field(ge=1)
    device: Literal["cpu"]
    threads: int = Field(ge=1)
    seed: int
    bootstrap: int = Field(ge=1000)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def _fingerprint(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": file_digest(path)}


def _prediction_index(predictions: list[Prediction], instances: list[Instance]) -> dict:
    by_id = {p.instance_id: p for p in predictions}
    expected = {x.id for x in instances}
    if len(by_id) != len(predictions) or len(expected) != len(instances):
        raise ValueError("Duplicate instance or prediction IDs")
    if set(by_id) != expected:
        raise ValueError("Prediction IDs do not exactly equal dataset IDs")
    return by_id


def _summary(instances: list[Instance], predictions: list[Prediction], config: TraceConfig) -> dict:
    by_id = _prediction_index(predictions, instances)
    result = asdict(evaluate("cross_encoder", instances, predictions,
                             bootstrap=config.bootstrap, seed=config.seed))
    decisive = [x for x in instances if by_id[x.id].label != Label.NEUTRAL]
    wrong_name = [x for x in instances if x.phenomenon == "cross_script_name_mismatch"]
    result.update({
        "label_order": [label.value for label in LABELS],
        "accuracy": sum(by_id[x.id].label == x.label for x in instances) / len(instances),
        "wrong_name_n": len(wrong_name),
        "wrong_name_predictions": dict(Counter(by_id[x.id].label.value for x in wrong_name)),
        "wrong_name_correct": sum(by_id[x.id].label == x.label for x in wrong_name),
        "default_policy": {
            "description": "Predicted neutral is reviewed; all other predictions automated",
            "automated_n": len(decisive),
            "automated_errors": sum(by_id[x.id].label != x.label for x in decisive),
            "review_n": len(instances) - len(decisive),
        },
        "per_language_macro_f1_ci": {
            language: asdict(bootstrap_macro_f1(
                [x for x in instances if x.language == language], predictions,
                n_resamples=config.bootstrap, seed=config.seed,
            ))
            for language in sorted({x.language for x in instances})
        },
    })
    return result


def compare_cache(
    instances: list[Instance], fresh: list[Prediction], cached: list[Prediction]
) -> dict:
    new = _prediction_index(fresh, instances)
    old = _prediction_index(cached, instances)
    changes = [
        {"id": x.id, "gold": x.label.value, "phenomenon": x.phenomenon,
         "fresh_label": new[x.id].label.value, "cached_label": old[x.id].label.value,
         "fresh_confidence": new[x.id].confidence, "cached_confidence": old[x.id].confidence}
        for x in instances if new[x.id].label != old[x.id].label
    ]
    return {
        "exact_test_id_match": True,
        "label_disagreements": len(changes),
        "same_label_n": len(instances) - len(changes),
        "max_absolute_confidence_difference": max(
            abs(new[x.id].confidence - old[x.id].confidence) for x in instances
        ),
        "changes": changes,
        "provenance_limit": "Cache contains no checkpoint, dataset hash or inference settings",
    }


def audit_reference(text: str) -> dict:
    """Read the supplied audit's aggregate evidence without inventing case labels."""
    matrix = []
    for label in ("Entailment", "Contradiction", "Neutral"):
        rows = [line for line in text.splitlines() if line.startswith(f"| {label} |")]
        if len(rows) != 1:
            raise ValueError(f"Cannot unambiguously parse audit confusion row {label}")
        matrix.append([int(cell.strip()) for cell in rows[0].split("|")[2:5]])
    row = next(line for line in text.splitlines()
               if line.startswith("| Cross-script wrong-name detection |"))
    fraction = row.split("|")[2].strip().split("=")[0]
    correct, total = (int(value.strip()) for value in fraction.split("/"))
    return {"confusion": matrix, "wrong_name_correct": correct, "wrong_name_n": total,
            "status": "Historical aggregate claim; original per-case predictions not supplied"}


def run_trace(config_path: Path, log=print) -> Path:
    import torch

    from kyc_nli.nli.model import CrossEncoderNLI

    config_path = _resolve(config_path)
    config = TraceConfig.model_validate(yaml.safe_load(config_path.read_text(encoding="utf-8")))
    paths = {key: _resolve(getattr(config, key)) for key in (
        "test_path", "train_path", "dev_path", "model_dir", "cache_path", "audit_path",
        "backup_path", "output_root",
    )}
    test = load_instances(paths["test_path"])
    if not test or any(x.provenance.contains_real_pii or leaks_ground_truth(x) for x in test):
        raise ValueError("Empty test set, real PII or serialized ground truth")
    split_data = {name: load_instances(paths[f"{name}_path"])
                  for name in ("train", "dev", "test")}
    identities = {name: {x.identity_id for x in rows} for name, rows in split_data.items()}
    if any(None in values for values in identities.values()):
        raise ValueError("Missing identity IDs prevent verifying split isolation")
    overlaps = {f"{a}_{b}": len(identities[a] & identities[b])
                for a, b in (("train", "dev"), ("train", "test"), ("dev", "test"))}
    if any(overlaps.values()):
        raise ValueError(f"Cross-split identity overlap: {overlaps}")
    model_files = sorted(p for p in paths["model_dir"].rglob("*") if p.is_file())
    if not any(p.suffix == ".safetensors" or p.name == "pytorch_model.bin" for p in model_files):
        raise FileNotFoundError("Actual checkpoint weights required")
    model_config = json.loads((paths["model_dir"] / "config.json").read_text(encoding="utf-8"))
    if model_config.get("model_type") != "xlm-roberta":
        raise ValueError("Expected the preserved XLM-R checkpoint")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = paths["output_root"] / stamp
    output.mkdir(parents=True, exist_ok=False)
    log(f"TRACE OUTPUT: {output}", flush=True)
    inputs = {str(p): _fingerprint(p) for p in [
        config_path, paths["test_path"], paths["train_path"], paths["dev_path"],
        paths["cache_path"], paths["audit_path"], *model_files,
    ]}
    backup = json.loads((paths["backup_path"] / "backup_manifest.json").read_text(encoding="utf-8"))
    preserved = {item["path"]: item["sha256"] for item in backup["files"]}
    for p in [paths["test_path"], paths["train_path"], paths["dev_path"],
              paths["cache_path"], *model_files]:
        if inputs[str(p)]["sha256"] != preserved[p.relative_to(repo_root()).as_posix()]:
            raise ValueError(f"Input differs from preserved state: {p}")

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=repo_root()).decode("utf-8")

    merge_head = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
        cwd=repo_root(), capture_output=True, text=True,
    ).stdout.strip() or None
    source_files = sorted((repo_root() / "src").rglob("*.py"))
    source_files += sorted((repo_root() / "configs").rglob("*.yaml"))
    source_files += [repo_root() / "pyproject.toml"]
    source = {p.relative_to(repo_root()).as_posix(): _fingerprint(p) for p in source_files}
    for p in source_files:
        dest = output / "source" / p.relative_to(repo_root())
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())
    (output / "working_tree.patch").write_text(git("diff", "HEAD", "--binary"), encoding="utf-8")
    (output / "pip_freeze.txt").write_bytes(subprocess.check_output(
        [os.sys.executable, "-m", "pip", "freeze"], cwd=repo_root(),
    ))
    audit_text = paths["audit_path"].read_text(encoding="utf-8")
    (output / "supplied_audit.md").write_text(audit_text, encoding="utf-8")
    reference = audit_reference(audit_text)
    manifest = {
        "status": "RUNNING", "created_utc": stamp,
        "config": config.model_dump(mode="json"), "inputs": inputs,
        "backup_manifest": _fingerprint(paths["backup_path"] / "backup_manifest.json"),
        "git_head": git("rev-parse", "HEAD").strip(), "git_status": git("status", "--short"),
        "git_merge_head": merge_head,
        "source_files": source, "label_index": dict(enumerate(label.value for label in LABELS)),
        "label_index_basis": "kyc_nli.nli.dataset.LABELS, also used by nli.train.to_pairs; "
                             "checkpoint config contains only generic LABEL_0/1/2 names",
        "checkpoint_id2label": model_config.get("id2label"),
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "processor": platform.processor(), "torch": torch.__version__,
                    "transformers": importlib.metadata.version("transformers")},
        "inference": {"max_length": config.max_length, "batch_size": config.batch_size,
                      "device": config.device, "threads": config.threads, "seed": config.seed,
                      "padding": "longest in batch", "truncation": True, "eval_mode": True,
                      "gradients": False, "sampling": False, "local_files_only": True},
        "split_sizes": {name: len(rows) for name, rows in split_data.items()},
        "identity_overlap": overlaps, "bootstrap_unit": "contrast_group",
        "limitations": [
            "Known v0 label defects preserved; this is not corrected-v1 performance",
            "Historical checkpoint-to-training-data byte provenance remains incomplete",
            "Aggregate audit cannot establish per-case agreement or checkpoint identity",
            "No threshold tuning or new training performed",
        ],
    }

    def write_json(name, data):
        (output / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    write_json("manifest.json", manifest)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    torch.manual_seed(config.seed)
    torch.set_num_threads(config.threads)
    torch.use_deterministic_algorithms(True)
    started = time.perf_counter()
    net = CrossEncoderNLI(paths["model_dir"], max_length=config.max_length,
                          batch_size=config.batch_size, device=config.device)
    manifest["inference"]["dtype"] = str(next(net.model.parameters()).dtype)
    manifest["inference"]["attention_implementation"] = net.model.config._attn_implementation
    manifest["inference"]["deterministic_algorithms"] = torch.are_deterministic_algorithms_enabled()
    pairs = [[serialise_premise(x), serialise_hypothesis(x)] for x in test]
    with (output / "serialized_inputs.jsonl").open("x", encoding="utf-8", newline="\n") as f:
        for x, pair in zip(test, pairs, strict=True):
            f.write(json.dumps({"id": x.id, "premise": pair[0], "hypothesis": pair[1]},
                               ensure_ascii=False) + "\n")
    lengths = [len(net.tokenizer(*pair, truncation=False)["input_ids"]) for pair in pairs]
    mismatch_lengths = [n for x, n in zip(test, lengths, strict=True)
                        if x.phenomenon == "cross_script_name_mismatch"]
    manifest["token_lengths"] = {
        "maximum": max(lengths), "over_192": sum(n > 192 for n in lengths),
        "wrong_name_maximum": max(mismatch_lengths),
        "wrong_name_over_192": sum(n > 192 for n in mismatch_lengths),
        "interpretation": "Length alone cannot change an untruncated pair's token IDs",
    }
    write_json("manifest.json", manifest)
    fresh = []
    with (output / "predictions.jsonl").open("x", encoding="utf-8", newline="\n") as f:
        for start in range(0, len(test), config.batch_size):
            batch = net.predict_all(test[start:start + config.batch_size])
            fresh.extend(batch)
            for prediction in batch:
                f.write(prediction.model_dump_json() + "\n")
            f.flush()
            if start == 0 or len(fresh) % 40 == 0 or len(fresh) == len(test):
                log(f"Predicted {len(fresh)}/{len(test)} "
                    f"({time.perf_counter() - started:.1f}s)", flush=True)

    cached = [Prediction.model_validate(p) for p in json.loads(
        paths["cache_path"].read_text(encoding="utf-8"))["cross_encoder"]]
    fresh_summary = _summary(test, fresh, config)
    cache_summary = _summary(test, cached, config)
    cache_comparison = compare_cache(test, fresh, cached)
    audit_comparison = {
        "reference": reference,
        "confusion_matches": fresh_summary["confusion"] == reference["confusion"],
        "wrong_name_count_matches": (
            fresh_summary["wrong_name_correct"] == reference["wrong_name_correct"]
        ),
        "per_case_comparison": "NOT_POSSIBLE: audit predictions/checkpoint hashes unavailable",
    }
    candidate = config.candidate_model_dir
    if candidate and _resolve(candidate).is_dir():
        manifest["alternative_checkpoint_files"] = {
            p.relative_to(_resolve(candidate)).as_posix(): _fingerprint(p)
            for p in sorted(_resolve(candidate).rglob("*")) if p.is_file()
        }
    # Fail closed if inference or a concurrent process modified an input or source.
    for path, evidence in inputs.items():
        if file_digest(Path(path)) != evidence["sha256"]:
            raise RuntimeError(f"Input changed during evaluation: {path}")
    for evidence in source.values():
        if file_digest(Path(evidence["path"])) != evidence["sha256"]:
            raise RuntimeError(f"Source changed during evaluation: {evidence['path']}")
    write_json("fresh_metrics.json", fresh_summary)
    write_json("cached_metrics.json", cache_summary)
    write_json("cache_comparison.json", cache_comparison)
    write_json("audit_comparison.json", audit_comparison)
    manifest["status"] = "COMPLETE"
    manifest["elapsed_seconds"] = time.perf_counter() - started
    manifest["inputs_unchanged_after_run"] = True
    manifest["outputs"] = {p.name: _fingerprint(p) for p in sorted(output.iterdir())
                           if p.is_file() and p.name != "manifest.json"}
    write_json("manifest.json", manifest)
    log(json.dumps({"fresh_confusion": fresh_summary["confusion"],
                    "fresh_macro_f1_ci": fresh_summary["macro_f1_ci"],
                    "fresh_wrong_name_correct": fresh_summary["wrong_name_correct"],
                    "cache_label_disagreements": cache_comparison["label_disagreements"],
                    "audit_confusion_matches": audit_comparison["confusion_matches"]}, indent=2))
    return output
