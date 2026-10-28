"""Build the presenter guide as PDF and Word from docs/PRESENTER-GUIDE.md.

    python scripts/build_presenter_docs.py            # -> build/presenter/
    python scripts/build_presenter_docs.py --out DIR

PDF: the markdown is rendered to a print-styled HTML page and printed by the
system's Edge or Chrome in headless mode. A browser does correct complex-script
shaping, which is why it is used rather than a Python PDF library: the guide
contains Bengali and Devanagari, and a renderer without HarfBuzz would misplace
the vowel signs.

Word: written by scripts/presenter_docx.js, which needs Node and the `docx`
package (`npm install docx` in scripts/). Skipped with a note if unavailable.

The markdown is the source of truth. It mirrors the shared presenter doc; edit
one, then the other, then rebuild.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "PRESENTER-GUIDE.md"
TITLE = "KYC-NLI: Plain-English Walkthrough"

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "Segoe UI", "Nirmala UI", system-ui, sans-serif; font-size: 10.8pt;
  line-height: 1.55; color: #1a1a1a; margin: 0; print-color-adjust: exact;
  -webkit-print-color-adjust: exact; }
h1 { font-size: 23pt; line-height: 1.2; margin: 0 0 4pt; letter-spacing: -0.3pt; }
h2 { font-size: 15pt; margin: 20pt 0 7pt; padding-bottom: 3pt; border-bottom: 1px solid #d8d8d8;
  break-after: avoid; }
h3 { font-size: 11.6pt; margin: 14pt 0 5pt; color: #333; break-after: avoid; }
p { margin: 0 0 8pt; }
.lede { color: #555; font-size: 10pt; margin-bottom: 16pt; }
ul { margin: 0 0 10pt; padding-left: 17pt; } li { margin-bottom: 4pt; }
blockquote { margin: 10pt 0 12pt; padding: 7pt 0 7pt 12pt; border-left: 3px solid #999;
  background: #fafafa; break-inside: avoid; }
blockquote p { margin: 0; }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 9.3pt; background: #f1f1f1;
  padding: 1px 4px; border-radius: 3px; }
pre { font-family: Consolas, "Cascadia Mono", "Nirmala UI", monospace; font-size: 9pt;
  background: #f5f5f5; border: 1px solid #e2e2e2; border-radius: 4px; padding: 8pt 10pt;
  margin: 0 0 11pt; white-space: pre; break-inside: avoid; line-height: 1.45; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 0 0 12pt; font-size: 9.8pt;
  break-inside: avoid; }
th, td { border: 1px solid #d5d5d5; padding: 5pt 7pt; text-align: left; vertical-align: top; }
th { background: #f0f0f0; font-weight: 600; }
strong { font-weight: 600; }
"""


def inline(text: str) -> str:
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    return out


def to_html(md: str) -> str:
    """The markdown subset the guide uses: headings, paragraphs, lists, quotes,
    fenced code and tables."""
    lines, body, i, lede_done = md.split("\n"), [], 0, False
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(html.escape(lines[i], quote=False))
                i += 1
            i += 1
            body.append("<pre><code>" + "\n".join(block) + "</code></pre>")
        elif line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, *rest = rows
            body.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head)
                        + "</tr></thead><tbody>")
            body += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rest]
            body.append("</tbody></table>")
        elif m := re.match(r"^(#{1,3})\s+(.*)$", line):
            n = len(m.group(1))
            body.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            i += 1
        elif line.startswith(">"):
            quoted = []
            while i < len(lines) and lines[i].startswith(">"):
                quoted.append(lines[i].lstrip(">").strip())
                i += 1
            body.append(f"<blockquote><p>{inline(' '.join(quoted))}</p></blockquote>")
        elif re.match(r"^[-*]\s+", line):
            body.append("<ul>")
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                item = re.sub(r"^[-*]\s+", "", lines[i])
                body.append(f"<li>{inline(item)}</li>")
                i += 1
            body.append("</ul>")
        else:
            cls = ""
            if not lede_done and body and body[0].startswith("<h1>"):
                cls, lede_done = ' class="lede"', True
            body.append(f"<p{cls}>{inline(line)}</p>")
            i += 1
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{TITLE}</title>"
            f"<style>{CSS}</style></head><body>" + "\n".join(body) + "</body></html>")


def find_browser() -> str | None:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("msedge")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "presenter")
    args = ap.parse_args()
    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    page = out / "presenter-guide.html"
    page.write_text(to_html(SOURCE.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"wrote {page}")

    pdf = out / f"{TITLE.replace(':', '')}.pdf"
    browser = find_browser()
    if browser is None:
        print("no Edge/Chrome found: open the HTML and print it to PDF by hand")
    else:
        subprocess.run(
            [browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf}", page.as_uri()],
            check=True, capture_output=True,
        )
        print(f"wrote {pdf} ({pdf.stat().st_size // 1024} KB)")

    docx = out / f"{TITLE.replace(':', '')}.docx"
    node = shutil.which("node")
    script = ROOT / "scripts" / "presenter_docx.js"
    if node is None:
        print("node not found: skipping the Word file")
        return 0
    result = subprocess.run([node, str(script), str(SOURCE), str(docx)],
                            capture_output=True, text=True, env=os.environ.copy())
    if result.returncode:
        print("Word file skipped:", (result.stderr.strip().splitlines() or ["?"])[-1])
        print("  install its one dependency with:  cd scripts && npm install docx")
    else:
        print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
