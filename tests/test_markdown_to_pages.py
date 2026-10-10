"""Tests for scripts/markdown_to_pages.py's escape_stray_backslashes."""
from markdown_to_pages import center_standalone_images, escape_stray_backslashes, unwrap_pandocbounded


def test_prose_backslash_is_doubled():
    r"""The exact bug this guards against: a Windows path in ordinary
    prose crashed the LaTeX build ("Undefined control sequence") because
    pandoc passes a bare "\U"/"\A"/"\D" straight through unescaped.
    """
    assert (
        escape_stray_backslashes(r"C:\Users\Alex\Documents\notes")
        == r"C:\\Users\\Alex\\Documents\\notes"
    )


def test_regex_like_text_is_doubled():
    """A regex-like string ("\\d+", "\\s*") is doubled the same as any
    other stray backslash in prose.
    """
    assert escape_stray_backslashes(r"match \d+ or \s* please") == r"match \\d+ or \\s* please"


def test_valid_punctuation_escape_untouched():
    r"""A backslash already followed by escapable punctuation (e.g.
    "\*") is left alone -- pandoc already renders it safely.
    """
    assert escape_stray_backslashes(r"an escaped \*asterisk\* here") == r"an escaped \*asterisk\* here"


def test_already_doubled_backslash_untouched():
    """An already-doubled "\\\\" pair is left alone, not re-escaped."""
    assert escape_stray_backslashes(r"literal \\vfill already escaped") == r"literal \\vfill already escaped"


def test_inline_code_span_untouched():
    r"""A backslash inside a single-backtick inline code span (`` `\vfill` ``)
    is left alone -- pandoc already renders it safely there.
    """
    assert escape_stray_backslashes(r"code: `\vfill` stays raw") == r"code: `\vfill` stays raw"


def test_double_backtick_code_span_untouched():
    """A backslash inside a double-backtick code span (which may itself
    contain a literal backtick) is left alone.
    """
    assert escape_stray_backslashes(r"code: ``\vfill` with a backtick`` end") == r"code: ``\vfill` with a backtick`` end"


def test_fenced_code_block_untouched():
    """A backslash inside a fenced code block (```` ``` ````) is left alone."""
    text = "```\n\\vfill in a fence\n```"
    assert escape_stray_backslashes(text) == text


def test_fenced_code_block_with_language_tag_untouched():
    """A fenced code block's language tag (```` ```python ````) doesn't
    prevent its content from being recognized as code.
    """
    text = "```python\nprint('\\vfill')\n```"
    assert escape_stray_backslashes(text) == text


def test_inline_math_untouched():
    r"""A backslash inside inline math ($...$) is left alone -- a raw
    LaTeX command there (e.g. "\int") is often intentional.
    """
    text = r"math: $\int_0^1 x^2\,dx$"
    assert escape_stray_backslashes(text) == text


def test_display_math_untouched():
    """A backslash inside display math ($$...$$) is left alone, same as
    inline math.
    """
    text = r"$$\int_0^1 x^2\,dx = \frac{1}{3}$$"
    assert escape_stray_backslashes(text) == text


def test_hard_line_break_backslash_preserved():
    """A single trailing backslash is pandoc's hard-line-break syntax,
    not a literal character -- must not be doubled.
    """
    text = "line one\\\nline two"
    assert escape_stray_backslashes(text) == text


def test_mixed_code_and_prose_on_same_line():
    r"""A code span and a stray backslash can coexist on the same line --
    only the prose backslash outside the span gets doubled.
    """
    text = r"the `\vfill` command vs a literal \vfill in prose"
    expected = r"the `\vfill` command vs a literal \\vfill in prose"
    assert escape_stray_backslashes(text) == expected


def test_hard_line_break_detection_is_per_line_not_per_document():
    """The hard-break exception is based on each *line* ending in a
    single backslash, not just the end of the whole string -- a
    mid-document line break is just as much a hard break as one on the
    last line.
    """
    text = "first line\\\nsecond line\\\nthird line"
    assert escape_stray_backslashes(text) == text


def test_backslash_followed_by_space_is_stray():
    """Only a backslash immediately before the line's own end is a hard
    break -- one followed by a space (or anything else) mid-line is
    still a stray, dangerous backslash and must be doubled.
    """
    assert escape_stray_backslashes("a path ending in C:\\Users\\ soon") == "a path ending in C:\\\\Users\\\\ soon"


def test_pandocbounded_wrapper_around_an_unsized_image_is_removed():
    # What pandoc 3.2+ emits for ![Tux](assets/tux.jpg): a macro only its
    # own LaTeX template defines.
    wrapped = r"\pandocbounded{\includegraphics[keepaspectratio,alt={Tux}]{assets/tux.jpg}}"
    bare = r"\includegraphics[keepaspectratio,alt={Tux}]{assets/tux.jpg}"
    assert unwrap_pandocbounded(wrapped) == bare
    assert unwrap_pandocbounded(f"text {wrapped} inline") == f"text {bare} inline"
    # Unwrapped, a standalone image is centered like a sized one.
    assert center_standalone_images(unwrap_pandocbounded(wrapped)) == "{\\centering\n" + bare + "\\par}"


def test_a_sized_image_without_the_wrapper_is_left_alone():
    sized = r"\includegraphics[width=0.78125in,height=\textheight,keepaspectratio,alt={T}]{assets/t.jpg}"
    assert unwrap_pandocbounded(sized) == sized
