"""Retrieve canonical citation metadata and official ACL style files."""
from __future__ import annotations

import concurrent.futures
import re
import urllib.request

from kyc_nli.languages import repo_root

ACL = {
    "bowman2015snli": "D15-1075", "williams2018mnli": "N18-1101",
    "yin2021docnli": "2021.findings-acl.435",
    "koreeda2021contractnli": "2021.findings-emnlp.164",
    "gardner2020contrast": "2020.findings-emnlp.117",
    "gururangan2018annotation": "N18-2017", "mccoy2019right": "P19-1334",
    "roark2020dakshina": "2020.lrec-1.294", "devlin2019bert": "N19-1423",
    "conneau2020xlmr": "2020.acl-main.747", "koehn2004significance": "W04-3250",
}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "KYC-NLI citation audit"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def main():
    root = repo_root()
    sources = root / "docs/literature/primary_bib"
    sources.mkdir(parents=True, exist_ok=True)

    def entry(item):
        key, identifier = item
        raw = fetch(f"https://aclanthology.org/{identifier}.bib").decode("utf-8")
        raw = re.sub(r'\n\s*abstract\s*=\s*".*?"\s*,?\n', "\n", raw, flags=re.S)
        raw = re.sub(r"(@\w+\{)[^,]+", lambda m: m[1] + key, raw, count=1)
        raw = raw.rstrip() + "\n"
        (sources / f"{key}.bib").write_text(raw, encoding="utf-8")
        return "% AUDITED primary ACL Anthology metadata, 2026-10-28.\n" + raw

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(entry, ACL.items()))
    extra = (root / "scripts/paper_primary_extras.bib").read_text(encoding="utf-8")
    (root / "paper/references.bib").write_text(
        "% Audit: docs/literature/paper-citation-audit-2026-10-28.md\n"
        + "\n".join(entries) + "\n" + extra, encoding="utf-8")
    for name in ("acl.sty", "acl_natbib.bst"):
        (root / "paper" / name).write_bytes(fetch(
            f"https://raw.githubusercontent.com/acl-org/acl-style-files/master/{name}"))
    print("Retrieved canonical bibliography metadata and official ACL style files")


if __name__ == "__main__":
    main()
