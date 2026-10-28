"""Regression guards for invalid surname negatives and immutable v1 freezing."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kyc_nli.data.generate import (
    GeneratorConfig,
    InstanceGenerator,
    accepted_surnames,
    normalise_surname,
)
from kyc_nli.data.name_pools import pool_for
from kyc_nli.languages import load_languages
from kyc_nli.schema import Field, Zone
from kyc_nli.v1 import freeze, validate_dataset


@pytest.mark.parametrize("language", list(load_languages()))
def test_exact_collision_is_repaired_without_consuming_rng(language):
    generator = InstanceGenerator(GeneratorConfig(seed=19))
    holder = generator.make_identity(language)
    state = generator.rng.getstate()
    claimed = generator._negative_surname(holder, holder, "test-identity")
    accepted = accepted_surnames(holder.surname_native, holder.surname_latin,
                                 holder.script, holder.language)
    assert normalise_surname(claimed) not in accepted
    assert generator.rng.getstate() == state
    assert claimed == generator._negative_surname(holder, holder, "test-identity")


def test_variant_collision_is_repaired_after_unicode_and_separator_normalisation(monkeypatch):
    generator = InstanceGenerator(GeneratorConfig(seed=5))
    language = next(iter(load_languages()))
    holder = generator.make_identity(language)
    pool = pool_for(language)
    other_latin = next(latin for _, latin in pool.surnames if latin != holder.surname_latin)
    other = replace(holder, surname_latin=other_latin)

    class Engine:
        def variants(self, native):
            wide = "".join(chr(ord(c) + 0xFEE0) if c.isascii() and c.isalpha()
                           else c for c in other_latin.lower())
            return {" ".join(wide)}

    monkeypatch.setattr("kyc_nli.data.generate.get_transliterator", lambda *args: Engine())
    assert generator._negative_surname(holder, other, "alias") != other_latin


def test_exhausted_pool_fails_instead_of_silently_emitting_a_bad_label(monkeypatch):
    generator = InstanceGenerator(GeneratorConfig(seed=5))
    language = next(iter(load_languages()))
    holder = generator.make_identity(language)
    pool = replace(pool_for(language), surnames=((holder.surname_native, holder.surname_latin),))
    monkeypatch.setattr("kyc_nli.data.generate.pool_for", lambda _: pool)
    with pytest.raises(ValueError, match="No distinct surname"):
        generator._negative_surname(holder, holder, "exhausted")


def test_attested_pool_alias_of_same_native_surname_is_excluded(monkeypatch):
    generator = InstanceGenerator(GeneratorConfig(seed=9))
    language = next(iter(load_languages()))
    holder = generator.make_identity(language)
    pool = pool_for(language)
    alias = next(latin for _, latin in pool.surnames if latin != holder.surname_latin)
    pool = replace(pool, surnames=pool.surnames + ((holder.surname_native, alias),))
    monkeypatch.setattr("kyc_nli.data.generate.pool_for", lambda _: pool)
    other = replace(holder, surname_latin=alias)
    assert generator._negative_surname(holder, other, "pool-alias") != alias


def test_repair_changes_only_colliding_hypotheses_and_provenance():
    config = GeneratorConfig(identities_per_language=20, seed=20260906)
    legacy = InstanceGenerator(replace(config, dataset_version="synth_v0")).generate()
    old = {x.id: x for x in legacy}
    new = InstanceGenerator(config).generate()
    changed = []
    for item in new:
        previous = old[item.id]
        assert item.premise == previous.premise
        assert item.identity_id == previous.identity_id
        if item.hypothesis != previous.hypothesis:
            changed.append(item.id)
            assert item.phenomenon == "cross_script_name_mismatch"
            # Use structured surname observations rather than generator rationale.
            viz = previous.observation(Field.SURNAME, Zone.VIZ)
            mrz = previous.observation(Field.SURNAME, Zone.MRZ)
            accepted = accepted_surnames(
                viz.clean_value, mrz.clean_value, viz.script, item.language,
            )
            assert normalise_surname(previous.hypothesis.value) in accepted
            assert normalise_surname(item.hypothesis.value) not in accepted
    assert changed, "Regression fixture must exercise the original collision bug"
    from kyc_nli.data.io import split_by_identity

    validate_dataset(new, split_by_identity(new))


def test_frozen_paths_cannot_be_overwritten(tmp_path):
    import yaml

    target = tmp_path / "frozen.jsonl"
    target.write_text("preserve me", encoding="utf-8")
    config = tmp_path / "freeze.yaml"
    config.write_text(yaml.safe_dump({
        "dataset_version": "synth_v1", "identities_per_language": 3,
        "noise_preset": "moderate", "seed": 7, "alt_romanisation_rate": 0.4,
        "reference_v0": str(tmp_path / "missing.jsonl"), "output": str(target),
    }), encoding="utf-8")
    with pytest.raises(FileExistsError):
        freeze(config)
    assert target.read_text() == "preserve me"


def test_freeze_records_hashes_and_preserves_the_reference(tmp_path):
    import json

    import yaml

    from kyc_nli.data.io import file_digest, save_instances

    reference = tmp_path / "v0.jsonl"
    legacy = InstanceGenerator(GeneratorConfig(
        identities_per_language=3, seed=7, dataset_version="synth_v0",
    )).generate()
    save_instances(legacy, reference)
    original_hash = file_digest(reference)
    config = tmp_path / "freeze.yaml"
    config.write_text(yaml.safe_dump({
        "dataset_version": "synth_v1", "identities_per_language": 3,
        "noise_preset": "moderate", "seed": 7, "alt_romanisation_rate": 0.4,
        "reference_v0": str(reference), "output": str(tmp_path / "v1.jsonl"),
    }), encoding="utf-8")
    manifest = json.loads(freeze(config).read_text(encoding="utf-8"))
    assert manifest["repeated_generation_identical"]
    assert manifest["v0_premises_and_split_ids_preserved"]
    assert manifest["integrity"]["clean_name_alias_collisions"] == 0
    for evidence in manifest["files"].values():
        from pathlib import Path

        assert file_digest(Path(evidence["path"])) == evidence["sha256"]
    assert file_digest(reference) == original_hash
    with pytest.raises(FileExistsError):
        freeze(config)
