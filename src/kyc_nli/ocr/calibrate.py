"""Measure what a real OCR engine actually does to each script.

This is milestone M1, and it exists because of a promise made in
docs/decisions/0004-ocr-noise-is-simulated.md: the confusion sets in
``kyc_nli.ocr.noise`` were hand-built from documented failure modes, and no
noise-conditioned number may appear in the paper until they are replaced with
measured ones.

WHY NOT MIDV-2020, AS THE PLAN ORIGINALLY SAID
MIDV-2020 covers ten document types from Albania, Azerbaijan, Spain, Estonia,
Finland, Greece, Latvia, Russia, Serbia and Slovakia. Every one is Latin, Greek
or Cyrillic. It contains **no Devanagari, Tamil, Bengali or Perso-Arabic
document at all**, so it cannot calibrate four of our five languages. The plan
was written before the active language set changed to the Indian context and was
not revisited. See docs/decisions/0006-ocr-calibration.md.

WHAT WE DO INSTEAD
Render known text with correct shaping, degrade it to approximate capture
conditions, OCR it, and align the result against the known input. This gives
exact ground truth and full control over the corruption level, which a scanned
corpus does not — but it lacks real paper, print and capture artefacts, which a
scanned corpus does have. Both limitations are reported.

The output is a per-script confusion matrix and character error rate, in the
shape ``kyc_nli.ocr.noise`` consumes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from kyc_nli.languages import load_languages, repo_root
from kyc_nli.ocr.render import DEGRADE_LEVELS, DegradeConfig, degrade, render
from kyc_nli.schema import Script

#: Tesseract language codes for our language codes.
TESSERACT_LANGS: dict[str, str] = {
    "en": "eng",
    "hi": "hin",
    "ta": "tam",
    "bn": "ben",
    "ur": "urd",
}

_TESSERACT_CANDIDATES = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
)


TESSDATA_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main"


def tessdata_dir() -> Path:
    """Our own language-pack directory.

    Tesseract's default tessdata lives under Program Files and needs
    administrator rights to write to. Keeping the packs in the repo's gitignored
    data/external means installing them needs no elevation, and the calibration
    depends on a known set of packs rather than whatever the machine has.
    """
    return repo_root() / "data" / "external" / "tessdata"


def download_langs(languages: tuple[str, ...] | None = None) -> Path:
    """Fetch the traineddata files we need. No administrator rights required."""
    import urllib.request

    target = tessdata_dir()
    target.mkdir(parents=True, exist_ok=True)
    wanted = {TESSERACT_LANGS[x] for x in (languages or tuple(TESSERACT_LANGS))}
    for lang in sorted(wanted):
        path = target / f"{lang}.traineddata"
        if not path.exists():
            urllib.request.urlretrieve(f"{TESSDATA_URL}/{lang}.traineddata", path)  # noqa: S310
    return target


def _tess_env() -> dict[str, str]:
    """Environment for a Tesseract call, pointing it at our own tessdata."""
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    local = tessdata_dir()
    if local.is_dir() and any(local.glob("*.traineddata")):
        env["TESSDATA_PREFIX"] = str(local)
    return env


def tesseract_path() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in _TESSERACT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def available_langs() -> set[str]:
    exe = tesseract_path()
    if exe is None:
        return set()
    try:
        out = subprocess.run(  # noqa: S603 - fixed executable, no shell
            [exe, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=_tess_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return {line.strip() for line in out.stdout.splitlines()[1:] if line.strip()}


def is_available(languages: tuple[str, ...] | None = None) -> bool:
    """True when Tesseract and every needed language pack are installed."""
    if tesseract_path() is None:
        return False
    needed = {TESSERACT_LANGS[x] for x in (languages or tuple(TESSERACT_LANGS))}
    return needed <= available_langs()


def run_ocr(image, lang: str, psm: int = 7) -> str:
    """OCR a single-line image. psm 7 tells Tesseract to expect one text line."""
    exe = tesseract_path()
    if exe is None:
        raise RuntimeError("Tesseract is not installed; see docs/plan.md M1.")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.png"
        image.save(src)
        result = subprocess.run(  # noqa: S603 - fixed executable, no shell
            [exe, str(src), "stdout", "-l", lang, "--psm", str(psm)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
            env=_tess_env(),
        )
    return " ".join(result.stdout.split())


# --------------------------------------------------------------------------
# Alignment
# --------------------------------------------------------------------------


#: Zero-width formatting characters. Tesseract emits these as a rendering
#: convention, not as a reading of any ink: it appends U+200C after Tamil words
#: ending in a pure consonant (pulli), which put a constant ~0.07 floor under
#: every Tamil CER and filled the confusion tables with ZWNJ entries. They are
#: invisible, carry no identity information, and any downstream comparison would
#: normalise them away, so counting them as OCR errors overstates the error rate
#: and pollutes the measured confusions.
#:
#: Note what is NOT stripped: Arabic diacritics. Losing a kasra is a real read
#: error and one the noise model deliberately simulates.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


def normalise(text: str) -> str:
    """Canonical form for comparison: NFC, minus zero-width formatting marks."""
    return unicodedata.normalize("NFC", text).translate(_ZERO_WIDTH)


def align(truth: str, hypothesis: str) -> list[tuple[str, str, str]]:
    """Levenshtein alignment, returning (op, truth_char, hyp_char) per position.

    ``op`` is one of match, sub, del, ins. The alignment is what turns "the OCR
    output was wrong" into "this character became that character", which is the
    only form a confusion table can be built from.

    Both sides are normalised first; see ``normalise``.
    """
    truth, hypothesis = normalise(truth), normalise(hypothesis)
    n, m = len(truth), len(hypothesis)
    # cost[i][j] = edits to turn truth[:i] into hypothesis[:j]
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = i
    for j in range(1, m + 1):
        cost[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub = cost[i - 1][j - 1] + (truth[i - 1] != hypothesis[j - 1])
            cost[i][j] = min(sub, cost[i - 1][j] + 1, cost[i][j - 1] + 1)

    ops: list[tuple[str, str, str]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and cost[i][j] == cost[i - 1][j - 1] + (
            truth[i - 1] != hypothesis[j - 1]
        ):
            op = "match" if truth[i - 1] == hypothesis[j - 1] else "sub"
            ops.append((op, truth[i - 1], hypothesis[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and cost[i][j] == cost[i - 1][j] + 1:
            ops.append(("del", truth[i - 1], ""))
            i -= 1
        else:
            ops.append(("ins", "", hypothesis[j - 1]))
            j -= 1
    ops.reverse()
    return ops


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------


@dataclass
class LevelResult:
    """What the engine did to one script at one degradation level."""

    level: str
    n_words: int
    n_chars: int
    #: Character error rate: (subs + dels + ins) / truth characters.
    cer: float
    substitution_rate: float
    deletion_rate: float
    insertion_rate: float
    #: How often the engine returned nothing at all. A blank output is not a
    #: character error, it is a total read failure, and averaging it into CER
    #: would hide it.
    blank_rate: float
    confusions: Counter = field(default_factory=Counter)

    def top_confusions(self, n: int = 12) -> list[tuple[str, str, int]]:
        return [(a, b, c) for (a, b), c in self.confusions.most_common(n)]


@dataclass
class CalibrationResult:
    language: str
    script: Script
    levels: list[LevelResult]

    def confusion_table(
        self, level: str | None = None, min_count: int = 2
    ) -> dict[str, tuple[str, ...]]:
        """Measured confusions in the shape ``kyc_nli.ocr.noise`` uses."""
        merged: Counter = Counter()
        for lr in self.levels:
            if level is None or lr.level == level:
                merged.update(lr.confusions)
        table: dict[str, list[str]] = {}
        for (src, dst), count in merged.most_common():
            if count < min_count or not src.strip() or not dst.strip():
                continue
            table.setdefault(src, [])
            if dst not in table[src] and len(table[src]) < 5:
                table[src].append(dst)
        return {k: tuple(v) for k, v in table.items() if v}


def calibrate_language(
    language: str,
    words: list[str],
    levels: tuple[DegradeConfig, ...] = DEGRADE_LEVELS,
    seed: int = 20260906,
) -> CalibrationResult:
    """Render, degrade, OCR and align every word at every degradation level."""
    script = load_languages()[language].script
    tess_lang = TESSERACT_LANGS[language]
    results: list[LevelResult] = []

    for level_idx, config in enumerate(levels):
        subs = dels = ins = chars = blanks = 0
        confusions: Counter = Counter()

        for word_idx, word in enumerate(words):
            image = render(word, script, size_px=config.font_size)
            image = degrade(image, config, seed=seed + level_idx * 1000 + word_idx)
            hypothesis = run_ocr(image, tess_lang)

            chars += len(normalise(word))
            if not normalise(hypothesis):
                blanks += 1
                dels += len(normalise(word))
                continue

            for op, truth_ch, hyp_ch in align(word, hypothesis):
                if op == "sub":
                    subs += 1
                    confusions[(truth_ch, hyp_ch)] += 1
                elif op == "del":
                    dels += 1
                elif op == "ins":
                    ins += 1

        denom = chars or 1
        results.append(
            LevelResult(
                level=config.name,
                n_words=len(words),
                n_chars=chars,
                cer=(subs + dels + ins) / denom,
                substitution_rate=subs / denom,
                deletion_rate=dels / denom,
                insertion_rate=ins / denom,
                blank_rate=blanks / (len(words) or 1),
                confusions=confusions,
            )
        )

    return CalibrationResult(language=language, script=script, levels=results)


# --------------------------------------------------------------------------
# Emitting the measured tables
# --------------------------------------------------------------------------

_MODULE_HEADER = '''"""MEASURED OCR error rates and confusions. GENERATED FILE - DO NOT EDIT.

