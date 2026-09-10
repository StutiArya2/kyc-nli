"""Dataset-integrity tests.

These guard properties the benchmark's credibility rests on. If one fails, any
number produced from the dataset is unusable, so they are not optional.
"""

from __future__ import annotations

from collections import Counter

import pytest

from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.data.io import split_by_identity
from kyc_nli.languages import load_languages
from kyc_nli.schema import Label


@pytest.fixture(scope="module")
def instances():
    config = GeneratorConfig(
        languages=tuple(load_languages()), identities_per_language=12, seed=7
    )
    return InstanceGenerator(config).generate()


def test_generation_is_deterministic() -> None:
    """Same config plus same seed must give byte-identical output."""
    config = GeneratorConfig(identities_per_language=5, seed=99)
    a = InstanceGenerator(config).generate()
    b = InstanceGenerator(config).generate()
    assert [i.model_dump_json() for i in sorted(a, key=lambda x: x.id)] == [
        i.model_dump_json() for i in sorted(b, key=lambda x: x.id)
    ]


def test_every_language_is_represented(instances) -> None:
    assert set(i.language for i in instances) == set(load_languages())


def test_all_three_labels_present_per_language(instances) -> None:
    for language in load_languages():
        labels = {i.label for i in instances if i.language == language}
        assert labels == set(Label), f"{language} is missing {set(Label) - labels}"


def test_ids_are_unique(instances) -> None:
    duplicates = [k for k, v in Counter(i.id for i in instances).items() if v > 1]
    assert not duplicates


def test_no_instance_claims_real_pii(instances) -> None:
    """The repo must never generate anything traceable to a real person."""
    assert not any(i.provenance.contains_real_pii for i in instances)


def test_every_instance_has_a_rationale(instances) -> None:
    """A gold label with no stated reason cannot be audited by an annotator."""
    assert all(i.rationale.strip() for i in instances)


def test_neutral_instances_are_structurally_neutral(instances) -> None:
    """NEUTRAL must mean the evidence is absent or unreadable, never merely weak.

    This is the project's central definitional commitment. If a NEUTRAL instance
    has a clean, legible observation of the hypothesised field, the label is a
    confidence judgement in disguise and the reviewer objection lands.
    """
    for inst in instances:
        if inst.label is not Label.NEUTRAL:
            continue
        readable = [
            o
            for o in inst.observations(inst.hypothesis.field)
            if o.confidence >= 0.35 and "?" not in o.value
        ]
        assert not readable, (
            f"{inst.id} is labelled NEUTRAL but carries a legible observation "
            f"of {inst.hypothesis.field.value}: {[o.value for o in readable]}"
        )


def test_splits_do_not_share_identities(instances) -> None:
    """The test that should have existed from the start.

    One fabricated identity produces THREE contrast groups (-name, -time,
    -evidence) that share a surname, dates and document number. Splitting on
    contrast_group_id alone put 359 of 383 test identities into training too, so
    a model could memorise a document in one group and recall it in another. The
    cross-encoder scored 0.989 macro-F1 under that split; the number measured
    memorisation as much as inference.

    Identity is the coarsest unit and therefore the one the split must respect.
    """
    splits = split_by_identity(instances)
    ids = {
        name: {i.identity_id for i in subset if i.identity_id}
        for name, subset in splits.items()
    }
    assert ids["train"], "no identity_id on any instance -- the field is not being set"
    assert not ids["train"] & ids["test"], (
        f"{len(ids['train'] & ids['test'])} identities appear in both train and test"
    )
    assert not ids["train"] & ids["dev"]
    assert not ids["dev"] & ids["test"]


def test_every_instance_carries_an_identity_id(instances) -> None:
    """Without it the splitter silently falls back to the group and leaks again."""
    missing = [i.id for i in instances if not i.identity_id]
    assert not missing, f"{len(missing)} instances have no identity_id, e.g. {missing[:3]}"


def test_one_identity_spans_several_contrast_groups(instances) -> None:
    """The precondition that makes the identity-level split necessary.

    If this ever stops being true, the identity and group splits coincide and
    the distinction stops mattering -- but silently, which is why it is asserted.
    """
    from collections import defaultdict

    groups_per_identity = defaultdict(set)
    for inst in instances:
        if inst.identity_id and inst.contrast_group_id:
            groups_per_identity[inst.identity_id].add(inst.contrast_group_id)
    assert max(len(v) for v in groups_per_identity.values()) > 1


def test_splits_do_not_share_contrast_groups(instances) -> None:
    """A group straddling train/test would leak the premise."""
    splits = split_by_identity(instances)
    groups = {
        name: {i.contrast_group_id for i in subset if i.contrast_group_id}
        for name, subset in splits.items()
    }
    assert not groups["train"] & groups["test"]
    assert not groups["train"] & groups["dev"]
    assert not groups["dev"] & groups["test"]


def test_splits_are_language_stratified(instances) -> None:
    """Every split must contain every language, or per-language results lie."""
    splits = split_by_identity(instances)
    for name, subset in splits.items():
        assert set(i.language for i in subset) == set(load_languages()), (
            f"split {name!r} is missing languages"
        )
