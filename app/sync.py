"""Matching places in the markdown with places in the PDF built from it,
so the editor and the preview can follow each other.

The build keeps no record of which markdown line became which part of
which page (pandoc and LaTeX sit in between), so the match is by text: a
line's words, as they will read once typeset, are looked for in the PDF's
text (editor -> preview), and a run of text clicked in the PDF is looked
for among the lines (preview -> editor). That's approximate -- repeated
phrases are told apart only by how far through the document they are, and
tables, math, and text edited since the last render may not be found --
but headings and ordinary prose land where they should.

Nothing here touches Qt; window.py wires it to the two views.
"""
import re
import unicodedata

# How many words of a line to look for, most specific first. Short runs
# stay clear of the PDF's line breaks and hyphenation; longer ones tell
# repeated openings apart.
SNIPPET_WORDS = (6, 4, 3, 2)
# How far above the cursor's line to look for one with text to match.
LOOK_BACK_LINES = 40

_TRANSLATE = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'", "′": "'",
        "“": '"', "”": '"', "„": '"', "″": '"',
        "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
        "…": "...",
        "­": "",
    }
)  # fmt: skip

_COMMENT_RE = re.compile(r"<!--.*?-->")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)(\{[^}]*\})?")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MATH_RE = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$")
_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
# What starts a line without being its text: heading marks, quote marks,
# list bullets and numbers, task boxes, and the ^<page> / ^^<page> of a
# cue or summary note.
_PREFIX_RE = re.compile(r"^\s*(?:(?:#{1,6}|>|[-*+]|\d+[.)])\s+|\[[ xX]\]\s+|\^{1,2}\d+\s+)*")
_MARKUP_RE = re.compile(r"[*_~`\\]|\^(?=\S)")
_TABLE_RULE_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
# The section number LaTeX puts before a heading's text ("2.1 Lists").
_SECTION_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*\s+")


def normalize(text):
    """Fold away what differs between source and typeset text without
    changing what it says: ligatures and other compatibility forms,
    typographic quotes and dashes (and the -- and --- that become them),
    case, and runs of whitespace. frontend_src/pdfviewer.js's normalize()
    does the same to the PDF's text.
    """
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE)
    text = re.sub(r"-{2,}", "-", text)
    return " ".join(text.lower().split())


def plain(line):
    """A markdown line's text roughly as it reads in the PDF: without its
    markup, normalized. "" for a line that contributes no text of its own
    (a blank line, a comment, a table's rule, a code fence).
    """
    if line.lstrip().startswith("```") or _TABLE_RULE_RE.match(line):
        return ""
    line = _COMMENT_RE.sub(" ", line)
    line = _MATH_RE.sub(" ", line)
    line = _IMAGE_RE.sub(" ", line)
    line = _LINK_RE.sub(r"\1", line)
    line = _TAG_RE.sub(" ", line)
    line = _PREFIX_RE.sub("", line)
    line = _MARKUP_RE.sub("", line)
    return normalize(line.replace("|", " "))


def _words(text):
    return [word for word in text.split(" ") if any(c.isalnum() for c in word)]


def snippets_for_line(markdown, line_number):
    """What to look for in the PDF to find where the markdown's line
    `line_number` (1-based) ended up: ([text, ...] most specific first,
    how far through the document the line is as 0-1). The line itself if
    it has text to match, else the nearest line above that does; ([], 0.0)
    if there's none.
    """
    lines = markdown.split("\n")
    if not lines:
        return [], 0.0
    start = max(1, min(line_number, len(lines)))
    for number in range(start, max(0, start - LOOK_BACK_LINES), -1):
        words = _words(plain(lines[number - 1]))
        # One short word matches all over the place.
        if len(words) >= 2 or (words and len(words[0]) >= 5):
            snippets = []
            for count in SNIPPET_WORDS:
                snippet = " ".join(words[:count])
                if snippet not in snippets:
                    snippets.append(snippet)
            return snippets, (number - 1) / len(lines)
    return [], 0.0


def line_for_text(markdown, text, fraction):
    """The markdown line (1-based) that produced `text`, a run of
    (normalized) text from the PDF found `fraction` (0-1) of the way
    through it -- or None if no line matches. Of several matching lines,
    the one nearest that far through the markdown wins.
    """
    wanted = _SECTION_NUMBER_RE.sub("", normalize(text))
    words = _words(wanted)
    if not words or (len(words) == 1 and len(words[0]) < 4):
        return None
    lines = markdown.split("\n")
    plains = [plain(line) for line in lines]
    # The whole run, then shorter openings of it: a run can spill past the
    # end of what one markdown line produced.
    for count in (len(words), 6, 4, 3, 2):
        if count > len(words):
            continue
        needle = " ".join(words[:count])
        matches = [i for i, candidate in enumerate(plains) if needle in " ".join(_words(candidate))]
        if matches:
            return min(matches, key=lambda i: abs(i / len(lines) - fraction)) + 1
    return None
