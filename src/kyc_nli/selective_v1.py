"""Dev-locked selective policies on the frozen v1 predictions.

Reuse the completed test inference and run only dev inference. Classification
results on this test have already been inspected; this is not a new blind test.
No threshold may be chosen from test labels or test operating points.
"""

from __future__ import annotations

import gc
import json
import math
import os
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field

from kyc_nli.baselines import ExactMatchBaseline, RuleBaseline
from kyc_nli.data.io import file_digest, load_instances
from kyc_nli.evaluation import review_load_at_error
from kyc_nli.nli.dataset import LABELS, leaks_ground_truth
from kyc_nli.schema import Instance, Label, Prediction
from kyc_nli.v1 import (
    EvaluationConfig,
    capture_source,
    fingerprint,
    resolve,
    score,
    write_json,
)


class SelectiveConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_config: Path
    reference_evaluation: Path
    output_root: Path
    error_budgets: list[float] = Field(min_length=1)
    curve_steps: int = Field(ge=1)


def prediction_index(instances: list[Instance], predictions: list[Prediction]) -> dict:
    result = {p.instance_id: p for p in predictions}
    if (len(result) != len(predictions) or len({x.id for x in instances}) != len(instances)
            or set(result) != {x.id for x in instances}):
        raise ValueError("Duplicate, missing or extra prediction/instance IDs")
    return result


def choose_on_dev(dev: list[Instance], predictions: list[Prediction], budgets: list[float]) -> dict:
    prediction_index(dev, predictions)
    choices = {}
    for budget in budgets:
        if not 0 < budget < 1:
            raise ValueError("Error budgets must be strictly between zero and one")
        point = review_load_at_error(dev, predictions, max_error=budget)
        choices[str(budget)] = {
            "status": "LOCKED_ON_DEV" if point else "NO_NONEMPTY_DEV_OPERATING_POINT",
            "threshold": point.threshold if point else None,
            "dev": asdict(point) if point else None,
        }
    return choices


def wilson(errors: int, total: int) -> list[float] | None:
    if not total:
        return None
    z = NormalDist().inv_cdf(0.975)
    p = errors / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, centre - half), min(1.0, centre + half)]


def policy_arrays(
    instances: list[Instance], predictions: list[Prediction], threshold: float,
) -> tuple:
    by_id = prediction_index(instances, predictions)
    automated = np.array([by_id[x.id].label != Label.NEUTRAL
                          and by_id[x.id].confidence >= threshold for x in instances], dtype=bool)
    wrong = np.array([by_id[x.id].label != x.label for x in instances], dtype=bool)
    return automated, automated & wrong


def policy_stats(
    instances: list[Instance], predictions: list[Prediction], threshold: float,
) -> dict:
    accepted, errors = policy_arrays(instances, predictions, threshold)
    n, e = int(accepted.sum()), int(errors.sum())
    return {"threshold": threshold, "coverage": n / len(instances),
            "review_load": 1 - n / len(instances), "automated_n": n, "automated_errors": e,
            "automated_error_rate": e / n if n else None,
            "wilson_95_ci_iid_reference_only": wilson(e, n),
            "statistical_guarantee": False}


def cluster_samples(instances: list[Instance], count: int, seed: int) -> list[np.ndarray]:
    groups = defaultdict(list)
    for index, instance in enumerate(instances):
        if not instance.contrast_group_id:
            raise ValueError("Contrast-group IDs required by the frozen bootstrap protocol")
        groups[instance.contrast_group_id].append(index)
    members = [np.array(groups[key]) for key in sorted(groups)]
    rng = np.random.default_rng(seed)
    return [np.concatenate([members[j] for j in rng.integers(0, len(members), len(members))])
            for _ in range(count)]


def uncertainty(instances: list[Instance], predictions: list[Prediction], threshold: float,
                samples: list[np.ndarray]) -> tuple:
    accepted, errors = policy_arrays(instances, predictions, threshold)
    coverage = np.array([float(accepted[index].mean()) for index in samples])
    risks = [float(errors[index].sum() / accepted[index].sum())
             for index in samples if accepted[index].any()]
    review = 1 - coverage
    return {
        "coverage_95_ci": np.quantile(coverage, [0.025, 0.975]).tolist(),
        "review_load_95_ci": np.quantile(review, [0.025, 0.975]).tolist(),
        "automated_error_95_ci": np.quantile(risks, [0.025, 0.975]).tolist() if risks else None,
        "undefined_risk_resamples": len(samples) - len(risks),
        "bootstrap_unit": "contrast_group", "n_resamples": len(samples),
        "scope": "Test resampling conditional on the dev-locked threshold",
    }, review


