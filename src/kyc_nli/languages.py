"""Language registry, loaded from configs/languages.yaml.

Nothing in the codebase should hardcode a language code. Iterate over
``load_languages()`` instead, so that adding a sixth language is a config edit.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator

from kyc_nli.schema import Script


def repo_root() -> Path:
    """Repo root, resolved from this file's location."""
    return Path(__file__).resolve().parents[2]


class Romanisation(BaseModel):
    """How much authority constrains the Latin rendering of a name.

    Three-valued, not boolean. Urdu is the case that forces this: the ICAO
    Doc 9303 Arabic table fixes the consonants but the script writes no short
    vowels, so the standard determines part of the answer and a lexicon supplies
    the rest. Collapsing that to True would overstate what the table gives you;
    collapsing it to False would discard a real constraint the baseline is
    entitled to use.
    """

    standard: str
    #: "full"    an authority fixes exactly one correct Latin rendering
    #: "partial" the standard constrains the rendering but does not determine it
    #: "none"    romanisation is genuinely one-to-many; a lookup table cannot
    #:           be sufficient even in principle
    normative: Literal["full", "partial", "none"]

    @field_validator("normative", mode="before")
    @classmethod
    def _coerce_legacy_bool(cls, v: object) -> object:
        """Accept the old boolean form so pre-0005 configs still load."""
        if isinstance(v, bool):
            return "full" if v else "none"
        return v

    @property
    def is_normative(self) -> bool:
        """True when a lookup table alone could in principle be correct."""
        return self.normative == "full"


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
