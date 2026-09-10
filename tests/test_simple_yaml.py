"""Tests for scripts/simple_yaml.py's parse_yaml and strip_quotes."""
import pytest

from simple_yaml import parse_yaml, strip_quotes


def test_strip_quotes_double_quoted():
    """A double-quoted value has its surrounding quotes stripped."""
    assert strip_quotes('"hello"') == "hello"


def test_strip_quotes_single_quoted_not_unescaped():
    """A single-quoted value's backslashes pass through literally.

    Only double-quoted values get backslash-escape handling (matching
    pipeline.write_header, which only ever emits double quotes).
    """
    assert strip_quotes("'a\\b'") == "a\\b"


def test_strip_quotes_unquoted_passthrough():
    """A value with no surrounding quotes is returned unchanged."""
    assert strip_quotes("no quotes here") == "no quotes here"


def test_strip_quotes_unescapes_quote_and_backslash():
    """A double-quoted value's escaped quotes/backslashes are unescaped
    back to their literal characters.

    Mirrors pipeline.write_header's escaping: backslash -> \\\\, then
    " -> \\".
    """
    raw = '"Say \\"hi\\" \\\\ok"'
    assert strip_quotes(raw) == 'Say "hi" \\ok'


def test_strip_quotes_lone_trailing_backslash():
    """A trailing backslash with nothing after it isn't a recognized
    escape -- left as a literal character rather than swallowed or
    erroring.
    """
    assert strip_quotes('"a\\"') == "a\\"


def test_parse_yaml_basic(tmp_path):
    """A simple double-quoted "key: value" file parses to a plain dict."""
    path = tmp_path / "t.yaml"
    path.write_text('topic: "Weekly Sync"\ndate: "2026-08-23"\n', encoding="utf-8")
    fields = parse_yaml(path)
    assert fields == {"topic": "Weekly Sync", "date": "2026-08-23"}


def test_parse_yaml_skips_comments_and_blank_lines(tmp_path):
    """Blank lines, a leading "#" comment line, and a trailing "# comment"
    on a value line are all ignored.
    """
    path = tmp_path / "t.yaml"
    path.write_text(
        "# a leading comment\n"
        "\n"
        'topic: "Standup"  # trailing comment\n'
        "\n",
        encoding="utf-8",
    )
    fields = parse_yaml(path)
    assert fields == {"topic": "Standup"}


def test_parse_yaml_unquoted_value(tmp_path):
    """A value with no surrounding quotes parses as-is."""
    path = tmp_path / "t.yaml"
    path.write_text("topic: bare-value\n", encoding="utf-8")
    assert parse_yaml(path) == {"topic": "bare-value"}


def test_parse_yaml_missing_colon_raises(tmp_path):
    """A non-blank, non-comment line without a ":" raises ValueError."""
    path = tmp_path / "t.yaml"
    path.write_text("not a key value line\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_yaml(path)
