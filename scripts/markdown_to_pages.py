#!/usr/bin/env python3
"""Convert md/notes.md into build/cornell-content.tex: one cornellFlow
environment per section of main-panel content. Also writes
build/cornell-cue.tex and build/cornell-summary.tex, which carry any
"^<page> <text>" / "^^<page> <text>" entries (see below) to their target
page's cue column / summary band.

pandoc converts Markdown to LaTeX; \\cornellFlow (defined in
settings/template.tex) then measures that content with TeX's \\vsplit and
automatically breaks it across as many pages as it actually needs, each
carrying the same repeating header (see yaml/header.yaml) and the next page
number.

A line containing only

    <!-- pagebreak -->

forces an extra break between two sections (e.g. to start a new topic on
its own page) on top of whatever automatic breaks \\cornellFlow inserts.

A line of the form

    ^<page> <text>

e.g. "^1 This is my question for Cue", adds <text> to the cue
column of the given page number (the actual rendered PDF page, matching
the "Page N" printed in each page's header) instead of the main notes
panel. Multiple entries targeting the same page render as a bulleted
list, in document order.

Similarly, a line of the form

    ^^<page> <text>

adds <text> to the page's summary band (the strip at the bottom of
the page) instead. Multiple entries targeting the same page render as
separate lines, in document order.

A page number below 1 is clamped to page 1. A page number past the end
of the document (e.g. "^99" in a 3-page document) renders on the actual
last page instead of silently vanishing.

Usage (from the repo root): python3 scripts/markdown_to_pages.py [input.md] [content.tex] [cue.tex] [summary.tex]
"""
import os
import re
import subprocess
import sys
from collections import defaultdict

PAGEBREAK_RE = re.compile(r"^\s*<!--\s*pagebreak\s*-->\s*$", re.MULTILINE)

# A whole line of the form "^<page> <text>" -- the caret must be followed
# directly by an optionally-signed integer then whitespace, so it can't
# be confused with pandoc's inline superscript syntax (e.g. "x^2^" or
# "x^-1^"), which never has a space right after the opening caret.
# "^^<page> <text>" (summary-band entries, see SUMMARY_RE) never matches
# this: the character right after the first caret is the second caret,
# not a digit or a sign.
CUE_RE = re.compile(r"^\^(?P<page>-?\d+)[ \t]+(?P<text>.+?)[ \t]*$", re.MULTILINE)

# A whole line of the form "^^<page> <text>" -- see module docstring.
SUMMARY_RE = re.compile(r"^\^\^(?P<page>-?\d+)[ \t]+(?P<text>.+?)[ \t]*$", re.MULTILINE)

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


# \href{<target>} -- pandoc emits this uniformly for every Markdown link,
# web URLs (https://...) and local files (assets/foo.txt) alike.
HREF_RE = re.compile(r"\\href\{([^}]*)\}")

# A URL with a scheme (http:, mailto:, ...) or a leading "/" or "#" is
# absolute/fragment and must be left alone; anything else is a path
# relative to the repo root, since that's `make build`'s compiling cwd
# regardless of where the input markdown file itself lives.
ABSOLUTE_LINK_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|/|#)")

# make build compiles with the repo root as cwd (so \includegraphics still
# resolves images at compile time) but writes the PDF one level down, into
# pdf/ (see Makefile's OUTDIR) -- PDF viewers resolve a relative \href
# target against the PDF's own location, not the compiling cwd, so local
# links need this "step back up to the repo root" prefix to still work.
RELATIVE_LINK_PREFIX = "../"


def rebase_relative_links(latex):
    def rebase(match):
        target = match.group(1)
        if ABSOLUTE_LINK_RE.match(target):
            return match.group(0)
        return f"\\href{{{RELATIVE_LINK_PREFIX}{target}}}"

    return HREF_RE.sub(rebase, latex)


def extract_directive_entries(markdown, pattern):
    """Pull directive lines matching `pattern` (CUE_RE or SUMMARY_RE) out
    of markdown, returning (remaining_markdown, entries), where entries is
    a list of (page_number, text) in document order and remaining_markdown
    has each directive line blanked out (so it doesn't also show up as a
    main-panel paragraph). A page number below 1 is clamped to 1 -- page 1
    always exists, so there's no ambiguity about where "before the start"
    should land. A page number past the end of the document is handled at
    render time instead (see render_cue_tex/render_summary_tex): the
    generator has no way to know the final page count yet, since it's
    only decided later by \\vsplit-based pagination in settings/template.tex.
    """
    entries = []

    def collect(m):
        entries.append((max(int(m.group("page")), 1), m.group("text")))
        return ""

    return pattern.sub(collect, markdown), entries