def run(config_path: Path) -> Path:
    import torch

    from kyc_nli.nli.model import CrossEncoderNLI

    config_path = resolve(config_path)
    config = SelectiveConfig.model_validate(yaml.safe_load(config_path.read_text(encoding="utf-8")))
    pipeline_path = resolve(config.evaluation_config)
    pipeline = EvaluationConfig.model_validate(
        yaml.safe_load(pipeline_path.read_text(encoding="utf-8")),
    )
    reference = resolve(config.reference_evaluation)
    original = json.loads((reference / "start.json").read_text(encoding="utf-8"))
    completed = json.loads((reference / "summary.json").read_text(encoding="utf-8"))
    if (completed["status"] != "COMPLETE"
            or original["configuration"] != pipeline.model_dump(mode="json")):
        raise ValueError("Completed reference run and identical inference configuration required")
    if original["label_index"] != {str(i): label.value for i, label in enumerate(LABELS)}:
        raise ValueError("Reference label mapping differs")
    # The model, serializer and scorer must match the source used for test inference.
    for relative in ("src/kyc_nli/nli/model.py", "src/kyc_nli/nli/dataset.py",
                     "src/kyc_nli/evaluation/metrics.py", "src/kyc_nli/v1.py"):
        if file_digest(resolve(Path(relative))) != original["source_files"][relative]["sha256"]:
            raise ValueError(f"Reference inference/scoring source changed: {relative}")
    manifest_path = resolve(pipeline.dataset_manifest)
    dataset = json.loads(manifest_path.read_text(encoding="utf-8"))
    if dataset["dataset_version"] != "synth_v1":
        raise ValueError("Frozen v1 data required")
    inputs = {str(path): fingerprint(path) for path in (
        config_path, pipeline_path, manifest_path,
        reference / "start.json", reference / "summary.json",
    )}
    for record in dataset["files"].values():
        if file_digest(Path(record["path"])) != record["sha256"]:
            raise ValueError("Frozen v1 hash mismatch")
        inputs[record["path"]] = record
    for key, evidence in original["inputs"].items():
        if file_digest(Path(key)) != evidence["sha256"]:
            raise ValueError(f"Reference evaluation input changed: {key}")
        inputs[key] = evidence
    dev = load_instances(Path(dataset["files"]["dev"]["path"]))
    test = load_instances(Path(dataset["files"]["test"]["path"]))
    if {x.identity_id for x in dev} & {x.identity_id for x in test}:
        raise ValueError("Dev/test identity overlap")
    if any(x.provenance.contains_real_pii or leaks_ground_truth(x) for x in dev):
        raise ValueError("Invalid dev inputs")
    for name in completed["systems"]:
        path = reference / name / "predictions.jsonl"
        inputs[str(path)] = fingerprint(path)
    output = resolve(config.output_root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output.mkdir(parents=True, exist_ok=False)
    print(f"V1 SELECTIVE OUTPUT: {output}", flush=True)
    source = capture_source(output)
    write_json(output / "start.json", {
        "configuration": config.model_dump(mode="json"),
        "inference": pipeline.model_dump(mode="json"),
        "inputs": inputs, "source_files": source, "reference_evaluation": str(reference),
        "test_policy": "Reuse previous fixed test inference; select all thresholds from dev only",
        "bootstrap_unit": "contrast_group", "n_resamples": pipeline.bootstrap,
        "limitations": ["Test classification results were previously inspected",
                        "Contrast-group bootstrap retains the repository protocol",
                        "Wilson intervals assume iid and are auxiliary, not clustered guarantees",
                        "Uncertainty is conditional on dev-selected thresholds; "
                        "dev is not resampled",
                        "Synthetic evaluation only; no deployment risk guarantee"],
    })
    torch.manual_seed(pipeline.seed)
    torch.set_num_threads(pipeline.threads)
    torch.use_deterministic_algorithms(True)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    samples = cluster_samples(test, pipeline.bootstrap, pipeline.seed)
    reports, review_samples = {}, {}
    for name in ["exact_match", "rule_engine", *pipeline.checkpoints]:
        target = output / name
        target.mkdir()
        if name in pipeline.checkpoints:
            checkpoint = pipeline.checkpoints[name]
            path = resolve(checkpoint.path)
            if file_digest(path / "model.safetensors") != checkpoint.sha256:
                raise ValueError(f"Checkpoint mismatch: {name}")
            model = CrossEncoderNLI(path, max_length=pipeline.max_length,
                                    batch_size=pipeline.batch_size, device="cpu")
        else:
            model = ExactMatchBaseline() if name == "exact_match" else RuleBaseline()
        predicted = []
        with (target / "dev_predictions.jsonl").open("x", encoding="utf-8") as stream:
            for start in range(0, len(dev), pipeline.batch_size):
                batch = dev[start:start + pipeline.batch_size]
                items = (model.predict_all(batch) if name in pipeline.checkpoints
                         else [model.predict(x) for x in batch])
                predicted.extend(items)
                for item in items:
                    stream.write(item.model_dump_json() + "\n")
                stream.flush()
                if name in pipeline.checkpoints and (
                    len(predicted) % 80 == 0 or len(predicted) == len(dev)
                ):
                    print(f"{name} dev: {len(predicted)}/{len(dev)}", flush=True)
        choices = choose_on_dev(dev, predicted, config.error_budgets)
        # Persist every dev choice before reading that system's test predictions.
        lock_path = target / "dev_thresholds.json"
        write_json(lock_path, {"choices": choices, "selected_on": "dev",
                              "dev_sha256": dataset["files"]["dev"]["sha256"]})
        test_predictions = [Prediction.model_validate_json(line) for line in
                            (reference / name / "predictions.jsonl").read_text(
                                encoding="utf-8").splitlines()]
        if score(name, test, test_predictions, pipeline) != completed["systems"][name]:
            raise ValueError("Reference prediction labels/metrics do not reproduce")
        result = {"default_test": policy_stats(test, test_predictions, 0.0),
                  "threshold_lock": fingerprint(lock_path), "budgets": {}}
        review_samples[name] = {}
        for budget, choice in choices.items():
            if choice["threshold"] is None:
                result["budgets"][budget] = choice
                continue
            threshold = choice["threshold"]
            applied = policy_stats(test, test_predictions, threshold)
            applied["point_estimate_meets_budget"] = (
                applied["automated_n"] > 0 and applied["automated_error_rate"] <= float(budget)
            )
            interval, draws = uncertainty(test, test_predictions, threshold, samples)
            result["budgets"][budget] = {**choice, "test": applied, "test_uncertainty": interval}
            review_samples[name][budget] = draws
        result["test_curve_diagnostic_only"] = [
            policy_stats(test, test_predictions, k / config.curve_steps)
            for k in range(config.curve_steps + 1)
        ]
        write_json(target / "selective.json", result)
        reports[name] = result
        print(f"{name}: dev thresholds locked and test policy scored", flush=True)
        del model
        gc.collect()
    comparisons = {}
    for name in pipeline.checkpoints:
        pairs = {}
        for budget in map(str, config.error_budgets):
            a = reports[name]["budgets"][budget]
            b = reports["rule_engine"]["budgets"][budget]
            if "test" not in a or "test" not in b:
                pairs[budget] = {"status": "NO_PAIRED_DEV_OPERATING_POINT"}
                continue
            diff = review_samples[name][budget] - review_samples["rule_engine"][budget]
            pairs[budget] = {
                "status": "PAIRED_FIXED_DEV_POLICIES", "delta_model_minus_rule_review":
                    a["test"]["review_load"] - b["test"]["review_load"],
                "95_ci": np.quantile(diff, [0.025, 0.975]).tolist(),
                "both_test_point_estimates_meet_budget": (
                    a["test"]["point_estimate_meets_budget"] and
                    b["test"]["point_estimate_meets_budget"]
                ),
                "scope": "Comparison at a common requested budget; realized test risks may differ",
            }
        comparisons[f"{name}-rule_engine"] = pairs
    for evidence in [*inputs.values(), *source.values()]:
        if file_digest(Path(evidence["path"])) != evidence["sha256"]:
            raise RuntimeError(f"Input or source changed: {evidence['path']}")
    write_json(output / "summary.json", {"status": "COMPLETE", "dataset_version": "synth_v1",
                                       "systems": reports, "paired_review_differences": comparisons,
                                       "inputs_unchanged_after_run": True})
    return output
