"""Language registry, loaded from configs/languages.yaml.

Nothing in the codebase should hardcode a language code. Iterate over
``load_languages()`` instead, so that adding a sixth language is a config edit.
"""

from __future__ import annotations

import functools
from pathlib import Path

import yaml
from pydantic import BaseModel

from kyc_nli.schema import Script


def repo_root() -> Path:
    """Repo root, resolved from this file's location."""
    return Path(__file__).resolve().parents[2]


class Romanisation(BaseModel):
    standard: str
    #: True when an authority (e.g. ICAO Doc 9303) fixes exactly one correct
    #: Latin rendering. False means romanisation is genuinely one-to-many, which
    #: is where a lookup table stops being sufficient.
    normative: bool


class LanguageSpec(BaseModel):
    code: str
    name: str
    script: Script
    romanisation: Romanisation
    failure_mode: str
    sources: list[dict] = []


@functools.lru_cache(maxsize=1)
def load_languages(path: Path | None = None) -> dict[str, LanguageSpec]:
    """Load the language registry, keyed by language code."""
    path = path or repo_root() / "configs" / "languages.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    specs = [LanguageSpec(**block) for block in raw["languages"]]
    return {s.code: s for s in specs}


def language_codes() -> list[str]:
    return list(load_languages())


def script_of(code: str) -> Script:
    return load_languages()[code].script
