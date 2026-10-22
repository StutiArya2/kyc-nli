"""Structural checks on the paper, for a machine with no LaTeX installed.

    python scripts/check_paper.py

This does not replace compiling. It catches the errors that a missing compiler
would otherwise hide until the night before a deadline: unbalanced braces,
mismatched environments, characters pdfLaTeX cannot typeset, references to
labels, citations, figures or tables that do not exist, and unverified
references that the text actually cites.
"""

from __future__ import annotations

import re
import sys

from kyc_nli.languages import repo_root

PAPER = repo_root() / "paper"


def strip_comments(tex: str) -> str:
    # A % starts a comment unless escaped as \%.
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in tex.splitlines())


def main() -> int:
    src = (PAPER / "main.tex").read_text(encoding="utf-8")
    tex = strip_comments(src)
    problems: list[str] = []

    # 1. Braces, ignoring escaped ones.
    depth = 0
    for lineno, line in enumerate(tex.splitlines(), 1):
        for ch in re.sub(r"\\[{}]", "", line):
            depth += {"{": 1, "}": -1}.get(ch, 0)
            if depth < 0:
                problems.append(f"line {lineno}: closing brace with nothing open")
                depth = 0
    if depth:
        problems.append(f"{depth} unclosed brace(s) at end of file")

    # 2. Environments must nest.
    stack: list[tuple[str, int]] = []
    for m in re.finditer(r"\\(begin|end)\{([^}]+)\}", tex):
        kind, env = m.groups()
        lineno = tex.count("\n", 0, m.start()) + 1
        if kind == "begin":
            stack.append((env, lineno))
        elif not stack or stack[-1][0] != env:
            open_env = stack[-1] if stack else ("nothing", 0)
            problems.append(f"line {lineno}: \\end{{{env}}} closes {open_env[0]} "
                            f"(opened line {open_env[1]})")
        else:
            stack.pop()
    problems += [f"line {ln}: \\begin{{{env}}} never closed" for env, ln in stack]

    # 3. Characters pdfLaTeX + T1/utf8 will not typeset. Accented Latin is fine;
    #    anything else must be written as a command or avoided.
    for lineno, line in enumerate(src.splitlines(), 1):
        for ch in line:
            if ord(ch) > 0x17F:
                problems.append(f"line {lineno}: non-Latin character U+{ord(ch):04X} {ch!r}")
        if re.search(r'\\char"[0-9A-Fa-f]{3,}', line):
            problems.append(f"line {lineno}: \\char beyond 0xFF fails in an 8-bit font")

    # 4. Labels, refs, citations.
    labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
    for ref in sorted(set(re.findall(r"\\(?:ref|autoref|cref)\{([^}]+)\}", tex))):
        if ref not in labels:
            problems.append(f"\\ref{{{ref}}} has no matching \\label")

    bib = (PAPER / "references.bib").read_text(encoding="utf-8")
    # Each entry runs to the first line that is a lone closing brace. Reading to
    # the next "@" instead swallowed the divider comment between the two tiers,
    # so the last audited entry was reported as UNVERIFIED.
    entries = dict(re.findall(r"@\w+\{([^,]+),(.*?)\n\}", bib, re.S))
    cited = set()
    for group in re.findall(r"\\cite[pt]?\*?(?:\[[^\]]*\])?\{([^}]+)\}", tex):
        cited.update(k.strip() for k in group.split(","))
    for key in sorted(cited):
        if key not in entries:
            problems.append(f"cited key {key!r} is not in references.bib")
    unverified = sorted(k for k in cited if k in entries and "UNVERIFIED" in entries[k])

    # 5. Figures and tables that are pulled in must exist.
    for fig in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex):
        if not (PAPER / f"{fig}.pdf").exists():
            problems.append(f"figure {fig}.pdf missing -- run scripts/make_figures.py")
    for tab in re.findall(r"\\input\{([^}]+)\}", tex):
        if not (PAPER / f"{tab}.tex").exists():
            problems.append(f"table {tab}.tex missing -- run scripts/make_tables.py")

    print(f"cited: {len(cited)} references ({len(cited) - len(unverified)} audited, "
          f"{len(unverified)} unverified)")
    if unverified:
        print("  verify before submission: " + ", ".join(unverified))
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nNo structural problems found. (This is not a substitute for compiling.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
