"""Loaders for external corpora. Everything here writes to data/external/, which
is gitignored — never commit corpus files.

Currently: the Dakshina dataset (Google Research, CC BY-SA 4.0), which covers all
four non-English languages in the active set with **human-elicited**
romanisations. That last word is the point. Dakshina's romanisations were written
by native speakers asked to type a word in Latin script, so a single native word
carries several attested spellings produced by different people — which is
exactly the one-to-many relation this project claims a rule table cannot capture.

That makes Dakshina useful for two distinct jobs, and it is worth being precise
about which is which:

1. MEASURING THE TRANSLITERATION ENGINES. How much real human romanisation
   variation does our variant set actually cover? Until now that number came from
   40 hand-written pairs per language, which we chose ourselves — a number that
   flatters us by construction. Dakshina replaces it with thousands of
   romanisations we did not pick.

2. SUPPLYING NAMES. Weaker fit. Dakshina lexicons are general Wikipedia
   vocabulary, not a name list, so most entries are ordinary words. Proper nouns
   are present but not labelled, and Dakshina is lowercase throughout, so there
   is no capitalisation signal to filter on. Treat name extraction here as
   best-effort and do not claim these are person names in the paper.

Job 1 is the one that actually strengthens the project. See docs/plan.md M2.
"""

from __future__ import annotations

import tarfile
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from kyc_nli.languages import repo_root

DAKSHINA_URL = "https://storage.googleapis.com/gresearch/dakshina/dakshina_dataset_v1.0.tar"
DAKSHINA_TAR = "dakshina_dataset_v1.0.tar"
DAKSHINA_DIR = "dakshina_dataset_v1.0"

#: Dakshina language codes for the active set. English is not in Dakshina and
#: does not need to be: it is the Latin-script control.
DAKSHINA_LANGUAGES: tuple[str, ...] = ("hi", "ta", "bn", "ur")


def external_dir() -> Path:
    return repo_root() / "data" / "external"


@dataclass(frozen=True)
class RomanisationEntry:
    """One native word and every attested Latin spelling of it."""

    native: str
    romanisations: tuple[str, ...]
    #: Attestation counts, parallel to ``romanisations`` where the source gives
    #: them. A spelling attested by many annotators is stronger evidence than one
    #: attested by a single annotator, and error analysis needs the distinction.
    counts: tuple[int, ...] = ()

    @property
    def primary(self) -> str:
        """The most-attested spelling, or the first if counts are unavailable."""
        if self.counts and len(self.counts) == len(self.romanisations):
            pairs = zip(self.romanisations, self.counts, strict=True)
            return max(pairs, key=lambda t: t[1])[0]
        return self.romanisations[0]


def is_available() -> bool:
    return (external_dir() / DAKSHINA_DIR).is_dir()


def download(force: bool = False, full: bool = False) -> Path:
    """Fetch Dakshina and extract what we use. Download is ~2 GB.

    By default only the transliteration lexicons are unpacked — 38 small files.
    The other 1.9 GB is Wikipedia text and romanized sentence data that nothing
    in this project reads, and unpacking it would cost disk for no benefit. Pass
    ``full=True`` if a later milestone needs the sentence corpora.

    Not called automatically by anything. A test run or a `kyc-nli generate`
    must never silently pull 2 GB off the network.
    """
    target = external_dir()
    target.mkdir(parents=True, exist_ok=True)
    extracted = target / DAKSHINA_DIR
    if extracted.is_dir() and not force:
        return extracted

    tar_path = target / DAKSHINA_TAR
    if not tar_path.exists() or force:
        urllib.request.urlretrieve(DAKSHINA_URL, tar_path)  # noqa: S310 - fixed https URL

    with tarfile.open(tar_path) as tf:
        members = (
            tf.getmembers()
            if full
            else [m for m in tf.getmembers() if "/lexicons/" in m.name]
        )
        tf.extractall(target, members=members, filter="data")
    return extracted


def lexicon_paths(language: str, split: str = "all") -> list[Path]:
    """The transliteration-lexicon files for ``language``.

    Matched by pattern rather than by exact filename: Dakshina's per-language
    layout has varied between releases, and a hardcoded name would fail as a
    silent empty result rather than an error.

    The ``translit.sampled`` prefix is required. The lexicon directories also
    contain stray working files (``tmp.rom.txt`` in ml/, for instance) whose
    format differs; globbing every .tsv and .txt would silently mix them in.
    """
    base = external_dir() / DAKSHINA_DIR / language / "lexicons"
    if not base.is_dir():
        return []
    pattern = (
        f"{language}.translit.sampled.*.tsv"
        if split == "all"
        else f"{language}.translit.sampled.{split}.tsv"
    )
    return sorted(base.glob(pattern))


def load_romanisations(
    language: str,
    min_length: int = 3,
    max_entries: int | None = None,
    split: str = "all",
) -> list[RomanisationEntry]:
    """Native → attested Latin spellings, merged across all lexicon splits.

    Dakshina's lexicon rows are tab-separated with the native word and one
    romanisation per row; the same native word recurs once per annotator, which
    is how the one-to-many relation is represented. We merge those rows so each
    native word carries the full set of spellings people actually wrote.
    """
    merged: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for path in lexicon_paths(language, split=split):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 2:
                    continue
                native, roman = parts[0].strip(), parts[1].strip()
                if not native or not roman:
                    continue
                count = 1
                if len(parts) > 2 and parts[2].strip().isdigit():
                    count = int(parts[2].strip())
                merged[native][roman.upper()] += count

    entries: list[RomanisationEntry] = []
    for native, spellings in merged.items():
        if len(native) < min_length:
            continue
        items = sorted(spellings.items(), key=lambda kv: (-kv[1], kv[0]))
        entries.append(
            RomanisationEntry(
                native=native,
                romanisations=tuple(r for r, _ in items),
                counts=tuple(c for _, c in items),
            )
        )

    entries.sort(key=lambda e: e.native)
    if max_entries is not None:
        entries = entries[:max_entries]
    return entries


def build_lexicon(language: str, split: str = "train") -> dict[str, set[str]]:
    """Attested native -> Latin spellings, for attaching to a transliterator.

    Defaults to the TRAIN split. Attaching a lexicon built from the split an
    engine is then scored on measures memorisation, not transliteration.
    """
    return {
        e.native: set(e.romanisations)
        for e in load_romanisations(language, split=split)
    }


def corpus_summary() -> dict[str, dict[str, int]]:
    """Per-language counts, for the dataset card and for sanity-checking a download."""
    out: dict[str, dict[str, int]] = {}
    for language in DAKSHINA_LANGUAGES:
        entries = load_romanisations(language)
        if not entries:
            out[language] = {"entries": 0, "spellings": 0, "files": len(lexicon_paths(language))}
            continue
        spellings = sum(len(e.romanisations) for e in entries)
        multi = sum(1 for e in entries if len(e.romanisations) > 1)
        out[language] = {
            "entries": len(entries),
            "spellings": spellings,
            "multi_spelling_entries": multi,
            "files": len(lexicon_paths(language)),
        }
    return out
