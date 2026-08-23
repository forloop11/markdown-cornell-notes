#!/usr/bin/env python3
"""Convert notes.md into build/cornell-content.tex: one \\cornellFlow{...}
per section of main-panel content.

pandoc converts Markdown to LaTeX; \\cornellFlow (defined in
cornell-notes.tex) then measures that content with TeX's \\vsplit and
automatically breaks it across as many pages as it actually needs, each
carrying the same repeating header (see meeting.yaml) and the next page
number.

A line containing only

    <!-- pagebreak -->

forces an extra break between two sections (e.g. to start a new topic on
its own page) on top of whatever automatic breaks \\cornellFlow inserts.

Usage (from the repo root): python3 scripts/markdown_to_pages.py [input.md] [output.tex]
"""
import os
import re
import subprocess
import sys

PAGEBREAK_RE = re.compile(r"^\s*<!--\s*pagebreak\s*-->\s*$", re.MULTILINE)


def markdown_to_latex(markdown):
    result = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "latex"],
        input=markdown,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pandoc failed: {result.stderr}")
    return result.stdout.strip()


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else "notes.md"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "build/cornell-content.tex"

    with open(in_path, encoding="utf-8") as f:
        markdown = f.read()

    chunks = [chunk.strip() for chunk in PAGEBREAK_RE.split(markdown)]
    chunks = [chunk for chunk in chunks if chunk]
    if not chunks:
        chunks = [""]

    pages = []
    for chunk in chunks:
        latex = markdown_to_latex(chunk)
        pages.append(f"\\cornellFlow{{%\n{latex}%\n}}")

    lines = [
        f"% Generated from {in_path} by scripts/markdown_to_pages.py -- do not edit by hand.",
        "",
        "\n\n".join(pages),
    ]

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
