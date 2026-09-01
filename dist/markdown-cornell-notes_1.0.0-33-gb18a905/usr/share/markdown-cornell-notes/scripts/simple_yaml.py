"""Minimal flat "key: value" YAML parser, shared by the generator scripts.

Supports only flat scalar mappings (no nesting, lists, or multi-line
values) -- everything these scripts' YAML sources need. Avoids a PyYAML
dependency for something this simple.
"""
import os


def strip_quotes(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_yaml(path):
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
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
