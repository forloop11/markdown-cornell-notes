#!/usr/bin/env python3
"""Convert notes.md into build/cornell-content.tex: one cornellFlow
environment per section of main-panel content.

pandoc converts Markdown to LaTeX; \\cornellFlow (defined in
settings/template.tex) then measures that content with TeX's \\vsplit and
automatically breaks it across as many pages as it actually needs, each
carrying the same repeating header (see header.yaml) and the next page
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

LONGTABLE_RE = re.compile(
    # spec is captured non-greedily up to the "}\n" that closes the
    # \begin{longtable}{...} argument -- can't use [^}]* here since
    # pandoc's column specs contain their own braces (e.g. "@{}ll@{}").
    r"\\begin\{longtable\}\[[^\]]*\]\{(?P<spec>.*?)\}\n(?P<body>.*?)\\end\{longtable\}",
    re.DOTALL,
)
LONGTABLE_MARKER_RE = re.compile(r"\\end(firsthead|head|foot|lastfoot)\s*\n?")
CAPTION_RE = re.compile(r"\A\\caption\{(?P<text>.*?)\}\\tabularnewline\s*\n", re.DOTALL)


def delongtable(latex):
    """Rewrite pandoc's \\begin{longtable}...\\end{longtable} (emitted for
    every pipe table) into a plain tabular.

    longtable is page-builder-aware: it tracks \\pagegoal/\\pagetotal to
    decide where to break a table across real pages, and anchors its
    closing rule (the \\endlastfoot block) near the page bottom in case
    the table turns out short on its final page. cornellFlow's tables
    always live inside a \\vsplit'd, fixed-height vbox rather than a real
    page, so that anchoring glue just stretches to fill the whole panel,
    shoving the table to the bottom with a big gap above it. Since these
    tables always fit within one panel -- cornellFlow's own \\vsplit loop
    is what paginates across panels -- longtable's multi-page machinery
    is both unneeded and actively harmful here.

    longtable's source order is header, footer, then body rows (footer
    comes before the rows because it's meant to repeat at the end of
    every page), marked off by \\endfirsthead/\\endhead/\\endfoot/
    \\endlastfoot. Reassembling as header + body + footer restores the
    order a plain tabular needs. \\caption (float-only; would crash the
    same way a captioned image does, see markdown-implicit_figures
    below) is downgraded to a bold text line above the table.

    The result is horizontally centered in the notes panel via
    \\centering (a declaration, not the `center` environment -- `center`
    adds stretchy vertical glue of its own, which risks the same
    panel-stretching bug this function exists to fix).
    """

    def convert(m):
        spec = m.group("spec")
        body = m.group("body")

        cap_m = CAPTION_RE.match(body)
        caption = None
        if cap_m:
            caption = cap_m.group("text")
            body = body[cap_m.end():]

        segments = {}
        pos = 0
        for marker in LONGTABLE_MARKER_RE.finditer(body):
            segments[marker.group(1)] = body[pos:marker.start()]
            pos = marker.end()
        row_body = body[pos:]

        header = segments.get("firsthead", segments.get("head", ""))
        footer = segments.get("lastfoot", segments.get("foot", ""))

        tabular = f"\\begin{{tabular}}{{{spec}}}\n{header}{row_body}{footer}\\end{{tabular}}"
        if caption:
            tabular = f"\\textbf{{{caption}}}\\par\n{tabular}"
        # \centering (a declaration, not the `center` environment) just
        # changes alignment for this group -- unlike `center`, it adds no
        # extra stretchy vertical glue, so it can't reintroduce the same
        # vsplit-panel-stretching bug longtable had.
        return f"{{\\centering\n{tabular}\\par}}"

    return LONGTABLE_RE.sub(convert, latex)


# A line that is *only* an \includegraphics call is a standalone image
# paragraph (e.g. ![Tux](tux.jpg) on its own line in notes.md) -- pandoc
# emits nothing else around it in that case. An image inline within a
# sentence never matches this (it shares its line with surrounding text),
# so this can't mis-fire on inline images.
STANDALONE_IMAGE_RE = re.compile(
    r"^\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}$", re.MULTILINE
)


def center_standalone_images(latex):
    """Horizontally center a standalone image paragraph in the notes
    panel, the same way delongtable() centers tables. \\centering is
    scoped to just this line, so it can't leak into surrounding text.
    """
    return STANDALONE_IMAGE_RE.sub(lambda m: f"{{\\centering\n{m.group(0)}\\par}}", latex)


def markdown_to_latex(markdown):
    result = subprocess.run(
        # --no-highlight: without it, a fenced code block with a language
        # tag (e.g. ```python) emits \begin{Shaded}/\Highlighting, which
        # need pandoc's syntax-highlighting preamble (fancyvrb, framed,
        # Tok color commands) that this document doesn't load. Plain
        # \begin{verbatim} works with any language tag or none.
        #
        # markdown-implicit_figures: without it, a standalone image with
        # alt text (e.g. ![Tux](tux.jpg)) is wrapped in a LaTeX `figure`
        # float with \caption. Floats need real page-level vertical mode
        # and crash ("Not in outer par mode") inside cornellFlow's vbox.
        # Disabling the extension keeps alt text but always emits a bare
        # \includegraphics.
        #
        # --wrap=none: without it, pandoc word-wraps its LaTeX output at
        # ~72 columns for readability. That's invisible in normal prose,
        # but center_standalone_images() below distinguishes "an image
        # alone on its line" (its own paragraph) from "an inline image
        # mid-sentence" -- and wrapping can put an inline image alone on
        # a line purely by coincidence of line length. --wrap=none keeps
        # each paragraph on one line so that heuristic is reliable.
        ["pandoc", "-f", "markdown-implicit_figures", "-t", "latex", "--no-highlight", "--wrap=none"],
        input=markdown,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pandoc failed: {result.stderr}")
    return center_standalone_images(delongtable(result.stdout.strip()))


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
        pages.append(f"\\begin{{cornellFlow}}\n{latex}\n\\end{{cornellFlow}}")

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
