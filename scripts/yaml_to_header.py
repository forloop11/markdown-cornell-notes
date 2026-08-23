#!/usr/bin/env python3
"""Convert meeting.yaml into build/cornell-header.tex.

Supports the flat "key: value" subset of YAML used for the Cornell notes
header fields (topic, date, attendees, time, project) -- no nesting, lists,
or multi-line values. Avoids a PyYAML dependency since the header data is
always this simple.

Usage (from the repo root): python3 scripts/yaml_to_header.py [input.yaml] [output.tex]
"""
import sys

from simple_yaml import parse_yaml, write_generated

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

    write_generated(out_path, lines)


if __name__ == "__main__":
    main()
