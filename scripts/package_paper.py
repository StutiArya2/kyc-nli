"""Package only explicitly referenced anonymous paper sources and aggregate evidence."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile

import yaml

from kyc_nli.languages import repo_root
from kyc_nli.paper_v1 import load_records


def main() -> None:
    root = repo_root()
    paper = root / "paper"
    config, records = load_records(root / "configs/experiments/paper_v1.yaml")
    tex = (paper / "main.tex").read_text(encoding="utf-8")
    names = {"main.tex", "numbers.tex", "references.bib", "acl.sty", "acl_natbib.bst"}
    names.update(f"{name}.tex" for name in re.findall(r"\\input\{([^}]+)\}", tex))
    names.update(f"{name}.pdf" for name in re.findall(
        r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex))
    content = {name: (paper / name).read_bytes() for name in sorted(names)}
    content["README.txt"] = (
        b"Anonymous ACL review source package\n\n"
        b"Compile main.tex with pdfLaTeX/BibTeX or Tectonic. Official ACL style files "
        b"are included without modification.\n"
        b"Scope: frozen synthetic v1, moderate noise only. Two recovered XLM-R artifacts "
        b"are evaluated separately. No claim of public data release or deployment safety.\n"
        b"Aggregate evidence and full artifact hashes are in artifact_inventory.json.\n"
        b"Code and synthetic-data release is planned subject to licensing review. "
        b"Private attestations, original identities, external corpora and weights "
        b"are excluded from this review package.\n"
    )
    start = records["evaluation_start"]
    inventory = {
        "scope": "synthetic_v1_moderate_only", "seed": config["seed"],
        "result_artifact_sha256": {k: v["sha256"] for k, v in config["inputs"].items()},
        "dataset_sha256": {k: v["sha256"] for k, v in records["dataset"]["files"].items()},
        "checkpoints": {k: {"weight_sha256": v["sha256"]}
                        for k, v in start["configuration"]["checkpoints"].items()},
        "tokenizer_sha256": "17463f5db207638d220ae81d1b382b4d5b29efc36f6993f0f7468bab0803c814",
        "inference": {k: start["configuration"][k]
                      for k in ("max_length", "batch_size", "threads", "seed", "bootstrap")},
        "classification": records["evaluation"]["systems"],
        "paired_classification": records["evaluation"]["paired_vs_rule"],
        "selective_5_percent": {
            k: row["budgets"]["0.05"] for k, row in records["selective"]["systems"].items()},
        "paired_review": records["selective"]["paired_review_differences"],
        "pilot": {k: records["pilot"][k] for k in (
            "n", "candidate_label_n", "unresolved_case_ids", "human_generator_disagreement_ids",
            "initial_AB_agreement", "initial_AB_per_language", "followup_agreement",
            "provenance", "limitations")},
    }
    content["artifact_inventory.json"] = json.dumps(inventory, indent=2).encode()
    # Detect private names from the actual records without embedding names in source/tests.
    pilot_config = yaml.safe_load((root / "configs/experiments/v1_pilot_report.yaml").read_text())
    private_names = []
    for key in ("attestation_1", "attestation_2", "annotator_declarations"):
        private_path = root / pilot_config[key]
        with private_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                private_names.extend(value for name, value in row.items()
                                     if name in {"reviewer_name", "annotator_name"})
    forbidden = ["C:\\Users\\", "D:\\Downloads\\", "D:\\kyc-nli\\", *private_names]
    for name, raw in content.items():
        if name.endswith(".pdf"):
            continue
        text = raw.decode("utf-8")
        if any(value.casefold() in text.casefold() for value in forbidden):
            raise ValueError(f"Private name or local path in submission file: {name}")
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in content.items()}
    content["SHA256SUMS.json"] = json.dumps(hashes, indent=2).encode()
    output = root / "output/paper"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "kyc_nli_acl_review_sources.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in content.items():
            archive.writestr(name, raw)
    path.write_bytes(buffer.getvalue())
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(content):
            raise ValueError("Archive verification failed")
    print(f"Anonymous source package: {path}")


if __name__ == "__main__":
    main()
