"""Edge cases for dataset serialisation and, above all, for the splitter.

The splitter is the single highest-risk function in this repository. It has
already produced one headline result that had to be thrown away: splitting on
`contrast_group_id` put 94% of test identities into training and the model
scored 0.989 macro-F1 by memorisation. `tests/test_generate.py` asserts the
no-overlap property on real generated data; this file attacks the function
directly with the inputs a generator would never produce.
"""

from __future__ import annotations

import json

import pytest

from kyc_nli.data.io import (
    load_instances,
    save_instances,
    split_by_identity,
    write_manifest,
)
from kyc_nli.schema import Field, Hypothesis, Instance, Label, Provenance, Script


def mk(
    key: str,
    *,
    language: str = "en",
    identity: str | None = None,
    group: str | None = None,
    label: Label = Label.ENTAILMENT,
    value: str = "X",
) -> Instance:
    return Instance(
        id=key,
        language=language,
        premise=[],
        hypothesis=Hypothesis(
            field=Field.SURNAME, value=value, script=Script.LATIN, language=language, text="t"
        ),
        label=label,
        identity_id=identity,
        contrast_group_id=group,
        provenance=Provenance(generator="test", seed=1),
    )


def population(n: int, languages: tuple[str, ...] = ("en",)) -> list[Instance]:
    """n identities per language, three instances each, as the generator emits."""
    out: list[Instance] = []
    for lang in languages:
        for i in range(n):
            ident = f"{lang}-{i:04d}"
            for suffix in ("name", "time", "evidence"):
                out.append(
                    mk(
                        f"{ident}-{suffix}-0",
                        language=lang,
                        identity=ident,
                        group=f"{ident}-{suffix}",
                    )
                )
    return out


# --------------------------------------------------------------------------
# save / load
# --------------------------------------------------------------------------


def test_instances_round_trip_through_disk_unchanged(tmp_path) -> None:
    original = [mk("b", value="চট্টোপাধ্যায়"), mk("a", value="سرور")]
    path = save_instances(original, tmp_path / "d.jsonl")
    again = load_instances(path)
    assert {i.id for i in again} == {"a", "b"}
    assert {i.hypothesis.value for i in again} == {"চট্টোপাধ্যায়", "سرور"}


def test_the_file_is_sorted_by_id_so_the_digest_is_stable(tmp_path) -> None:
    """The manifest records a SHA-256 of this file. If dict ordering could change
    the bytes, the digest would stop being evidence that two runs agree."""
    a = save_instances([mk("b"), mk("a")], tmp_path / "a.jsonl").read_bytes()
    b = save_instances([mk("a"), mk("b")], tmp_path / "b.jsonl").read_bytes()
    assert a == b


def test_an_empty_dataset_writes_an_empty_file_rather_than_failing(tmp_path) -> None:
    path = save_instances([], tmp_path / "empty.jsonl")
    assert path.read_text(encoding="utf-8") == ""
    assert load_instances(path) == []


