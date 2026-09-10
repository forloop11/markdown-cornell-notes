from markdown_to_pages import escape_stray_backslashes


def test_prose_backslash_is_doubled():
    # The exact bug this guards against: a Windows path in ordinary prose
    # crashed the LaTeX build ("Undefined control sequence") because
    # pandoc passes a bare "\U"/"\A"/"\D" straight through unescaped.
    assert (
        escape_stray_backslashes(r"C:\Users\Alex\Documents\notes")
        == r"C:\\Users\\Alex\\Documents\\notes"
    )


def test_regex_like_text_is_doubled():
    assert escape_stray_backslashes(r"match \d+ or \s* please") == r"match \\d+ or \\s* please"


def test_valid_punctuation_escape_untouched():
    assert escape_stray_backslashes(r"an escaped \*asterisk\* here") == r"an escaped \*asterisk\* here"


def test_already_doubled_backslash_untouched():
    assert escape_stray_backslashes(r"literal \\vfill already escaped") == r"literal \\vfill already escaped"


def test_inline_code_span_untouched():
    assert escape_stray_backslashes(r"code: `\vfill` stays raw") == r"code: `\vfill` stays raw"


def test_double_backtick_code_span_untouched():
    assert escape_stray_backslashes(r"code: ``\vfill` with a backtick`` end") == r"code: ``\vfill` with a backtick`` end"


def test_fenced_code_block_untouched():
    text = "```\n\\vfill in a fence\n```"
    assert escape_stray_backslashes(text) == text


def test_fenced_code_block_with_language_tag_untouched():
    text = "```python\nprint('\\vfill')\n```"
    assert escape_stray_backslashes(text) == text


def test_inline_math_untouched():
    text = r"math: $\int_0^1 x^2\,dx$"
    assert escape_stray_backslashes(text) == text


def test_display_math_untouched():
    text = r"$$\int_0^1 x^2\,dx = \frac{1}{3}$$"
    assert escape_stray_backslashes(text) == text


def test_hard_line_break_backslash_preserved():
    # A single trailing backslash is pandoc's hard-line-break syntax, not
    # a literal character -- must not be doubled.
    text = "line one\\\nline two"
    assert escape_stray_backslashes(text) == text


def test_mixed_code_and_prose_on_same_line():
    text = r"the `\vfill` command vs a literal \vfill in prose"
    expected = r"the `\vfill` command vs a literal \\vfill in prose"
    assert escape_stray_backslashes(text) == expected


def test_hard_line_break_detection_is_per_line_not_per_document():
    # The hard-break exception is based on each *line* ending in a single
    # backslash, not just the end of the whole string -- a mid-document
    # line break is just as much a hard break as one on the last line.
    text = "first line\\\nsecond line\\\nthird line"
    assert escape_stray_backslashes(text) == text


def test_backslash_followed_by_space_is_stray():
    # Only a backslash immediately before the line's own end is a hard
    # break -- one followed by a space (or anything else) mid-line is
    # still a stray, dangerous backslash and must be doubled.
    assert escape_stray_backslashes("a path ending in C:\\Users\\ soon") == "a path ending in C:\\\\Users\\\\ soon"
