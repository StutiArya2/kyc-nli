"""Dataset serialisation: JSONL instances plus a machine-written manifest.

The manifest is not documentation. It is the record that lets anyone regenerate
the exact dataset from a config and a seed, and it is what the benchmark card in
the paper is built from. Never hand-edit it.
"""

from __future__ import annotations

import hashlib
import json
import platform
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from kyc_nli import __version__
from kyc_nli.schema import Instance


def save_instances(instances: list[Instance], path: Path) -> Path:
    """Write instances as one JSON object per line, sorted by id for stability."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for inst in sorted(instances, key=lambda i: i.id):
            fh.write(inst.model_dump_json() + "\n")
    return path


def load_instances(path: Path) -> list[Instance]:
    with path.open("r", encoding="utf-8") as fh:
        return [Instance.model_validate_json(line) for line in fh if line.strip()]


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(
    instances: list[Instance],
    dataset_path: Path,
    manifest_path: Path,
    generator_config: dict,
) -> Path:
    """Record exactly what was generated and under what conditions."""
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kyc_nli_version": __version__,
        "python": platform.python_version(),
        "dataset_file": dataset_path.name,
        "sha256": file_digest(dataset_path),
        "n_instances": len(instances),
        "generator_config": generator_config,
        "counts": {
            "by_label": dict(Counter(i.label.value for i in instances)),
            "by_language": dict(Counter(i.language for i in instances)),
            "by_phenomenon": dict(Counter(i.phenomenon for i in instances)),
        },
        "contrast_groups": len({i.contrast_group_id for i in instances if i.contrast_group_id}),
        "contains_real_pii": any(i.provenance.contains_real_pii for i in instances),
        "note": (
            "Machine-generated. Do not hand-edit. Regenerate with "
            "`kyc-nli generate` using the config recorded above."
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def split_by_identity(
    instances: list[Instance], dev_fraction: float = 0.15, test_fraction: float = 0.15
) -> dict[str, list[Instance]]:
    """Split by contrast group, stratified by language.

    Two constraints, both of which have bitten this project already:

    1. NO GROUP MAY STRADDLE A SPLIT. Members of a contrast group share a
       premise, so a group split across train/test lets a model memorise the
       document rather than reason about it.
    2. EVERY SPLIT MUST CONTAIN EVERY LANGUAGE. Group ids are prefixed with the
       language code, so an unstratified sort put 100% of the test set in one
       language and made the per-language breakdown meaningless. Stratify.
    """
    groups_by_language: dict[str, list[str]] = defaultdict(list)
    seen: set[str] = set()
    for inst in instances:
        key = inst.contrast_group_id or inst.id
        if key not in seen:
            seen.add(key)
            groups_by_language[inst.language].append(key)

    test_groups: set[str] = set()
    dev_groups: set[str] = set()
    for groups in groups_by_language.values():
        # Sort by a stable digest, not lexically: lexical order correlates with
        # the identity index, which correlates with generation order.
        ordered = sorted(groups, key=lambda g: hashlib.sha256(g.encode()).hexdigest())
        n = len(ordered)
        n_test = int(n * test_fraction)
        n_dev = int(n * dev_fraction)
        test_groups.update(ordered[:n_test])
        dev_groups.update(ordered[n_test : n_test + n_dev])

    out: dict[str, list[Instance]] = {"train": [], "dev": [], "test": []}
    for inst in instances:
        key = inst.contrast_group_id or inst.id
        if key in test_groups:
            out["test"].append(inst)
        elif key in dev_groups:
            out["dev"].append(inst)
        else:
            out["train"].append(inst)
    return out
