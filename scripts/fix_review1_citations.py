"""Apply the citation-audit corrections to the Review 1 deck.

Operates on raw slide XML with exact-match string replacement. Every target is a
complete <a:t> run (verified by inspection), so no run-splitting is involved and
no XML is reparsed — round-tripping OOXML through ElementTree rewrites namespace
prefixes and corrupts the deck.

Every replacement asserts it found exactly the expected number of occurrences.
A silent no-op here would leave a wrong number in a deck we have told the user is
corrected, which is worse than crashing.

Usage (from the repo root):

    python scripts/fix_review1_citations.py \
        "docs/proposal/NLP review 1.pptx" \
        "docs/proposal/NLP review 1 (corrected).pptx"

Corrections and their sources are documented in docs/literature/citation-audit.md.
This script is the record of exactly what was changed; do not edit the corrected
deck by hand without adding the edit here too.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="kyc-nli-deck-"))

# (slide number, old run text, new run text, expected occurrences)
EDITS: list[tuple[int, str, str, int]] = [
    # ---------------- Paper 1, FakeIDet2: wrong year and four wrong figures
    (4, "<a:t>2026</a:t>", "<a:t>2025</a:t>", 1),
    (
        4,
        "EER: 1.69% vs 54.25% (baseline) on composite attacks • 9.56% (DLC-2021), "
        "14.47% (KID34K) cross-DB • 37.51% on GAN-generated fakes • "
        "4.05%→16.54% as anonymization increases.",
        "EER: 2.09% vs 54.08% (FakeIDet baseline) on composite attacks • 8.90% "
        "(DLC-2021), 13.84% (KID34K) cross-DB • 39.41% on synthetic/GAN "
        "(Benalcazar et al.) • anonymization degradation reported.",
        1,
    ),
    # ---------------- Paper 4, Adam & Kliegr: journal publication, not a preprint
    (7, "<a:t>2024</a:t>", "<a:t>2025</a:t>", 1),
    (
        7,
        "<a:t>arXiv / KG venue</a:t>",
        "<a:t>Information Processing &amp; Management (Elsevier)</a:t>",
        1,
    ),
    # ---------------- Paper 9, Marchesin et al.: an EDITORIAL, not a survey
    (
        12,
        "Survey / position analysis: systematically categorizes LLM roles across KG "
        "data-quality pipelines and compares reported performance and failure "
        "patterns across studies.",
        "Guest editorial introducing an IPM special issue — not a survey. Frames the "
        "problem space of LLMs in KG data quality and introduces the issue's "
        "contributed papers.",
        1,
    ),
    (
        12,
        "Cross-study comparative summary; no single new empirical figure (survey format).",
        "Editorial format: no empirical results of its own.",
        1,
    ),
    (
        12,
        "Systematic categorization of LLM roles in KG quality • cross-study comparison "
        "surfaces recurring failure patterns.",
        "Assembles a current set of contributed papers on LLMs for KG data quality • "
        "useful as a pointer into that literature.",
        1,
    ),
    (
        12,
        "No new empirical benchmark of its own • reliability bounded by the "
        "heterogeneous studies it surveys • limited treatment of noisy/OCR-derived "
        "text specifically.",
        "An editorial, not a systematic review: no stated search protocol and no "
        "cross-study synthesis of its own • cite it as a pointer, not as evidence.",
        1,
    ),
    # ---------------- Paper 12, González & Tapia: wrong architecture, known dataset size
    (
        15,
        "CNN-based presentation-attack detector using a modality-decoupled "
        "architecture — separate detection branches per attack type — trained on "
        "captured vs. presentation-attack ID card images.",
        "Hybrid two-stage multiclass network for end-to-end presentation-attack "
        "detection, built on MobileNetV2: a serial two-stage architecture trained "
        "from scratch.",
        1,
    ),
    (
        15,
        "Private Chilean ID card image database (third-party; not publicly released "
        "due to privacy constraints).",
        "Chilean ID card database of 190K real-case images, plus new fake images from "
        "synthetic and PVC ID cards; not publicly released due to privacy constraints.",
        1,
    ),
    (
        15,
        "Modality-decoupling improves per-attack-type detection granularity.",
        "Among the first end-to-end PAD evaluations on ID cards • the two-stage design "
        "separates detection from attack-type classification.",
        1,
    ),
    (
        15,
        "Private, single-country, non-public dataset limits reproducibility and "
        "cross-country generalization claims • vision-only, no textual/semantic layer.",
        "Single-country, non-public dataset limits reproducibility and cross-country "
        "generalization claims • vision-only, no textual/semantic layer.",
        1,
    ),
    # ---------------- Comparative analysis table
    (16, "<a:t>FakeIDet2 (2026)</a:t>", "<a:t>FakeIDet2 (2025)</a:t>", 1),
    (16, "<a:t>Adam &amp; Kliegr (2024)</a:t>", "<a:t>Adam &amp; Kliegr (2025)</a:t>", 1),
    (16, "<a:t>Survey / categorization</a:t>", "<a:t>Editorial, not a survey</a:t>", 1),
    (16, "<a:t>Meta-analysis</a:t>", "<a:t>None (editorial)</a:t>", 1),
    (16, "<a:t>CNN, modality-decoupled</a:t>", "<a:t>MobileNetV2, 2-stage serial</a:t>", 1),
    (16, "<a:t>Private Chilean DB</a:t>", "<a:t>Chilean ID DB (190K)</a:t>", 1),
    (16, "<a:t>Private, single-country data</a:t>", "<a:t>Single-country, non-public</a:t>", 1),
    # ---------------- Paper 2, Voerman et al.: full title and author order
    (
        5,
        "<a:t>J. Voerman, M. Al-Ghadi, M. Coustaty, et al.</a:t>",
        "<a:t>J. Voerman, M. Al-Ghadi, N. Sidere, M. Coustaty, O. Lessard</a:t>",
        1,
    ),
]

# Paper Title cell on slide 4 only (leave the slide heading short so it still fits).
SLIDE4_TITLE_CELL = (
    "<a:t>Paper Title</a:t>",
    "FakeIDet2: Privacy-Aware Detection of Fake Identity Documents",
    "Privacy-Aware Detection of Fake Identity Documents: Methodology, Benchmark, "
    "and Improved Algorithms (FakeIDet2)",
)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    if not src.exists():
        print(f"FAIL: {src} not found")
        return 1
    with zipfile.ZipFile(src) as z:
        z.extractall(ROOT)

    changed: dict[int, str] = {}

    for slide, old, new, expected in EDITS:
        path = ROOT / f"ppt/slides/slide{slide}.xml"
        s = changed.get(slide) or path.read_text(encoding="utf-8")
        found = s.count(old)
        if found != expected:
            print(f"FAIL slide{slide}: expected {expected} occurrence(s), found {found}")
            print(f"      {old[:90]!r}")
            return 1
        changed[slide] = s.replace(old, new)
        print(f"  ok  slide{slide}: {old[:60]!r}")

    # Slide 4 Paper Title cell: the same string is also the slide heading, so
    # rewrite only the occurrence that follows the "Paper Title" label.
    anchor, old_title, new_title = SLIDE4_TITLE_CELL
    s = changed[4]
    idx = s.find(anchor)
    if idx == -1:
        print("FAIL slide4: 'Paper Title' anchor not found")
        return 1
    tail = s[idx:]
    if tail.count(old_title) != 1:
        print(
            f"FAIL slide4: expected 1 title occurrence after the anchor, "
            f"found {tail.count(old_title)}"
        )
        return 1
    changed[4] = s[:idx] + tail.replace(old_title, new_title, 1)
    print("  ok  slide4: Paper Title cell -> published title")

    for slide, content in changed.items():
        target = ROOT / f"ppt/slides/slide{slide}.xml"
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)

    if out.exists():
        out.unlink()
    files = sorted(p for p in ROOT.rglob("*") if p.is_file())
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(ROOT).as_posix())
    print(f"\nwrote {out} ({out.stat().st_size:,} bytes, {len(files)} parts)")
    shutil.rmtree(ROOT, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
