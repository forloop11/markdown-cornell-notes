"""Tests for app/sync.py: matching markdown lines with text in the PDF, for
the editor <-> preview sync.
"""
import sync

NOTES = """# Text Formatting

Welcome to the jungle. We've got fun and games.

^1 This is my question for Cue on page 1

<!-- a comment that prints nothing -->

**Bold**, *italic*, `inline code`, and ~~strikethrough~~.

# Lists

- Bullet item
- [x] Completed task
1. First

See the [project page](https://example.com/x) -- it's "quoted"...

| Name | Role |
|------|------|
| Lily | Lead |

Inline $x^2$ math here.

# Lists
"""


def line(text):
    return NOTES.split("\n").index(text) + 1


def test_normalize_folds_typography_case_and_spacing():
    assert sync.normalize("Ofﬁce  “Hours” – it’s…") == 'office "hours" - it\'s...'
    assert sync.normalize("a -- b --- c") == "a - b - c"


def test_plain_reads_a_line_as_the_pdf_will():
    assert sync.plain("## Text Formatting") == "text formatting"
    assert sync.plain("^1 This is my question") == "this is my question"
    assert sync.plain("^^2 A summary") == "a summary"
    assert sync.plain("- [x] Completed task") == "completed task"
    assert sync.plain("3. Third") == "third"
    assert sync.plain("> A quoted line") == "a quoted line"
    assert sync.plain("**Bold**, *italic*, `inline code`, and ~~strikethrough~~.") == "bold, italic, inline code, and strikethrough."
    assert sync.plain("See the [project page](https://example.com/x) now") == "see the project page now"
    assert sync.plain("![Tux](assets/tux.jpg){width=75px}") == ""
    assert sync.plain("| Lily | Lead |") == "lily lead"
    for nothing in ("", "   ", "<!-- pagebreak -->", "|------|------|", "```python", "$$x^2$$"):
        assert sync.plain(nothing) == "", nothing


def test_snippets_for_a_line_run_from_most_to_least_specific():
    snippets, fraction = sync.snippets_for_line(NOTES, line("Welcome to the jungle. We've got fun and games."))
    assert snippets == ["welcome to the jungle. we've got", "welcome to the jungle.", "welcome to the", "welcome to"]
    assert 0 < fraction < 0.2


def test_a_line_with_nothing_to_match_falls_back_to_the_text_above_it():
    comment = line("<!-- a comment that prints nothing -->")
    snippets, _ = sync.snippets_for_line(NOTES, comment + 1)  # the blank line after it
    assert snippets[0].startswith("this is my question for cue")
    # ...and a heading stands for the blank line under it.
    assert sync.snippets_for_line(NOTES, 2)[0] == ["text formatting"]


def test_snippets_cope_with_empty_notes_and_lines_out_of_range():
    assert sync.snippets_for_line("", 1) == ([], 0.0)
    assert sync.snippets_for_line("\n\n\n", 2) == ([], 0.0)
    assert sync.snippets_for_line(NOTES, 10_000)[0] == ["lists"]
    assert sync.snippets_for_line(NOTES, -5)[0] == ["text formatting"]


def test_line_for_text_finds_where_pdf_text_came_from():
    assert sync.line_for_text(NOTES, "welcome to the jungle.", 0.1) == line("Welcome to the jungle. We've got fun and games.")
    # A heading as LaTeX numbers it.
    assert sync.line_for_text(NOTES, "1 text formatting", 0.0) == 1
    # Text with its markup gone, and typographic quotes back to plain.
    assert sync.line_for_text(NOTES, "bold, italic, inline code", 0.3) == line(
        "**Bold**, *italic*, `inline code`, and ~~strikethrough~~."
    )
    assert sync.line_for_text(NOTES, sync.normalize("project page – it’s “quoted”"), 0.6) == line(
        'See the [project page](https://example.com/x) -- it\'s "quoted"...'
    )
    # A run that carries on past the line's own text still finds the line.
    assert sync.line_for_text(NOTES, "this is my question for cue on page 1 and then some more", 0.2) == line(
        "^1 This is my question for Cue on page 1"
    )


def test_line_for_text_picks_the_nearer_of_two_identical_lines():
    first, last = NOTES.split("\n").index("# Lists") + 1, len(NOTES.split("\n")) - 1
    assert sync.line_for_text(NOTES, "2 lists", 0.3) == first
    assert sync.line_for_text(NOTES, "2 lists", 0.95) == last


def test_line_for_text_gives_up_on_text_too_short_or_not_there():
    assert sync.line_for_text(NOTES, "1", 0.5) is None
    assert sync.line_for_text(NOTES, "the", 0.5) is None
    assert sync.line_for_text(NOTES, "nowhere in these notes", 0.5) is None
