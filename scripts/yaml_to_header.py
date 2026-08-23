#!/usr/bin/env python3
"""Convert meeting.yaml into build/cornell-header.tex.

Supports the flat "key: value" subset of YAML used for the Cornell notes
header fields (topic, date, attendees, time, project) -- no nesting, lists,
or multi-line values. Avoids a PyYAML dependency since the header data is
always this simple.

Usage (from the repo root): python3 scripts/yaml_to_header.py [input.yaml] [output.tex]
"""
import os
import sys

FIELD_MACROS = {
    "topic": "cnHdrTopic",
    "date": "cnHdrDate",
    "attendees": "cnHdrAttendees",
    "time": "cnHdrTime",
    "project": "cnHdrProject",
}

LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(value):
    return "".join(LATEX_SPECIALS.get(ch, ch) for ch in value)


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


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else "meeting.yaml"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "build/cornell-header.tex"

    fields = parse_yaml(in_path)

    unknown = set(fields) - set(FIELD_MACROS)
    if unknown:
        raise ValueError(f"{in_path}: unrecognized field(s): {', '.join(sorted(unknown))}")

    lines = [
        f"% Generated from {in_path} by scripts/yaml_to_header.py -- do not edit by hand.",
    ]
    for key, macro in FIELD_MACROS.items():
        value = escape_latex(fields.get(key, ""))
        lines.append(f"\\renewcommand{{\\{macro}}}{{{value}}}")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
