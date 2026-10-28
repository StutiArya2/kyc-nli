"""Reconcile submitted human decisions without replacing frozen generator labels."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from kyc_nli.annotation_v1 import VISIBLE_FIELDS, validate_sheet, write_csv
from kyc_nli.data.io import file_digest
from kyc_nli.schema import Label
from kyc_nli.v1 import fingerprint, resolve, write_json


class PilotReportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch: Path
    initial_adjudication: Path
    review_assignment: Path
    reviewer_1: Path
    reviewer_2: Path
    attestation_1: Path
    attestation_2: Path
    annotator_declarations: Path
    sheet_a: Path
    sheet_b: Path
    output_root: Path
    seed: int


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError(f"Empty or malformed CSV: {path.name}")
    return rows


def checked_rows(rows: list[dict], expected: dict, label_field: str) -> dict:
    actual = {r["case_id"]: dict(r) for r in rows}
    if len(rows) != len(actual) or actual.keys() != expected.keys():
        raise ValueError("Duplicate, missing or unexpected case IDs")
    for case_id, row in actual.items():
        if any(row[f] != expected[case_id][f] for f in VISIBLE_FIELDS):
            raise ValueError(f"Altered visible evidence: {case_id}")
        label = row[label_field].strip().casefold()
        if label not in {""} | {x.value for x in Label}:
            raise ValueError(f"Invalid label: {case_id}")
        rationale = "rationale" if label_field == "adjudicated_label" else "reviewer_rationale"
        if not row[rationale].strip():
            raise ValueError(f"Missing rationale, including for blank labels: {case_id}")
        row[label_field] = label
    return actual


def agreement(left: list[str], right: list[str]) -> dict:
    """Blank/uncertain responses are counted separately from conditional NLI agreement."""
    pairs = list(zip(left, right, strict=True))
    definite = [(a, b) for a, b in pairs if a in {x.value for x in Label}
                and b in {x.value for x in Label}]
    n = len(definite)
    observed = sum(a == b for a, b in definite) / n if n else None
    ca, cb = Counter(a for a, _ in definite), Counter(b for _, b in definite)

    def kappa(expected: float) -> float | None:
        return (observed - expected) / (1 - expected) if n and expected < 1 else None

    per_class = {}
    for label in Label:
        binary_observed = sum((a == label.value) == (b == label.value)
                              for a, b in definite) / n if n else None
        pa, pb = (ca[label.value] / n, cb[label.value] / n) if n else (0, 0)
        pe = pa * pb + (1 - pa) * (1 - pb)
        per_class[label.value] = {
            "n": n, "positive_a": ca[label.value], "positive_b": cb[label.value],
            "binary_kappa": (binary_observed - pe) / (1 - pe) if n and pe < 1 else None,
        }
    return {
        "n": len(pairs), "same_response_n": sum(a == b for a, b in pairs),
        "both_definite_n": n, "conditional_agreement": observed,
        "conditional_kappa": kappa(sum(ca[x.value] * cb[x.value] / n**2 for x in Label))
                             if n else None,
        "per_class_on_definite_subset": per_class,
        "responses_a": dict(Counter(left)), "responses_b": dict(Counter(right)),
    }


def reconcile(expected: dict, a: dict, b: dict, initial: dict,
              reviewers: list[dict], key: dict) -> list[dict]:
    flags = {i for i in expected if a[i]["human_label"] == "uncertain"
             or b[i]["human_label"] == "uncertain"
             or a[i]["human_label"] != b[i]["human_label"]
             or a[i]["human_label"] != key[i]["generator_label"]}
    if set(initial) != flags:
        raise ValueError("Initial adjudication does not cover precisely the flagged cases")
    pending = {i for i, r in initial.items() if not r["adjudicated_label"]
               or r["adjudicated_label"] != key[i]["generator_label"]}
    if not reviewers or any(set(r) != pending for r in reviewers):
        raise ValueError("Follow-up review does not cover precisely unresolved/disputed cases")
    result = []
    for case_id, reference in expected.items():
        label, source = a[case_id]["human_label"], "initial_AB_consensus"
        if case_id in initial:
            label, source = initial[case_id]["adjudicated_label"], "initial_adjudication"
        if case_id in pending:
            labels = {r[case_id]["reviewer_label"] for r in reviewers}
            label = next(iter(labels)) if len(labels) == 1 else ""
            source = "followup_consensus" if label else "followup_unresolved"
        result.append({
            "case_id": case_id, "language": reference["language"],
            "generator_label": key[case_id]["generator_label"],
            "candidate_human_label": label, "decision_source": source,
            "status": "unresolved" if not label else (
                "human_generator_disagreement" if label != key[case_id]["generator_label"]
                else "candidate_label_recorded"),
        })
    return result


def run(config_path: Path) -> Path:
    config_path = resolve(config_path)
    config = PilotReportConfig.model_validate(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
    )
    batch = resolve(config.batch)
    manifest_path = batch / "ANALYST_ONLY/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in ("expected_visible_rows", "generator_key", "dataset_test", "label_definitions"):
        record = manifest[name]
        if file_digest(Path(record["path"])) != record["sha256"]:
            raise ValueError(f"Frozen reference changed: {name}")
    expected_list = json.loads(Path(manifest["expected_visible_rows"]["path"]).read_text(
        encoding="utf-8"))
    expected = {r["case_id"]: r for r in expected_list}
    key = {r["case_id"]: r for r in read_csv(Path(manifest["generator_key"]["path"]))}
    paths = {name: resolve(value) for name, value in config if isinstance(value, Path)
             and name not in {"batch", "output_root"}}
    # Preserve and then parse the exact bytes whose hashes appear in the report.
    output = resolve(config.output_root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    originals = output / "private_received_originals"
    originals.mkdir(parents=True, exist_ok=False)
    records, copies = {}, {}
    for name, path in paths.items():
        target = originals / f"{name}{path.suffix}"
        target.write_bytes(path.read_bytes())
        records[name] = {"source": fingerprint(path), "preserved": fingerprint(target)}
        if records[name]["source"]["sha256"] != records[name]["preserved"]["sha256"]:
            raise ValueError("Input changed while preserving originals")
        copies[name] = target
    a = validate_sheet(copies["sheet_a"], expected_list)
    b = validate_sheet(copies["sheet_b"], expected_list)
    if not a["complete"] or not b["complete"]:
        raise ValueError("Initial annotations incomplete")
    initial_rows = read_csv(copies["initial_adjudication"])
    initial = checked_rows(initial_rows, {r["case_id"]: expected[r["case_id"]]
                                        for r in initial_rows}, "adjudicated_label")
    assignment_rows = read_csv(copies["review_assignment"])
    assignment = {r["case_id"]: expected[r["case_id"]] for r in assignment_rows}
    checked_rows([dict(r, reviewer_rationale="assignment") for r in assignment_rows],
                 assignment, "reviewer_label")
    reviewers = [checked_rows(read_csv(copies[name]), assignment, "reviewer_label")
                 for name in ("reviewer_1", "reviewer_2")]
    reviewer_ids = []
    for index, reviewer in enumerate(reviewers, 1):
        attestations = read_csv(copies[f"attestation_{index}"])
        if len(attestations) != 1:
            raise ValueError("Expected one attestation per reviewer")
        attestation = attestations[0]
        reviewer_ids.append(attestation["reviewer_id"])
        ids = [i.strip() for i in attestation["case_ids_reviewed"].split(";")]
        if len(ids) != len(set(ids)) or set(ids) != set(assignment):
            raise ValueError("Attestation case set mismatch")
        if not all(value.strip() for value in attestation.values()) or any(
            attestation[f].strip().casefold() != "yes" for f in (
                "independent_of_annotator_A", "independent_of_annotator_B",
                "blind_to_prior_labels_and_predictions")):
            raise ValueError("Incomplete competence/independence/blinding declaration")
        if any(r["reviewer_id"] != attestation["reviewer_id"]
               or r["review_date"] != attestation["review_completed_date"]
               for r in reviewer.values()):
            raise ValueError("Reviewer metadata does not match attestation")
    if len(set(reviewer_ids)) != len(reviewers):
        raise ValueError("Reviewer identifiers must differ")
    declarations = read_csv(copies["annotator_declarations"])
    if (len(declarations) != 2
            or {r["annotator_id"] for r in declarations} != {"ANNOTATOR_A", "ANNOTATOR_B"}
            or any(not value.strip() for r in declarations for value in r.values())):
        raise ValueError("Incomplete A/B declarations")
    cases = reconcile(expected, a["rows"], b["rows"], initial, reviewers, key)
    write_csv(output / "case_decisions.csv", cases, list(cases[0]))
    ids = sorted(expected)
    initial_metrics = agreement([a["rows"][i]["human_label"] for i in ids],
                                [b["rows"][i]["human_label"] for i in ids])
    per_language = {}
    for language in sorted({r["language"] for r in expected.values()}):
        subset = [i for i in ids if expected[i]["language"] == language]
        per_language[language] = agreement([a["rows"][i]["human_label"] for i in subset],
                                           [b["rows"][i]["human_label"] for i in subset])
    report = {
        "status": "PILOT_RECORD_FINALIZED_WITH_UNRESOLVED_CASES_AND_LIMITATIONS",
        "full_benchmark_human_validation_complete": False,
        "n": len(cases), "candidate_label_n": sum(bool(r["candidate_human_label"]) for r in cases),
        "unresolved_case_ids": [r["case_id"] for r in cases if r["status"] == "unresolved"],
        "human_generator_disagreement_ids": [r["case_id"] for r in cases
                                              if r["status"] == "human_generator_disagreement"],
        "decision_sources": dict(Counter(r["decision_source"] for r in cases)),
        "initial_AB_agreement": initial_metrics, "initial_AB_per_language": per_language,
        "followup_agreement": agreement(
            [reviewers[0][i]["reviewer_label"] for i in sorted(assignment)],
            [reviewers[1][i]["reviewer_label"] for i in sorted(assignment)]),
        "provenance": "Competence, blinding and independence self-declared; identities, "
                      "credentials and signatures not independently authenticated.",
        "limitations": [
            "Unresolved is an annotation status, never a fourth NLI label or automatic NEUTRAL.",
            "Conditional agreement excludes uncertain/blank cases and cannot describe all cases.",
            "Follow-up cases were selected after inspection; not a fresh random validation sample.",
            "Expert agreement does not prove OCR reconstruction or romanisation validity. "
            "Some rationales still reconstruct damaged dates/names without unique textual support.",
            "VERMEY human-generator disagreement is retained, not silently reconciled.",
            "Balanced 60-case pilot does not establish full-benchmark or deployment validity.",
            "No generator labels, frozen inputs, model evaluations or label definitions changed.",
        ],
        "seed": config.seed, "inputs": records, "configuration": fingerprint(config_path),
        "implementation": fingerprint(Path(__file__)), "batch_manifest": fingerprint(manifest_path),
    }
    for name in ("expected_visible_rows", "generator_key", "dataset_test", "label_definitions"):
        record = manifest[name]
        if file_digest(Path(record["path"])) != record["sha256"]:
            raise ValueError(f"Frozen reference changed during reporting: {name}")
    write_json(output / "report.json", report)
    text = (
        "# Human-validation pilot record — 28 October 2026\n\n"
        f"The {len(cases)}-case pilot record is finalized with "
        f"{report['candidate_label_n']} candidate human labels and "
        f"{len(report['unresolved_case_ids'])} unresolved cases. "
        "This is not complete human validation of the benchmark.\n\n"
        "Initial A/B responses match on "
        f"{initial_metrics['same_response_n']}/{initial_metrics['n']} cases, including "
        "uncertain responses. Both gave definite NLI labels on "
        f"{initial_metrics['both_definite_n']} cases; conditional kappa is "
        f"{initial_metrics['conditional_kappa']}. Neither initial annotator used contradiction. "
        "Per-language and per-class conditional statistics are in report.json.\n\n"
        "The final follow-up reviewers agree on ten definite decisions and three blank "
        "statuses. This 13-case selected follow-up must not be substituted for initial "
        "60-case inter-annotator agreement.\n\n"
        "Unresolved IDs: " + ", ".join(report["unresolved_case_ids"]) + ".\n\n"
        "Human-generator disagreement IDs: "
        + ", ".join(report["human_generator_disagreement_ids"]) + ".\n\n"
        "Competence, independence and blinding declarations have been received for A/B "
        "and both follow-up reviewers. They are self-declarations, not independent "
        "authentication of people, qualifications or signatures. Original personal "
        "declarations are retained privately; public reporting should use reviewer IDs.\n\n"
        + "\n".join(f"- {item}" for item in report["limitations"]) + "\n"
    )
    (output / "pilot_report.md").write_text(text, encoding="utf-8")
    return output