Regenerate with:  kyc-nli calibrate-ocr --words {words} --write-tables

Produced by rendering known text with correct complex-script shaping, degrading
it, running Tesseract, and aligning the output against the input. See
docs/decisions/0006-ocr-calibration.md for what this does and does not measure;
in particular, rendered text has no paper grain, glare or perspective, so these
rates are a LOWER BOUND on real-document error.

Seed {seed}. {words} words per language per level.
"""

from __future__ import annotations

'''


def render_measured_module(
    results: dict[str, CalibrationResult], words: int, seed: int
) -> str:
    """Emit a Python module carrying the measured rates and confusion tables."""
    parts: list[str] = [_MODULE_HEADER.format(words=words, seed=seed)]

    parts.append("#: Measured (substitution, deletion, insertion) rates per level,")
    parts.append("#: averaged over the Indic scripts (hi, ta, bn). English is excluded")
    parts.append("#: as the easy case and Urdu as the anomalous one -- its error is")
    parts.append("#: dominated by whole-word read failures, not character confusion.")
    parts.append("MEASURED_RATES: dict[str, dict[str, float]] = {")
    indic = [r for code, r in results.items() if code in ("hi", "ta", "bn")]
    if indic:
        for idx, level in enumerate(indic[0].levels):
            sub = sum(r.levels[idx].substitution_rate for r in indic) / len(indic)
            dele = sum(r.levels[idx].deletion_rate for r in indic) / len(indic)
            ins = sum(r.levels[idx].insertion_rate for r in indic) / len(indic)
            parts.append(
                f'    "{level.level}": {{"substitution": {sub:.4f}, '
                f'"deletion": {dele:.4f}, "insertion": {ins:.4f}}},'
            )
    parts.append("}")
    parts.append("")

    parts.append("#: Per-language whole-word read-failure rate, by level. Urdu is the")
    parts.append("#: reason this exists: its OCR failure is bimodal -- the engine either")
    parts.append("#: reads a word correctly or returns nothing at all -- which a")
    parts.append("#: character-substitution model cannot express.")
    parts.append("MEASURED_BLANK_RATES: dict[str, dict[str, float]] = {")
    for code, result in results.items():
        inner = ", ".join(f'"{lr.level}": {lr.blank_rate:.4f}' for lr in result.levels)
        parts.append(f'    "{code}": {{{inner}}},')
    parts.append("}")
    parts.append("")

    parts.append("#: Measured character confusions, most frequent first.")
    parts.append("MEASURED_CONFUSIONS: dict[str, dict[str, tuple[str, ...]]] = {")
    for code, result in results.items():
        table = result.confusion_table(min_count=3)
        parts.append(f'    "{code}": {{')
        for src, dsts in list(table.items())[:40]:
            parts.append(f"        {src!r}: {dsts!r},")
        parts.append("    },")
    parts.append("}")
    parts.append("")
    return "\n".join(parts)