def as_list(env, texts):
    """Wrap `texts` (already-converted LaTeX) as \\item entries inside
    `env`, a settings/template.tex list environment (cnCueList or
    cnSummaryList).
    """
    items = "".join(f"\\item {text}\n" for text in texts)
    return f"\\begin{{{env}}}\n{items}\\end{{{env}}}"


def render_directive_tex(macro, env, entries):
    """Build the content of a \\renewcommand{<macro>} that, given the
    current page number as #1, returns every entry targeting that page
    (each run through the same Markdown/LaTeX pipeline as the main
    content), wrapped in `env`.

    A page number past the end of the document can't be caught at
    generation time (see extract_directive_entries), so every entry also
    gets a fallback branch, active only on the document's actual last
    page (\\ifcnlastpage, set by \\cnFlowLoop in settings/template.tex):
    if the entry's target page is still greater than #1 there -- i.e. it
    was never matched by an earlier, real page -- it renders there
    instead of silently vanishing.
    """
    by_page = defaultdict(list)
    for page, text in entries:
        by_page[page].append(markdown_to_latex(text))

    body = "".join(
        f"  \\ifnum#1={page} {as_list(env, texts)}\\fi%\n"
        f"  \\ifcnlastpage\\ifnum{page}>#1 {as_list(env, texts)}\\fi\\fi%\n"
        for page, texts in sorted(by_page.items())
    )
    return f"\\renewcommand{{{macro}}}[1]{{%\n{body}}}\n"


def render_cue_tex(entries):
    """Build build/cornell-cue.tex's content: a \\renewcommand{\\cnCueText}
    that, given a page number, returns every "^<page> <text>" entry
    targeting that page (each run through the same Markdown/LaTeX
    pipeline as the main content) as a bullet in an unordered list.
    """
    return render_directive_tex("\\cnCueText", "cnCueList", entries)


def render_summary_tex(entries):
    """Build build/cornell-summary.tex's content: a
    \\renewcommand{\\cnSummaryText} that, given a page number, returns
    every "^^<page> <text>" entry targeting that page (each run through
    the same Markdown/LaTeX pipeline as the main content) as an item in
    an ordered (numbered) list, in document order.
    """
    return render_directive_tex("\\cnSummaryText", "cnSummaryList", entries)


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
    latex = rebase_relative_links(result.stdout.strip())
    return center_standalone_images(delongtable(latex))


def write_generated(out_path, in_path, body):
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    header = f"% Generated from {in_path} by scripts/markdown_to_pages.py -- do not edit by hand.\n\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + body)


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else "md/notes.md"
    content_path = sys.argv[2] if len(sys.argv) > 2 else "build/cornell-content.tex"
    cue_path = sys.argv[3] if len(sys.argv) > 3 else "build/cornell-cue.tex"
    summary_path = sys.argv[4] if len(sys.argv) > 4 else "build/cornell-summary.tex"

    with open(in_path, encoding="utf-8") as f:
        markdown = f.read()

    # Summary entries ("^^<page>") first: SUMMARY_RE can't accidentally
    # match a cue line, but stripping summary lines first keeps the
    # extraction order self-evident regardless.
    markdown, summary_entries = extract_directive_entries(markdown, SUMMARY_RE)
    markdown, cue_entries = extract_directive_entries(markdown, CUE_RE)

    chunks = [chunk.strip() for chunk in PAGEBREAK_RE.split(markdown)]
    chunks = [chunk for chunk in chunks if chunk]
    if not chunks:
        chunks = [""]

    pages = []
    for chunk in chunks:
        latex = markdown_to_latex(chunk)
        pages.append(f"\\begin{{cornellFlow}}\n{latex}\n\\end{{cornellFlow}}")

    # Marks the last cornellFlow block so \cnFlowLoop (settings/template.tex)
    # can tell, once it's producing that block's own last \vsplit page, that
    # it's rendering the document's actual final page -- see \cnlastpage in
    # render_directive_tex above.
    pages[-1] = "\\cnfinalflowtrue\n" + pages[-1]

    write_generated(content_path, in_path, "\n\n".join(pages) + "\n")
    write_generated(cue_path, in_path, render_cue_tex(cue_entries))
    write_generated(summary_path, in_path, render_summary_tex(summary_entries))


if __name__ == "__main__":
    main()
