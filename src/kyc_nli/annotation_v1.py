"""Prepare blinded observed-input worksheets; never fabricate human judgments."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sklearn.metrics import cohen_kappa_score

from kyc_nli.data.io import file_digest, load_instances
from kyc_nli.languages import load_languages
from kyc_nli.nli.dataset import serialise_hypothesis, serialise_premise
from kyc_nli.schema import Label
from kyc_nli.v1 import fingerprint, resolve, write_json

VISIBLE_FIELDS = ["case_id", "language", "document_evidence", "claim"]
RESPONSE_FIELDS = ["human_label", "confidence_1_to_5", "notes"]
ALLOWED = {label.value for label in Label} | {"uncertain"}


class AnnotationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_manifest: Path
    label_definitions: Path
    output_root: Path
    seed: int
    per_language_label: int = Field(ge=1)
    wrong_name_per_language: int = Field(ge=0)


def select_cases(instances: list, config: AnnotationConfig) -> list:
    """Distinct identities prevent repeated premises from revealing contrast labels."""
    if config.wrong_name_per_language > config.per_language_label:
        raise ValueError("Wrong-name quota exceeds contradiction quota")
    rng = random.Random(config.seed)
    selected, used = [], set()
    for language in load_languages():
        strata = [(Label.CONTRADICTION, True, config.wrong_name_per_language),
                  (Label.CONTRADICTION, False,
                   config.per_language_label - config.wrong_name_per_language),
                  (Label.ENTAILMENT, None, config.per_language_label),
                  (Label.NEUTRAL, None, config.per_language_label)]
        for label, wrong_name, count in strata:
            if count == 0:
                continue
            eligible = sorted((x for x in instances if x.language == language and x.label == label
                               and (wrong_name is None or
                                    (x.phenomenon == "cross_script_name_mismatch") == wrong_name)),
                              key=lambda x: x.id)
            rng.shuffle(eligible)
            chosen = []
            for instance in eligible:
                if instance.identity_id and instance.identity_id not in used:
                    chosen.append(instance)
                    used.add(instance.identity_id)
                if len(chosen) == count:
                    break
            if len(chosen) != count:
                raise ValueError(f"Insufficient distinct identities for {language}/{label.value}")
            selected.extend(chosen)
    rng.shuffle(selected)
    return selected


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare(config_path: Path) -> Path:
    config_path = resolve(config_path)
    config = AnnotationConfig.model_validate(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
    )
    manifest_path = resolve(config.dataset_manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = manifest["files"]["test"]
    if (manifest["dataset_version"] != "synth_v1"
            or file_digest(Path(evidence["path"])) != evidence["sha256"]):
        raise ValueError("Frozen v1 test data required")
    instances = load_instances(Path(evidence["path"]))
    selected = select_cases(instances, config)
    expected_n = len(load_languages()) * len(Label) * config.per_language_label
    if len(selected) != expected_n:
        raise ValueError("Incomplete stratification")
    output = resolve(config.output_root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    private = output / "ANALYST_ONLY"
    private.mkdir(parents=True, exist_ok=False)
    rows, key = [], []
    for instance in selected:
        case_id = hashlib.sha256(
            f"{config.seed}:{evidence['sha256']}:{instance.id}".encode()
        ).hexdigest()[:16]
        rows.append({"case_id": case_id, "language": instance.language,
                     "document_evidence": serialise_premise(instance),
                     "claim": serialise_hypothesis(instance),
                     **dict.fromkeys(RESPONSE_FIELDS, "")})
        key.append({"case_id": case_id, "instance_id": instance.id,
                    "identity_id": instance.identity_id, "generator_label": instance.label.value,
                    "phenomenon": instance.phenomenon})
    if len({r["case_id"] for r in rows}) != expected_n:
        raise ValueError("Blinded ID collision")
    write_json(private / "expected_visible_rows.json", rows)
    write_csv(private / "generator_key.csv", key, list(key[0]))
    instructions = (
        "# Independent annotation pilot\n\n"
        "All examples are synthetic. Work independently and do not discuss cases or inspect "
        "generator labels, model predictions, source IDs or the analyst key. The coordinator "
        "must assign separate people; file checks cannot prove independence.\n\n"
        "Read LABEL_DEFINITIONS.md unchanged. Label the shown document evidence and claim using "
        "entailment, contradiction or neutral. Use uncertain as an annotation status when you "
        "cannot decide or the written definitions are ambiguous; explain in notes. It is not "
        "a fourth NLI gold label. Do not use neutral to mean personal uncertainty. Do not "
        "guess hidden clean OCR values. Report ambiguity for adjudication.\n\n"
        "The evidence is exactly the model's observed-input serialization. VIZ is the visual "
        "inspection zone, MRZ the machine-readable zone, and ? means unreadable. Field legend: "
        "sur=surname, giv=given names, dob=birth date, doi=issue date, doe=expiry, num=document "
        "number, nat=nationality, pob=birthplace, auth=issuing authority, era=template era.\n\n"
        "Fill human_label. Confidence 1 through 5 is optional. Add notes, especially for "
        "uncertain cases. Keep all case IDs and evidence unchanged; rows may be reordered. "
        "Return only your completed CSV. Declare to the coordinator which scripts/languages "
        "you can read; do not guess cases outside your competence.\n"
    )
    definition_path = resolve(config.label_definitions)
    artifacts = {}
    for suffix in ("A", "B"):
        folder = output / f"annotator_{suffix}"
        folder.mkdir()
        ordered = list(rows)
        random.Random(f"{config.seed}:{suffix}").shuffle(ordered)
        write_csv(folder / "sheet.csv", ordered, VISIBLE_FIELDS + RESPONSE_FIELDS)
        (folder / "README.md").write_text(instructions, encoding="utf-8")
        (folder / "LABEL_DEFINITIONS.md").write_bytes(definition_path.read_bytes())
        archive_path = output / f"annotator_{suffix}.zip"
        with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.iterdir()):
                archive.write(path, path.name)
        artifacts[suffix] = fingerprint(archive_path)
    write_json(private / "manifest.json", {
        "status": "PREPARED_AWAITING_INDEPENDENT_HUMAN_LABELS", "n": expected_n,
        "seed": config.seed, "dataset_version": "synth_v1", "dataset_test": evidence,
        "configuration": fingerprint(config_path),
        "implementation": fingerprint(Path(__file__)),
        "label_definitions": fingerprint(definition_path),
        "expected_visible_rows": fingerprint(private / "expected_visible_rows.json"),
        "generator_key": fingerprint(private / "generator_key.csv"),
        "per_language_label": {f"{language}/{label.value}": sum(
            x.language == language and x.label == label for x in selected
        ) for language in load_languages() for label in Label},
        "distinct_identities": len({x.identity_id for x in selected}),
        "wrong_name_cases": sum(x.phenomenon == "cross_script_name_mismatch" for x in selected),
        "shareable_artifacts": artifacts,
        "blinding": "No generator labels, rationales, source IDs, clean values or model outputs "
                    "in worksheets; key is separate. Cooperative, not adversarial blinding.",
        "limits": f"{expected_n}-case balanced pilot; not completed "
                  "human validation or a population-representative sample",
    })
    print(f"Prepared {expected_n} blinded cases: {output}", flush=True)
    return output


def validate_sheet(path: Path, expected: list[dict]) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != VISIBLE_FIELDS + RESPONSE_FIELDS:
            raise ValueError("Worksheet columns changed")
        rows = list(reader)
    canonical = {r["case_id"]: r for r in expected}
    actual = {r["case_id"]: r for r in rows}
    if len(rows) != len(actual) or set(actual) != set(canonical):
        raise ValueError("Duplicate, missing or unexpected case IDs")
    complete = True
    for case_id, row in actual.items():
        if any(row[field] != canonical[case_id][field] for field in VISIBLE_FIELDS):
            raise ValueError(f"Altered evidence or claim: {case_id}")
        label = row["human_label"].strip().casefold()
        if not label:
            complete = False
        elif label not in ALLOWED:
            raise ValueError(f"Invalid human label: {case_id}")
        if row["confidence_1_to_5"].strip() not in {"", "1", "2", "3", "4", "5"}:
            raise ValueError(f"Invalid confidence: {case_id}")
        if label == "uncertain" and not row["notes"].strip():
            complete = False
        row["human_label"] = label
    return {"complete": complete, "rows": actual}


def check(batch: Path, sheet_a: Path, sheet_b: Path) -> Path:
    batch = resolve(batch)
    manifest = json.loads((batch / "ANALYST_ONLY/manifest.json").read_text(encoding="utf-8"))
    for key in ("expected_visible_rows", "generator_key", "dataset_test"):
        record = manifest[key]
        if file_digest(Path(record["path"])) != record["sha256"]:
            raise ValueError(f"Annotation reference changed: {key}")
    expected = json.loads(
        (batch / "ANALYST_ONLY/expected_visible_rows.json").read_text(encoding="utf-8"),
    )
    a, b = validate_sheet(resolve(sheet_a), expected), validate_sheet(resolve(sheet_b), expected)
    report = {"status": "INCOMPLETE", "n": len(expected),
              "sheet_a_complete": a["complete"], "sheet_b_complete": b["complete"],
              "human_validation_complete": False}
    if a["complete"] and b["complete"]:
        ids = sorted(a["rows"])
        left = [a["rows"][i]["human_label"] for i in ids]
        right = [b["rows"][i]["human_label"] for i in ids]
        definite = [(x, y) for x, y in zip(left, right, strict=True)
                    if x != "uncertain" and y != "uncertain"]
        report.update({
            "status": "COMPLETED_SHEETS_PROVENANCE_NOT_VERIFIED_ADJUDICATION_PENDING",
            "agreement_including_uncertain_status": sum(
                x == y for x, y in zip(left, right, strict=True)
            ) / len(ids),
            "uncertain_a": Counter(left)["uncertain"], "uncertain_b": Counter(right)["uncertain"],
            "both_definite_n": len(definite),
            "agreement_on_definite_only": sum(x == y for x, y in definite) / len(definite)
                                          if definite else None,
            "cohen_kappa_on_definite_only": float(cohen_kappa_score(
                [x for x, _ in definite], [y for _, y in definite],
            )) if len({label for pair in definite for label in pair}) > 1 else None,
            "limits": "File checks do not verify independent humans or blinding. Uncertain cases "
                      "are explicitly counted; conditional agreement is not full-sample agreement.",
        })
    output = batch / "checks" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "report.json", report)
    return output / "report.json"
