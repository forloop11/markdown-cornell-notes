"""Minimal flat "key: value" YAML parser, shared by the generator scripts.

Supports only flat scalar mappings (no nesting, lists, or multi-line
values) -- everything these scripts' YAML sources need. Avoids a PyYAML
dependency for something this simple.
"""
import os


def _unescape_double_quoted(inner):
    r"""Reverse the `\` -> `\\`, `"` -> `\"` escaping applied by
    pipeline.write_header. A backslash before any other character isn't
    an escape sequence this format produces, so it's left as-is.
    """
    result = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner) and inner[i + 1] in "\\\"":
            result.append(inner[i + 1])
            i += 2
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def strip_quotes(value):
    """Strip a matching pair of surrounding quotes from `value`, if any,
    unescaping backslash-escapes for a double-quoted value. Returns
    `value` unchanged if it isn't quoted.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return _unescape_double_quoted(inner) if value[0] == '"' else inner
    return value


def parse_yaml(path):
    """Parse `path` as a flat "key: value" mapping and return it as a
    dict of strings. Blank lines and "#"-prefixed comments (including a
    trailing "# comment" on a value line) are ignored. Raises ValueError
    on a line that isn't blank/a comment and doesn't contain ":".
    """
    fields = {}
    with open(path, encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            if ":" not in line:
                raise ValueError(f"{path}:{lineno}: expected 'key: value', got: {raw_line!r}")
            key, _, value = line.partition(":")
            fields[key.strip()] = strip_quotes(value.strip())
    return fields


def write_generated(out_path, lines):
    """Write `lines` (joined with newlines, plus a trailing newline) to
    `out_path`, creating its parent directory first if needed.
    """
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