def test_blank_lines_in_a_hand_touched_file_are_skipped(tmp_path) -> None:
    """Trailing newlines and editor artefacts must not become a parse error on a
    dataset that is otherwise fine."""
    path = save_instances([mk("a")], tmp_path / "d.jsonl")
    path.write_text(path.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    assert len(load_instances(path)) == 1


def test_the_file_uses_unix_newlines_on_every_platform(tmp_path) -> None:
    """This repository is developed on Windows and the digest must not depend on
    that. A CRLF file has a different SHA-256 for identical data."""
    path = save_instances([mk("a")], tmp_path / "d.jsonl")
    assert b"\r\n" not in path.read_bytes()


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------


def test_the_manifest_records_what_a_regeneration_would_need(tmp_path) -> None:
    instances = population(4)
    data = save_instances(instances, tmp_path / "d.jsonl")
    manifest = write_manifest(instances, data, tmp_path / "d.manifest.json", {"seed": 7})
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["n_instances"] == len(instances)
    assert payload["generator_config"] == {"seed": 7}
    assert payload["sha256"] and len(payload["sha256"]) == 64
    assert payload["contrast_groups"] == 12
    assert payload["counts"]["by_label"] == {"entailment": 12}


def test_the_manifest_flags_real_pii_if_a_single_instance_carries_it(tmp_path) -> None:
    """The flag is the whole ethics claim. Any-not-all is the only safe reading."""
    clean = mk("a")
    tainted = mk("b")
    tainted = tainted.model_copy(
        update={"provenance": Provenance(generator="t", contains_real_pii=True)}
    )
    data = save_instances([clean, tainted], tmp_path / "d.jsonl")
    manifest = write_manifest([clean, tainted], data, tmp_path / "m.json", {})
    assert json.loads(manifest.read_text(encoding="utf-8"))["contains_real_pii"] is True


def test_non_latin_text_survives_into_the_manifest_readably(tmp_path) -> None:
    """ensure_ascii would render every Indic language as \\uXXXX escapes and make
    the one human-facing artefact of a run unreadable."""
    instances = [mk("a", language="hi")]
    data = save_instances(instances, tmp_path / "d.jsonl")
    manifest = write_manifest(instances, data, tmp_path / "m.json", {"note": "देवनागरी"})
    assert "देवनागरी" in manifest.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# split_by_identity: the property that must never break
# --------------------------------------------------------------------------


def test_no_identity_appears_in_more_than_one_split() -> None:
    """The bug that invalidated a 0.989 result, asserted directly."""
    splits = split_by_identity(population(40))
    seen = {name: {i.identity_id for i in part} for name, part in splits.items()}
    assert not seen["train"] & seen["test"]
    assert not seen["train"] & seen["dev"]
    assert not seen["dev"] & seen["test"]


def test_no_contrast_group_straddles_a_split() -> None:
    """Implied by the identity property, asserted separately because the contrast
    metric is meaningless the moment it stops holding."""
    splits = split_by_identity(population(40))
    groups = {name: {i.contrast_group_id for i in part} for name, part in splits.items()}
    assert not groups["train"] & groups["test"]
    assert not groups["train"] & groups["dev"]


def test_every_language_reaches_every_split() -> None:
    """An unstratified sort once put 100% of the test set in one language, which
    silently deleted the per-language breakdown the cross-script claim rests on."""
    languages = ("en", "hi", "ta", "bn", "ur")
    splits = split_by_identity(population(20, languages))
    for part in splits.values():
        assert {i.language for i in part} == set(languages)


def test_a_language_with_only_three_identities_still_reaches_every_split() -> None:
    """int(3 * 0.15) is 0. Dev and test used to come back empty here without a
    word, so a smoke run with --identities 5 scored a model on nothing."""
    splits = split_by_identity(population(3))
    assert all(len(part) > 0 for part in splits.values())


def test_the_documented_split_proportions_are_unchanged_at_realistic_size() -> None:
    """The published results were measured at 700/150/150. The small-population
    fix must not have moved the split the numbers in the papers came from."""
    splits = split_by_identity(population(1000))
    identities = {name: len({i.identity_id for i in part}) for name, part in splits.items()}
    assert identities == {"train": 700, "dev": 150, "test": 150}


def test_the_split_is_deterministic_across_calls_and_input_order() -> None:
    """Two runs of `kyc-nli generate` must produce the same test set, or no two
    numbers in the project are comparable."""
    data = population(30)
    a = split_by_identity(data)
    b = split_by_identity(list(reversed(data)))
    assert {i.id for i in a["test"]} == {i.id for i in b["test"]}


def test_assignment_does_not_track_the_order_identities_were_generated() -> None:
    """Identity ids are sequential, so a lexical sort would put the whole test
    set at one end of generation -- correlated with anything that drifts."""
    splits = split_by_identity(population(100))
    indices = sorted(int(k.split("-")[1]) for k in {i.identity_id for i in splits["test"]})
    assert indices[0] < 20 and indices[-1] > 80


def test_an_instance_with_no_identity_falls_back_to_its_contrast_group() -> None:
    """Hand-built probe instances carry no identity. Falling back to the group
    keeps the minimal pair together, which is the next-best guarantee."""
    data = [mk(f"g{g}-{m}", group=f"g{g}") for g in range(20) for m in range(2)]
    splits = split_by_identity(data)
    groups = {name: {i.contrast_group_id for i in part} for name, part in splits.items()}
    assert not groups["train"] & groups["test"]


def test_an_instance_with_neither_key_falls_back_to_its_own_id() -> None:
    """Last resort. Every instance must land in exactly one split regardless."""
    data = [mk(f"lone-{i}") for i in range(20)]
    splits = split_by_identity(data)
    assert sum(len(part) for part in splits.values()) == 20


def test_splitting_nothing_returns_three_empty_splits() -> None:
    assert split_by_identity([]) == {"train": [], "dev": [], "test": []}


def test_every_instance_lands_in_exactly_one_split() -> None:
    data = population(25, ("en", "hi"))
    splits = split_by_identity(data)
    ids = [i.id for part in splits.values() for i in part]
    assert sorted(ids) == sorted(i.id for i in data)
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "dev,test",
    [(0.6, 0.6), (1.0, 0.0), (-0.1, 0.2), (0.5, 0.5), (0.2, 1.5)],
)
def test_fractions_that_would_starve_the_training_set_are_rejected(
    dev: float, test: float
) -> None:
    """Silently returning an empty train split is how a config typo becomes a
    day of debugging a model that had nothing to learn from."""
    with pytest.raises(ValueError):
        split_by_identity(population(10), dev_fraction=dev, test_fraction=test)


def test_zero_fractions_put_everything_in_train() -> None:
    """The legitimate way to ask for no held-out data, e.g. a final refit."""
    splits = split_by_identity(population(10), dev_fraction=0.0, test_fraction=0.0)
    assert len(splits["dev"]) == 0 and len(splits["test"]) == 0
    assert len(splits["train"]) == 30
